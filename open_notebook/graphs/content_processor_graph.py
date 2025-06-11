from typing import Optional, TypedDict, Union, Dict, Any, Literal
from pathlib import Path
from loguru import logger
from langgraph.graph import StateGraph, END, START
import re

from open_notebook.tools.ocr_tool import (
    extract_text_from_image as ocr_extract_text_from_image,
    extract_text_from_pdf,
)
from open_notebook.tools.speech_to_text_tool import speech_to_text
from open_notebook.tools.youtube_transcript_tool import get_youtube_transcript
from open_notebook.tools.website_scraper import get_content_from_url, get_title_from_url
from open_notebook.tools.unstructured_file_loader import load_file_content
from open_notebook.tools.image_captioning_tool import get_text_from_image
from langchain_docling import DoclingLoader
from langchain_community.document_loaders import CSVLoader, UnstructuredFileLoader
from langchain_core.documents import Document
from docling.document_converter import DocumentConverter
from open_notebook.graphs.content_processing.youtube import get_video_title as get_youtube_video_title_specific
# from open_notebook.config import UPLOADS_FOLDER # Not directly used in this graph


class ContentState(TypedDict):
    """
    Represents the state of content being processed.
    """
    # Fields from the error message
    content: Optional[str]
    file_path: Optional[str]
    url: Optional[str]
    title: Optional[str]
    source_type: Optional[str] # Main type after processing, e.g., 'pdf', 'youtube', 'webpage'
    identified_type: Optional[str] # More granular type, could be same as source_type or more specific
    identified_provider: Optional[str] # e.g., 'youtube', 'vimeo'
    metadata: Optional[Dict[str, Any]] # For any other metadata
    delete_source: Optional[bool]
    bypass_llm_filter: Optional[bool] # Added for LLM filter bypass flag
    processing_method: Optional[Literal['docling', 'legacy']] = 'docling' # Added processing_method
    use_llm_content_filter: Optional[bool] = False # New field for link-specific LLM filter

    # Other potentially useful fields (can be added based on existing graph needs)
    error: Optional[str]
    # youtube_url: Optional[str] # No longer primary input, url is used.


def get_source_type_from_path(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    logger.debug(f"get_source_type_from_path: file_path='{file_path}', ext='{ext}'")
    
    # Ensure .webp is handled for completeness, though not strictly necessary for current issue
    if ext in ['.jpg', '.jpeg', '.png', '.webp']: 
        logger.debug(f"get_source_type_from_path: returning 'image' for ext '{ext}'")
        return 'image'
    elif ext == '.pdf':
        logger.debug(f"get_source_type_from_path: returning 'pdf' for ext '{ext}'")
        return 'pdf'
    elif ext in ['.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a']:
        logger.debug(f"get_source_type_from_path: returning 'audio' for ext '{ext}'")
        return 'audio'
    elif ext in ['.mp4', '.mov', '.avi', '.mkv']:
        logger.debug(f"get_source_type_from_path: returning 'video' for ext '{ext}'")
        return 'video'
    elif ext == '.txt':
        logger.debug(f"get_source_type_from_path: returning 'txt' for ext '{ext}'")
        return 'txt'
    elif ext in ['.doc', '.docx']:
        logger.debug(f"get_source_type_from_path: returning 'docx' for ext '{ext}'")
        return 'docx'
    elif ext == '.csv':
        logger.debug(f"get_source_type_from_path: returning 'csv' for ext '{ext}'")
        return 'csv'
    
    logger.debug(f"get_source_type_from_path: returning 'unknown' for ext '{ext}'")
    return 'unknown'

async def process_youtube_url(state: ContentState) -> ContentState:
    video_url_raw = state.get("url") # Get the URL from the 'url' field
    if not video_url_raw:
        logger.error("process_youtube_url called with missing URL in state.")
        return {**state, "error": "URL missing for YouTube processing", "content": ""}

    video_url = video_url_raw.strip() # Strip whitespace
    if not video_url: # Explicitly check if URL is empty after stripping
        logger.error("process_youtube_url called with an empty URL string.")
        return {**state, "error": "Empty URL provided for YouTube processing.", "content": ""}

    logger.debug(f"Processing YouTube URL (stripped): {video_url}")

    # Preserve bypass_llm_filter flag from input state
    bypass_filter = state.get("bypass_llm_filter", False)

    try:
        # Extract video_id first, as it's needed for fallback title and specific title fetching
        video_id_match = (
            re.search(r"watch\?v=([^&]+)", video_url) or
            re.search(r"youtu\.be/([^&?]+)", video_url) or
            re.search(r"/live/([^&?/\\#]+)", video_url) # Added to handle /live/ URLs
        )
        
        video_id = video_id_match.group(1) if video_id_match else None

        if not video_id:
            logger.warning(f"Could not extract video_id from YouTube URL: {video_url}")
            # Use the URL itself or a generic error title if video_id extraction fails.
            video_title = video_url 
            transcript = "Error: Could not extract video ID from URL."
        else:
            # Attempt to get a title using the YouTube-specific function first
            video_title = await get_youtube_video_title_specific(video_id)
            logger.info(f"Attempted specific YouTube title fetch for {video_id}: '{video_title}'")

            # Fallback to general get_title_from_url if specific one fails or returns empty
            if not video_title:
                logger.info(f"Specific YouTube title fetch failed for {video_id}, falling back to general get_title_from_url.")
                video_title = await get_title_from_url(video_url)
            
            # Further fallback title logic if all else fails or gives generic/error titles
            if not video_title or video_title == video_url or "processing error" in video_title.lower() or video_title.lower() in ["watch", "/watch", "youtube"]:
                old_title = video_title # for logging
                video_title = f"YouTube Video ({video_id})"
                logger.info(f"Using fallback title for YouTube video ({video_id}): '{video_title}' (was: '{old_title}')")

            # Get transcript (video_id is available here)
            transcript = get_youtube_transcript(video_url) # This function also extracts video_id internally, but we have it.
        
        if transcript.startswith("Error:"):
            logger.warning(f"Failed to get transcript for {video_url}: {transcript}")
            return {
                **state,
                "content": transcript, # Use the error message as content
                "title": video_title,
                "error": transcript, # Also keep it in the error field
                "source_type": "youtube",
                "identified_type": "video_transcript",
                "identified_provider": "youtube",
                "metadata": {"original_url": video_url},
                "bypass_llm_filter": bypass_filter # Carry over the flag
            }
        
        logger.info(f"Successfully fetched transcript for {video_url}")
        return {
            **state,
            "content": transcript,
            "title": video_title,
            "source_type": "youtube",
            "identified_type": "video_transcript",
            "identified_provider": "youtube",
            "metadata": {"original_url": video_url},
            "bypass_llm_filter": bypass_filter, # Carry over the flag
            "error": None # Clear any prior error
        }
    except Exception as e:
        logger.exception(f"Exception in process_youtube_url for {video_url}")
        error_message = f"Error: A critical error occurred in process_youtube_url: {str(e)}"
        return {
            **state,
            "content": error_message, # Ensure content shows the error
            "title": "YouTube Video (Processing Error)",
            "error": error_message,
            "source_type": "youtube",
            "identified_type": "video_transcript",
            "identified_provider": "youtube",
            "metadata": {"original_url": video_url},
            "bypass_llm_filter": bypass_filter # Carry over the flag
        }

async def process_general_url(state: ContentState) -> ContentState:
    url_input_raw = state.get("url")
    # Get the specific LLM filter setting for links, default to False (off, meaning filter is NOT used by default)
    user_wants_llm_filter_for_link = state.get("use_llm_content_filter", False)
    
    # This is the original bypass_llm_filter from the state, typically for "Scrape all website"
    # It should be preserved if present, or defaulted.
    original_bypass_llm_filter_for_scrape = state.get("bypass_llm_filter", False)

    if not url_input_raw:
        logger.error("process_general_url called with missing URL in state.")
        return {
            **state, 
            "error": "URL missing for general processing", 
            "content": "", 
            "use_llm_content_filter": user_wants_llm_filter_for_link, # Preserve user's choice for this link
            "bypass_llm_filter": original_bypass_llm_filter_for_scrape # Preserve original scrape setting
        }

    url_input = url_input_raw.strip()
    if not url_input:
        logger.error("process_general_url called with an empty URL string.")
        return {
            **state, 
            "error": "Empty URL provided for general processing.", 
            "content": "", 
            "use_llm_content_filter": user_wants_llm_filter_for_link, # Preserve user's choice
            "bypass_llm_filter": original_bypass_llm_filter_for_scrape # Preserve original scrape setting
        }

    # For non-PDF URLs, the decision to USE the LLM filter comes from user_wants_llm_filter_for_link.
    # The get_content_from_url function's bypass_llm_filter param is True if we want to SKIP the filter.
    # So, effective_bypass_for_url_tool = not user_wants_llm_filter_for_link
    effective_bypass_for_url_tool = True # Default to bypassing (not using) the filter
    if not url_input.lower().endswith(".pdf"):
        effective_bypass_for_url_tool = not user_wants_llm_filter_for_link

    logger.debug(f"Processing general URL (stripped): {url_input}, User wants LLM Filter for this link: {user_wants_llm_filter_for_link}, Effective Bypass for get_content_from_url: {effective_bypass_for_url_tool}")
    
    processing_method = state.get("processing_method", "docling")
    docling_failed = False
    content = ""
    title = ""
    source_type = ""
    identified_type = ""

    try:
        if url_input.lower().endswith(".pdf"):
            source_type = "pdf"
            identified_type = "pdf_document"
            title = await get_title_from_url(url_input) or Path(url_input).name
            
            # LLM content filter is not applicable to direct PDF URLs, it's for web page content
            logger.info(f"Processing PDF URL: {url_input}. LLM content filter is bypassed.")

            if processing_method == "docling":
                try:
                    logger.info(f"Attempting to process PDF URL with Docling: {url_input}")
                    loader = DoclingLoader(url_input)
                    docs = loader.load()
                    content = "\\n\\n".join([doc.page_content for doc in docs]) if docs else ""
                    if not content:
                        logger.warning(f"Docling processed PDF URL {url_input} but returned no content.")
                except Exception as e_docling:
                    logger.error(f"Docling failed for PDF URL {url_input}: {e_docling}. Falling back to legacy.")
                    docling_failed = True
            
            if processing_method == "legacy" or docling_failed:
                logger.info(f"Processing PDF URL with legacy method: {url_input}")
                content = extract_text_from_pdf(url_input, is_url=True)
        else: 
            # For non-PDFs, use the effective_bypass_for_url_tool based on user's checkbox
            content = await get_content_from_url(url_input, bypass_llm_filter=effective_bypass_for_url_tool)
            title = await get_title_from_url(url_input) or url_input
            source_type = "webpage"
            identified_type = "html_content"
        
        return {
            **state,
            "content": content,
            "title": title,
            "source_type": source_type,
            "identified_type": identified_type,
            "metadata": {"original_url": url_input},
            "use_llm_content_filter": user_wants_llm_filter_for_link, # Carry over the user's choice for this specific link
            "bypass_llm_filter": original_bypass_llm_filter_for_scrape, # Preserve original general scrape setting
            "error": None
        }
    except Exception as e:
        logger.exception(f"Error processing general URL {url_input}")
        return {
            **state, 
            "error": str(e), 
            "title": url_input or "URL Processing Error", 
            "content": "", 
            "use_llm_content_filter": user_wants_llm_filter_for_link, # Preserve choice
            "bypass_llm_filter": original_bypass_llm_filter_for_scrape # Preserve scrape setting
        }

def process_file(state: ContentState) -> ContentState:
    file_path_str = state.get("file_path")
    # Preserve original bypass_llm_filter flag (for scraping) from input state.
    # It's not directly used by file processing types here but should be carried forward.
    original_bypass_llm_filter_for_scrape = state.get("bypass_llm_filter", False)
    # Preserve use_llm_content_filter (for links) from input state.
    # It's not directly used by file processing types but should be carried forward if somehow set.
    user_wants_llm_filter_for_link = state.get("use_llm_content_filter", False)
    
    logger.debug(f"--- process_file node START --- file_path_str from state: '{file_path_str}', Original Scrape Bypass: {original_bypass_llm_filter_for_scrape}, Link LLM Filter Choice: {user_wants_llm_filter_for_link}")

    if not file_path_str:
        logger.warning("process_file: file_path_str is None or empty. Returning error.")
        return {
            **state, 
            "error": "File path missing", 
            "content": "", 
            "bypass_llm_filter": original_bypass_llm_filter_for_scrape,
            "use_llm_content_filter": user_wants_llm_filter_for_link
        }
    
    file_path_obj = Path(file_path_str)
    file_source_type = get_source_type_from_path(file_path_str) # This now has internal logging
    logger.info(f"process_file: Determined file_source_type='{file_source_type}' for file '{file_path_obj.name}'") # Log determined type

    title = file_path_obj.name
    content = ""
    error = None
    processing_method = state.get("processing_method", "docling") # Get processing method
    docling_failed = False

    # Determine the MIME type for image processing
    mime_type = "image/jpeg" # Default
    if file_source_type == 'image':
        ext = file_path_obj.suffix.lower()
        if ext == '.png':
            mime_type = "image/png"
        elif ext == '.webp':
            mime_type = "image/webp"
        # jpeg is default

    try:
        if file_source_type == 'image':
            # Use the new image captioning tool
            image_prompt = "Describe the content of this image in detail."
            logger.info(f"Using image_captioning_tool for {file_path_str} with prompt: '{image_prompt}' and mime_type: {mime_type}")
            content = get_text_from_image(image_path=str(file_path_obj), prompt=image_prompt, mime_type=mime_type)
            if content.startswith("Error:"):
                error = content # The tool returns error messages starting with "Error:"
                content = "" # Clear content if there was an error from the tool
        elif file_source_type == 'pdf':
            if processing_method == "docling":
                try:
                    logger.info(f"Attempting to process PDF file with Docling: {file_path_str}")
                    loader = DoclingLoader(str(file_path_obj))
                    docs = loader.load()
                    content = "\\n\\n".join([doc.page_content for doc in docs]) if docs else ""
                    if not content:
                        logger.warning(f"Docling processed PDF file {file_path_str} but returned no content. Setting docling_failed=True.")
                        docling_failed = True
                except Exception as e_docling:
                    logger.error(f"Docling failed for PDF file {file_path_str}: {e_docling}. Falling back to legacy.")
                    docling_failed = True
            
            if processing_method == "legacy" or docling_failed:
                logger.info(f"Processing PDF file with legacy method: {file_path_str}")
                content = extract_text_from_pdf(str(file_path_obj))
        elif file_source_type == 'csv':
            if processing_method == "docling":
                docling_failed = False
                try:
                    logger.info(f"Attempting to process CSV file with Docling (DocumentConverter targeting markdown table): {file_path_str}")
                    
                    converter = DocumentConverter()
                    result = converter.convert(str(file_path_obj)) # Use converter.convert()

                    if result and result.document:
                        docling_doc = result.document
                        # Use default export, which seems to be GFM table for CSVs
                        content = docling_doc.export_to_markdown()
                        logger.info(f"Docling default export_to_markdown() for CSV {file_path_str} (type: {type(content)}):") # End f-string before newline
                        logger.info(content) # Log the actual content on a new line
                        
                        if not content: # Check if content is empty after conversion
                            logger.warning(f"Docling (via DocumentConverter and default export_to_markdown) for CSV {file_path_str} resulted in no content. Setting docling_failed=True.")
                            docling_failed = True
                    else:
                        logger.warning(f"Docling DocumentConverter().convert() failed to produce a result or document for CSV: {file_path_str}")
                        docling_failed = True

                    if not docling_failed:
                         logger.debug(f"Docling (DocumentConverter with csv_to_markdown_table) markdown output for CSV {file_path_str}: {content[:1500]}...")
                    
                except Exception as e_docling:
                    logger.error(f"Docling (via DocumentConverter for markdown table) failed for CSV file {file_path_str}: {e_docling}. Setting docling_failed=True.")
                    docling_failed = True
                
                if docling_failed:
                    logger.info(f"Docling processing failed for CSV {file_path_str}. Falling back to CSVLoader.")
                    # Fallback to CSVLoader
                    try:
                        loader = CSVLoader(file_path=file_path_str)
                        docs = loader.load()
                        content = "\n".join([doc.page_content for doc in docs])
                        logger.info(f"Successfully processed CSV {file_path_str} with CSVLoader fallback.")
                    except Exception as e_csvloader:
                        logger.error(f"CSVLoader also failed for {file_path_str}: {e_csvloader}. Falling back to UnstructuredFileLoader.")
                        # Fallback to UnstructuredFileLoader
                        try:
                            loader = UnstructuredFileLoader(file_path_str)
                            docs = loader.load()
                            content = "\n".join([doc.page_content for doc in docs])
                            logger.info(f"Successfully processed CSV {file_path_str} with UnstructuredFileLoader fallback.")
                        except Exception as e_unstructured:
                            logger.error(f"UnstructuredFileLoader also failed for {file_path_str}: {e_unstructured}. No content extracted.")
                            content = "" # Ensure content is empty string if all fail
            else: # Legacy or Docling failed and fell through
                try:
                    logger.info(f"Processing CSV file with CSVLoader: {file_path_str}")
                    loader = CSVLoader(file_path=str(file_path_obj)) # CSVLoader might have different parameters
                    docs = loader.load()
                    content = "\n\n".join([doc.page_content for doc in docs]) if docs else ""
                except Exception as e_csvloader:
                    logger.error(f"CSVLoader also failed for {file_path_str}: {e_csvloader}. Falling back to unstructured.")
                    # Fallback to unstructured if CSVLoader also fails
                    legacy_docs = load_file_content(str(file_path_obj))
                    content = "\n\n".join([doc.page_content for doc in legacy_docs]) if legacy_docs else ""
                    if not content:
                        error = f"All CSV processing methods failed for {file_path_str}."

        elif file_source_type == 'docx':
            if processing_method == "docling":
                try:
                    logger.info(f"Attempting to process DOCX file with Docling: {file_path_str}")
                    loader = DoclingLoader(str(file_path_obj))
                    docs = loader.load()
                    content = "\\n\\n".join([doc.page_content for doc in docs]) if docs else ""
                    logger.debug(f"Docling output for DOCX {file_path_str}: {content[:500]}...")
                    if not content:
                        logger.warning(f"Docling processed DOCX {file_path_str} but returned no content. Will use unstructured.")
                        docling_failed = True
                except Exception as e_docling:
                    logger.error(f"Docling failed for DOCX file {file_path_str}: {e_docling}. Falling back to unstructured.")
                    docling_failed = True
            
            if processing_method == "legacy" or docling_failed:
                logger.info(f"Processing DOCX file with UnstructuredFileLoader (legacy): {file_path_str}")
                docs = load_file_content(str(file_path_obj))
                content = "\\n\\n".join([doc.page_content for doc in docs]) if docs else ""
                if not content:
                    error = f"UnstructuredFileLoader failed for DOCX {file_path_str}."

        elif file_source_type in ['audio', 'video']:
            content = speech_to_text(str(file_path_obj))
        elif file_source_type in ['txt', 'docx'] or file_source_type == 'unknown':
            docs = load_file_content(str(file_path_obj))
            content = "\\n\\n".join([doc.page_content for doc in docs]) if docs else ""
            if not content and file_source_type == 'unknown':
                 error = f"Unsupported file type or empty content: {file_source_type}"
        else:
            error = f"Unsupported file type: {file_source_type}"
    except Exception as e:
        logger.exception(f"Error processing file {file_path_str}")
        error = str(e)
        
    return {
        **state,
        "content": content,
        "title": title,
        "source_type": file_source_type, # Overall type
        "identified_type": file_source_type, # Can be same or more specific
        "error": error,
        "metadata": {"original_filename": file_path_obj.name},
        "bypass_llm_filter": original_bypass_llm_filter_for_scrape, # Carry over the original scrape bypass flag
        "use_llm_content_filter": user_wants_llm_filter_for_link # Carry over the link-specific filter choice
    }

def process_text_content(state: ContentState) -> ContentState:
    """Processes raw text content."""
    logger.debug("Processing text content.")
    content = state.get("content")
    if not content:
        logger.warning("process_text_content called with no content.")
        return {**state, "content": "", "error": "No content provided."}
    
    # Use the first 50 characters as the title
    title = content.strip()[:50] + "..."

    return {
        **state,
        "content": content,
        "title": title,
        "source_type": "text",
        "identified_type": "text",
        "error": None
    }

def route_content(state: ContentState) -> str:
    """Routes content to the appropriate processing node."""
    if state.get("error"):
        logger.warning(f"Routing to error handler due to pre-existing error: {state.get('error')}")
        return "error_handler"

    if state.get("url"):
        url = state.get("url", "").strip()
        logger.info(f"Routing content from URL: {url}")
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube_url"
        else:
            return "general_url"
    elif state.get("file_path"):
        logger.info(f"Routing content from file path: {state.get('file_path')}")
        return "file"
    elif state.get("content"):
        logger.info("Routing raw text content.")
        return "text_content"
    else:
        logger.error("Router unable to determine content source. Routing to error handler.")
        return "error_handler"

def handle_error_node(state: ContentState) -> ContentState:
    error_message = state.get('error', "Unknown error during content processing.")
    logger.error(f"Error Node: {error_message}")
    return {
        **state,
        "content": state.get("content", ""), # Ensure content exists
        "title": state.get("title", "Processing Error"),
        "error": error_message # Ensure error field is populated for END state
    }

graph_builder = StateGraph(ContentState)

graph_builder.add_node("process_youtube_url", process_youtube_url)
graph_builder.add_node("process_general_url", process_general_url)
graph_builder.add_node("process_file", process_file)
graph_builder.add_node("process_text_content", process_text_content)
graph_builder.add_node("error_node", handle_error_node)

graph_builder.add_conditional_edges(
    START,
    route_content,
    {
        "youtube_url": "process_youtube_url",
        "general_url": "process_general_url",
        "file": "process_file",
        "text_content": "process_text_content",
        "error_handler": "error_node"
    }
)

graph_builder.add_edge("process_youtube_url", END)
graph_builder.add_edge("process_general_url", END)
graph_builder.add_edge("process_file", END)
graph_builder.add_edge("process_text_content", END)
graph_builder.add_edge("error_node", END)

graph = graph_builder.compile()

if __name__ == "__main__":
    logger.remove() # Remove default logger
    logger.add(lambda msg: print(msg, end=''), format="{time} | {level} | {message}") # Print to stdout for testing

    print("--- Testing YouTube URL ---")
    youtube_state_input: ContentState = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", 
        "source_type": "youtube_link_initial",
        # Initialize other fields as None or default per ContentState definition
        "content": None, "file_path": None, "title": None, 
        "identified_type": None, "identified_provider": None, 
        "metadata": None, "delete_source": None, "error": None,
        "bypass_llm_filter": False
    }
    result_youtube = graph.invoke(youtube_state_input)
    print(f"YouTube Result: Error: {result_youtube.get('error')}, Title: {result_youtube.get('title')}, Content Length: {len(result_youtube.get('content', ''))}")
    # print(f"Full State: {result_youtube}")
    print("\n")

    print("--- Testing General Web URL ---")
    web_url_state_input: ContentState = {
        "url": "https://www.example.com", 
        "source_type": "url_initial", # or let router decide if source_type is None
        "content": None, "file_path": None, "title": None, 
        "identified_type": None, "identified_provider": None, 
        "metadata": None, "delete_source": None, "error": None,
        "bypass_llm_filter": False
    }
    result_web_url = graph.invoke(web_url_state_input)
    print(f"Web URL Result: Error: {result_web_url.get('error')}, Title: {result_web_url.get('title')}, Content Length: {len(result_web_url.get('content', ''))}")
    print("\n")

    print("--- Testing Direct Text Input ---")
    text_input_state: ContentState = {
        "content": "This is a direct piece of text provided by the user.",
        "title": "My Manual Note",
        "source_type": "text", # Explicitly set for direct text
        "url": None, "file_path": None, 
        "identified_type": None, "identified_provider": None, 
        "metadata": None, "delete_source": None, "error": None,
        "bypass_llm_filter": False
    }
    result_text = graph.invoke(text_input_state)
    print(f"Text Input Result: Error: {result_text.get('error')}, Title: {result_text.get('title')}, Content Length: {len(result_text.get('content', ''))}")
    print("\n")

    # To test file processing, create a dummy file:
    # with open("dummy_test_file.txt", "w") as f: f.write("Hello from dummy file.")
    # file_input_state: ContentState = {
    #     "file_path": "dummy_test_file.txt", 
    #     "source_type": "file_initial", 
    #     "content": None, "url": None, "title": None, 
    #     "identified_type": None, "identified_provider": None, 
    #     "metadata": None, "delete_source": False, "error": None
    # }
    # result_file = graph.invoke(file_input_state)
    # print(f"File Input Result: Error: {result_file.get('error')}, Title: {result_file.get('title')}, Content Length: {len(result_file.get('content', ''))}")
    # import os; os.remove("dummy_test_file.txt")

    logger.info("Example invocations complete. Check output.") 