from typing import Optional, TypedDict, Union, Dict, Any
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
    
    logger.debug(f"get_source_type_from_path: returning 'unknown' for ext '{ext}'")
    return 'unknown'

async def process_youtube_url(state: ContentState) -> ContentState:
    video_url = state.get("url") # Get the URL from the 'url' field
    logger.debug(f"Processing YouTube URL: {video_url}")
    if not video_url:
        logger.error("process_youtube_url called without URL in state.")
        return {**state, "error": "URL missing for YouTube processing", "content": ""}

    try:
        # Extract video_id first, as it's needed for fallback title
        video_id_match = re.search(r"watch\?v=([^&]+)", video_url) or re.search(r"youtu\.be/([^&?]+)", video_url)
        video_id_for_title = video_id_match.group(1) if video_id_match else "Unknown ID"

        transcript = get_youtube_transcript(video_url)
        
        # Attempt to get a title
        video_title = await get_title_from_url(video_url) 

        # Fallback title logic
        if not video_title or video_title == video_url or "processing error" in video_title.lower() or video_title.lower() in ["watch", "/watch"]:
            video_title = f"YouTube Video ({video_id_for_title})"
            logger.info(f"Using fallback title for YouTube video: {video_title}")
        
        if transcript.startswith("Error:"):
            logger.warning(f"Failed to get transcript for {video_url}: {transcript}")
            return {
                **state,
                "content": "",
                "title": video_title,
                "error": transcript,
                "source_type": "youtube",
                "identified_type": "video_transcript",
                "identified_provider": "youtube",
                "metadata": {"original_url": video_url}
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
            "error": None # Clear any prior error
        }
    except Exception as e:
        logger.exception(f"Exception in process_youtube_url for {video_url}")
        return {
            **state,
            "content": "",
            "title": "YouTube Video (Error)",
            "error": str(e),
            "source_type": "youtube",
            "identified_type": "video_transcript",
            "identified_provider": "youtube",
            "metadata": {"original_url": video_url}
        }

async def process_general_url(state: ContentState) -> ContentState:
    url_input = state.get("url")
    logger.debug(f"Processing general URL: {url_input}")
    if not url_input:
        return {**state, "error": "URL missing for general processing", "content": ""}
    try:
        if url_input.lower().endswith(".pdf"):
            # Assuming extract_text_from_pdf can handle URLs or local paths if needed by its own logic
            # If extract_text_from_pdf is also async, it needs to be awaited.
            # For now, assuming it's synchronous or handles its async nature internally if it's from a library.
            content = extract_text_from_pdf(url_input, is_url=True) 
            title = await get_title_from_url(url_input) or Path(url_input).name # Awaited
            source_type = "pdf"
            identified_type = "pdf_document"
        else: 
            content = await get_content_from_url(url_input) # Awaited
            title = await get_title_from_url(url_input) or url_input # Awaited
            source_type = "webpage"
            identified_type = "html_content"
        
        return {
            **state,
            "content": content,
            "title": title,
            "source_type": source_type,
            "identified_type": identified_type,
            "metadata": {"original_url": url_input},
            "error": None
        }
    except Exception as e:
        logger.exception(f"Error processing general URL {url_input}")
        return {**state, "error": str(e), "title": url_input or "URL Processing Error", "content": ""}

def process_file(state: ContentState) -> ContentState:
    file_path_str = state.get("file_path")
    logger.debug(f"--- process_file node START --- file_path_str from state: '{file_path_str}'") # Log entry and file_path_str

    if not file_path_str:
        logger.warning("process_file: file_path_str is None or empty. Returning error.")
        return {**state, "error": "File path missing", "content": ""}
    
    file_path_obj = Path(file_path_str)
    file_source_type = get_source_type_from_path(file_path_str) # This now has internal logging
    logger.info(f"process_file: Determined file_source_type='{file_source_type}' for file '{file_path_obj.name}'") # Log determined type

    title = file_path_obj.name
    content = ""
    error = None
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
            content = extract_text_from_pdf(str(file_path_obj))
        elif file_source_type in ['audio', 'video']:
            content = speech_to_text(str(file_path_obj))
        elif file_source_type in ['txt', 'docx'] or file_source_type == 'unknown':
            docs = load_file_content(str(file_path_obj))
            content = "\n\n".join([doc.page_content for doc in docs]) if docs else ""
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
        "metadata": {"original_filename": file_path_obj.name}
    }

def process_text_content(state: ContentState) -> ContentState:
    logger.debug("Processing direct text content.")
    pasted_content = state.get("content", "") # Content comes in directly
    return {
        **state,
        "content": pasted_content,
        "title": state.get("title") or "Pasted Text",
        "source_type": "text",
        "identified_type": "pasted_text",
        "error": None
    }

def route_content(state: ContentState) -> str:
    logger.debug(f"Routing content with state keys: {list(state.keys())}, source_type: {state.get('source_type')}, url: {state.get('url')[:50] if state.get('url') else None}")
    
    # Check for the temporary source_type from Streamlit UI
    if state.get("source_type") == "youtube_link_initial" and state.get("url"):
        logger.info("Routing to process_youtube_url based on initial type.")
        return "process_youtube_url"
    elif state.get("url"): # General URL (non-YouTube direct or after YouTube processing if URL is re-evaluated)
        logger.info("Routing to process_general_url.")
        return "process_general_url"
    elif state.get("file_path"):
        logger.info("Routing to process_file.")
        return "process_file"
    elif state.get("content") is not None and state.get("source_type") == "text": # Check for direct text
        logger.info("Routing to process_text_content.")
        return "process_text_content"
    else:
        logger.warning(f"No valid content input found for routing. State: { {k:v for k,v in state.items() if k!= 'content'} }")
        return "error_node"

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
        "process_youtube_url": "process_youtube_url",
        "process_general_url": "process_general_url",
        "process_file": "process_file",
        "process_text_content": "process_text_content",
        "error_node": "error_node"
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
        "metadata": None, "delete_source": None, "error": None
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
        "metadata": None, "delete_source": None, "error": None
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
        "metadata": None, "delete_source": None, "error": None
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