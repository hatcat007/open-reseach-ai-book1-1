import asyncio
import os
from pathlib import Path

import streamlit as st
from humanize import naturaltime
from loguru import logger

from open_notebook.config import UPLOADS_FOLDER
from open_notebook.domain.models import model_manager
from open_notebook.domain.notebook import Source
from open_notebook.domain.transformation import Transformation
from open_notebook.exceptions import UnsupportedTypeException
from open_notebook.graphs.source import source_graph
from open_notebook.tools.website_scraper import scrape_website
from pages.components import source_panel

from .consts import source_context_icons


@st.dialog("Source", width="large")
def source_panel_dialog(source_id, notebook_id=None):
    source_panel(source_id, notebook_id=notebook_id, modal=True)


@st.dialog("Add a Source", width="large")
def add_source(notebook_id):
    if not model_manager.speech_to_text:
        st.warning(
            "Since there is no speech to text model selected, you can't upload audio/video files."
        )
    
    # Initialize common variables
    source_link = None
    source_file = None
    source_text = None
    website_url_to_scrape = None
    max_pages_to_scrape = 0

    # Updated source types
    source_type_options = ["Link", "Upload", "Text", "Scrape all website", "YouTube Link"]
    source_type = st.radio("Type", source_type_options)
    
    # This will hold the primary input for the graph (either content_state or scraped_documents)
    graph_input_payload = {}
    # This will hold the specific content details (url, file_path, content) for single source types
    content_request_details = {}

    if source_type == "Link":
        source_link = st.text_input("Link (URL for a single page, PDF, etc.)")
        content_request_details["url"] = source_link
        graph_input_payload["content_state"] = content_request_details
    elif source_type == "Upload":
        source_file = st.file_uploader("Upload (PDF, TXT, DOCX, Audio, Video, etc.)")
        content_request_details["delete_source"] = st.checkbox("Delete source after processing", value=True)
        graph_input_payload["content_state"] = content_request_details
    elif source_type == "Text":
        source_text = st.text_area("Text (Paste any text content here)")
        content_request_details["content"] = source_text
        graph_input_payload["content_state"] = content_request_details
    elif source_type == "Scrape all website":
        website_url_to_scrape = st.text_input("Website Base URL (e.g., https://www.example.com)")
        max_pages_to_scrape = st.number_input("Max pages to scrape (0 for all)", min_value=0, value=10, step=1, help="Set to 0 to try and scrape all pages found in the sitemap. Large websites can take a very long time and consume many resources.")
        # For this type, scraped_documents will be populated directly later.
    elif source_type == "YouTube Link":
        youtube_url_input = st.text_input("YouTube Video URL")
        content_request_details["url"] = youtube_url_input # Use 'url' key
        content_request_details["source_type"] = "youtube_link_initial" # Temporary type for routing
        graph_input_payload["content_state"] = content_request_details

    transformations = Transformation.get_all()
    default_transformations = [t for t in transformations if t.apply_default]
    apply_transformations = st.multiselect(
        "Apply transformations",
        options=transformations,
        format_func=lambda t: t.name,
        default=default_transformations,
    )
    run_embed = st.checkbox(
        "Embed content for vector search",
        help="Creates an embedded content for vector search. Costs a little money and takes a little bit more time. You can do this later if you prefer.",
    )
    if st.button("Process", key="add_source_button"):
        logger.debug(f"Adding source of type: {source_type}")
        if not notebook_id:
            st.error("Notebook ID is missing. Cannot add source.")
            return

        with st.status("Processing...", expanded=True) as status_ui:
            try:
                if source_type == "Upload" and source_file is not None:
                    status_ui.write("Uploading file...")
                    file_name = source_file.name
                    file_extension = Path(file_name).suffix
                    base_name = Path(file_name).stem

                    new_path = os.path.join(UPLOADS_FOLDER, file_name)
                    counter = 0
                    while os.path.exists(new_path):
                        counter += 1
                        new_file_name = f"{base_name}_{counter}{file_extension}"
                        new_path = os.path.join(UPLOADS_FOLDER, new_file_name)

                    content_request_details["file_path"] = str(new_path)
                    with open(new_path, "wb") as f:
                        f.write(source_file.getbuffer())
                    status_ui.write(f"File uploaded to: {new_path}")
                    graph_input_payload["content_state"] = content_request_details
                
                elif source_type == "Scrape all website":
                    if not website_url_to_scrape:
                        st.warning("Please enter a website URL to scrape.")
                        return
                    status_ui.write(f"Starting website scrape for: {website_url_to_scrape} (max_pages: {max_pages_to_scrape or 'all'})")
                    # Run the scraper (this is an async function)
                    scraped_docs = asyncio.run(scrape_website(website_url_to_scrape, max_pages=max_pages_to_scrape))
                    if not scraped_docs:
                        st.warning(f"No documents were scraped from {website_url_to_scrape}. Please check the URL and sitemap.")
                        return
                    status_ui.write(f"Successfully scraped {len(scraped_docs)} pages. Preparing to add to notebook.")
                    graph_input_payload["scraped_documents"] = scraped_docs
                    # Ensure content_state is not present if scraped_documents is being used
                    graph_input_payload.pop("content_state", None)


                # Common parameters for the graph invocation
                graph_input_payload["notebook_id"] = notebook_id
                graph_input_payload["apply_transformations"] = apply_transformations
                graph_input_payload["embed"] = run_embed

                logger.info(f"Invoking source_graph with payload: { {k: type(v) if k=='scraped_documents' else v for k,v in graph_input_payload.items()} }")
                
                # Invoke the graph
                asyncio.run(source_graph.ainvoke(graph_input_payload))
                
                status_ui.update(label="Processing complete!", state="complete", expanded=False)
                st.toast("Source(s) added successfully!", icon="🎉")

            except UnsupportedTypeException as e:
                st.warning(
                    "This type of content is not supported yet. If you think it should be, let us know on the project Issues's page"
                )
                st.error(e)
                st.link_button(
                    "Go to Github Issues",
                    url="https://www.github.com/lfnovo/open-notebook/issues",
                )
                status_ui.update(label="Error!", state="error")
                return

            except Exception as e:
                logger.error("Error during source processing:", exc_info=True)
                st.exception(e)
                status_ui.update(label="Error!", state="error")
                return

        st.rerun()


def source_card(source, notebook_id):
    # todo: more descriptive icons
    icon = "🔗"
    if source.asset and source.asset.file_path:
        icon = "📄"
    elif source.asset and source.asset.url and "youtube.com" in source.asset.url:
        icon = "📹"
    elif not source.asset or (not source.asset.url and not source.asset.file_path):
        icon = "✍️"

    # Ensure session state structure for context_config exists
    if notebook_id not in st.session_state:
        st.session_state[notebook_id] = {}
    if "context_config" not in st.session_state[notebook_id]:
        st.session_state[notebook_id]["context_config"] = {}
    
    default_source_display_value = source_context_icons[0]  # Changed from 2 to 0 ("⛔ not in context")

    # Get the current selection for this source from session_state
    current_selection_value = st.session_state[notebook_id]["context_config"].get(source.id, default_source_display_value)
    
    try:
        current_display_index = source_context_icons.index(current_selection_value)
    except ValueError:
        current_display_index = source_context_icons.index(default_source_display_value)
        # If value was invalid, correct it in session_state and query_params
        st.session_state[notebook_id]["context_config"][source.id] = default_source_display_value
        st.query_params[f"ctx_source_{source.id}"] = default_source_display_value

    def on_source_context_change():
        new_value = st.session_state[f"source_select_{source.id}"]
        st.session_state[notebook_id]["context_config"][source.id] = new_value
        st.query_params[f"ctx_source_{source.id}"] = new_value

    with st.container(border=True):
        title = (source.title if source.title else "No Title").strip()
        st.markdown((f"{icon} **{title}**"))
        st.selectbox(
            "Context",
            label_visibility="collapsed",
            options=source_context_icons,
            index=current_display_index, 
            key=f"source_select_{source.id}", # Unique key for selectbox widget
            on_change=on_source_context_change
        )
        st.caption(
            f"Updated: {naturaltime(source.updated)}, **{len(source.insights)}** insights. Type: {source.asset.source_type if source.asset else 'text'}"
        )
        if st.button("Expand", icon="📝", key=f"expand_source_{source.id}"):
            source_panel_dialog(source.id, notebook_id)


def source_list_item(source_id, score=None):
    source: Source = Source.get(source_id)
    if not source:
        st.error("Source not found")
        return
    
    icon = "🔗"
    if source.asset and source.asset.file_path:
        icon = "📄"
    elif source.asset and source.asset.url and "youtube.com" in source.asset.url:
        icon = "📹"
    elif not source.asset or (not source.asset.url and not source.asset.file_path):
        icon = "✍️"
        
    title_display = f"{icon} "
    if score is not None:
        title_display += f"[{score:.2f}] "
    title_display += f"**{source.title or 'No Title'}** {naturaltime(source.updated)}"

    with st.expander(title_display):
        for insight in source.insights:
            st.markdown(f"**{insight.insight_type}**")
            st.write(insight.content)
        if st.button("Edit source", icon="📝", key=f"x_edit_source_{source.id}"):
            source_panel_dialog(source_id=source.id)
