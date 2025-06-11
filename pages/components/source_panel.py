import asyncio
import streamlit as st
import streamlit_scrollable_textbox as stx  # type: ignore # Re-add this import
import streamlit_antd_components as sac
from humanize import naturaltime
from loguru import logger
import pandas as pd
from io import StringIO

from open_notebook.domain.models import model_manager
from open_notebook.domain.notebook import Source, Notebook
from open_notebook.domain.transformation import Transformation
from open_notebook.graphs.transformation import graph as transform_graph
from pages.stream_app.utils import check_models
from pages.stream_app.utils import extract_plain_think_block, extract_xml_think_block
from open_notebook.tools.download_utils import (
    source_to_txt,
    source_to_md,
    source_to_json,
    source_to_docx_bytes,
    source_to_pdf_bytes,
    transformation_to_txt,
    transformation_to_md,
    transformation_to_json,
    transformation_to_docx_bytes,
    transformation_to_pdf_bytes,
)
from open_notebook.utils import sanitize_filename
from open_notebook.utils import token_count


def source_panel(source_id: str, notebook_id=None, modal=False):
    check_models(only_mandatory=False)
    source: Source = Source.get(source_id)
    if not source:
        raise ValueError(f"Source not found: {source_id}")

    current_title = source.title if source.title else "No Title"
    source.title = st.text_input("Title", value=current_title)
    if source.title != current_title:
        st.toast("Saved new Title")
        source.save()

    process_tab, source_tab = st.tabs(["Process", "Source"])
    with process_tab:
        c1, c2 = st.columns([0.6, 0.4]) # Adjust internal columns, e.g. [2,1] or [0.6, 0.4]
        with c1:
            title = st.empty()
            if source.title:
                title.subheader(source.title)
            if source.asset and source.asset.url:
                from_src = f"from URL: {source.asset.url}"
            elif source.asset and source.asset.file_path:
                from_src = f"from file: {source.asset.file_path}"
            else:
                from_src = "from text"
            st.caption(f"Created {naturaltime(source.created)}, {from_src}")
            for insight in source.insights:
                expander_title = insight.insight_type or "Transformation Result"
                with st.expander(f"**{expander_title}**"):
                    processed_insight_content, think_insight_content = extract_plain_think_block(insight.content or "")
                    if not think_insight_content:
                        processed_insight_content, think_insight_content = extract_xml_think_block(insight.content or "")

                    st.markdown(processed_insight_content)
                    if think_insight_content:
                        st.markdown("___")
                        st.subheader("🤔 Thinking Process")
                        st.text(think_insight_content)
                    
                    b_col1, b_col2 = st.columns(2)
                    if b_col1.button(
                        "Delete", type="primary", key=f"delete_insight_{insight.id}"
                    ):
                        insight.delete()
                        st.rerun(scope="fragment" if modal else "app")
                        st.toast("Insight (Transformation result) deleted")
                    if notebook_id:
                        if b_col2.button(
                            "Save as Note", icon="📝", key=f"save_note_{insight.id}"
                        ):
                            insight.save_as_note(notebook_id)
                            st.toast("Saved as Note. Refresh the Notebook to see it.")
                    
                    st.divider()
                    st.write("**Download Result**")
                    dl_col1, dl_col2, dl_col3 = st.columns(3)
                    
                    safe_insight_title = sanitize_filename(expander_title)

                    with dl_col1:
                        st.download_button(
                            label="Download TXT",
                            data=transformation_to_txt(expander_title, insight.content or ""),
                            file_name=f"{safe_insight_title}.txt",
                            mime="text/plain",
                            key=f"download_txt_insight_{insight.id}"
                        )
                        st.download_button(
                            label="Download DOCX",
                            data=transformation_to_docx_bytes(expander_title, insight.content or ""),
                            file_name=f"{safe_insight_title}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"download_docx_insight_{insight.id}"
                        )
                    with dl_col2:
                        st.download_button(
                            label="Download MD",
                            data=transformation_to_md(expander_title, insight.content or ""),
                            file_name=f"{safe_insight_title}.md",
                            mime="text/markdown",
                            key=f"download_md_insight_{insight.id}"
                        )
                        st.download_button(
                            label="Download PDF",
                            data=transformation_to_pdf_bytes(expander_title, insight.content or ""),
                            file_name=f"{safe_insight_title}.pdf",
                            mime="application/pdf",
                            key=f"download_pdf_insight_{insight.id}"
                        )
                    with dl_col3:
                        st.download_button(
                            label="Download JSON",
                            data=transformation_to_json(expander_title, insight.content or "", original_source_id=source.id, transformation_details=None),
                            file_name=f"{safe_insight_title}.json",
                            mime="application/json",
                            key=f"download_json_insight_{insight.id}"
                        )

        with c2:
            transformations = Transformation.get_all(order_by="name asc")
            with st.container(border=True):
                st.write("**Run a transformation**")
                search_term = st.text_input("Search transformations", key=f"search_transformation_{source.id}")

                if search_term:
                    filtered_transformations = [
                        t for t in transformations if search_term.lower() in t.name.lower()
                    ]
                else:
                    filtered_transformations = transformations

                if not filtered_transformations:
                    st.warning("No transformations match your search.")
                    selected_transformation = None
                else:
                    selected_transformation = st.selectbox(
                        "Select transformation",
                        filtered_transformations,
                    key=f"transformation_{source.id}",
                    format_func=lambda x: x.name,
                        label_visibility="collapsed"
                    )
                
                if selected_transformation:
                    st.caption(selected_transformation.description)
                    if st.button("Run", key=f"run_transformation_button_{source.id}"):
                        asyncio.run(
                            transform_graph.ainvoke(
                                    input=dict(source=source, transformation=selected_transformation)
                            )
                        )
                        st.rerun(scope="fragment" if modal else "app")
                elif not filtered_transformations and transformations:
                    st.info("Clear search to see all transformations.")

            if not model_manager.embedding_model:
                help = (
                    "No embedding model found. Please, select one on the Models page."
                )
            else:
                help = "This will generate your embedding vectors on the database for powerful search capabilities"

            if source.embedded_chunks == 0 and st.button(
                "Embed vectors",
                icon="🦾",
                help=help,
                disabled=model_manager.embedding_model is None,
            ):
                source.vectorize()
                st.success("Embedding complete")

            with st.container(border=True):
                st.caption(
                    "Deleting the source will also delete all its insights and embeddings"
                )
                if st.button(
                    "Delete", type="primary", key=f"bt_delete_source_{source.id}"
                ):
                    source.delete()
                    st.rerun()

    with source_tab:
        st.subheader("Content")
        
        # --- BEGIN MODIFICATION: Attempt to display GFM table with st.dataframe ---
        raw_content = source.full_text or ""
        gfm_table_displayed = False

        # Basic check for GFM table: starts with '|' and contains a separator line an indication of GFM table
        if raw_content.strip().startswith("|") and "\\n|---" in raw_content:
            try:
                # Prepare the GFM string for pd.read_csv
                # 1. Split into lines and strip whitespace from each line
                lines = [line.strip() for line in raw_content.strip().split('\\n')]
                
                # 2. Filter out the GFM separator line (e.g., |---|---|) as read_csv expects only header and data
                # Also filter empty lines that might result from splitting
                data_lines = [line for line in lines if line and not line.replace('|', '').replace('-', '').strip() == ""]
                
                if len(data_lines) > 1: # We need at least a header and one data row
                    # Join the remaining lines back into a string
                    cleaned_gfm_for_pandas = "\\n".join(data_lines)
                    string_io_data = StringIO(cleaned_gfm_for_pandas)
                    
                    # Use read_csv with pipe delimiter.
                    # The first line of data_lines will be treated as the header.
                    df = pd.read_csv(string_io_data, sep='|', lineterminator='\\n', skipinitialspace=True)

                    # Post-processing DataFrame:
                    # 1. Drop first and last columns if they are empty (often artifacts of leading/trailing pipes)
                    if not df.empty:
                        # Check and drop the first column if it's entirely empty/whitespace or unnamed
                        first_col_name = str(df.columns[0])
                        if first_col_name.strip() == "" or "Unnamed: 0" in first_col_name:
                            if df[df.columns[0]].isnull().all() or df[df.columns[0]].astype(str).str.strip().eq('').all():
                                df = df.iloc[:, 1:]
                        
                        # Check and drop the last column if it's entirely empty/whitespace or unnamed
                        if len(df.columns) > 0: # Check if columns are left
                            last_col_name = str(df.columns[-1])
                            if last_col_name.strip() == "" or "Unnamed:" in last_col_name: # Covers "Unnamed: X"
                                if df[df.columns[-1]].isnull().all() or df[df.columns[-1]].astype(str).str.strip().eq('').all():
                                    df = df.iloc[:, :-1]
                    
                    # 2. Strip whitespace from column names
                    if not df.empty:
                        df.columns = [str(col).strip() for col in df.columns]
                    
                    # 3. Reset index if columns were dropped or for cleanliness
                    if not df.empty:
                        df.reset_index(drop=True, inplace=True)

                    if not df.empty:
                        # Convert DataFrame to Markdown string
                        markdown_output = df.to_markdown(index=False)
                        # Display with st.markdown, wrapped in a container
                        with st.container(): # Ensure it's in a container
                            st.markdown(markdown_output)
                        gfm_table_displayed = True
                    else:
                        logger.warning("Tried to parse GFM to DataFrame, but result was empty after processing. Falling back to markdown.")
                else:
                    logger.warning("Not enough data lines to form a DataFrame after filtering GFM table. Falling back to markdown.")
            except Exception as e:
                logger.warning(f"Failed to parse GFM table with pandas: {e}. Falling back to markdown. Raw content (first 500 chars):\\n{raw_content[:500]}")
        
        if not gfm_table_displayed:
            # Fallback to original markdown rendering if not a GFM table or if parsing failed
            processed_content, think_content = extract_plain_think_block(raw_content)
            if not think_content: # Try XML if plain think block not found
                processed_content, think_content = extract_xml_think_block(raw_content)
            
            st.markdown(processed_content) # Display the processed content (without think logs here)

            if think_content:
                with st.expander("🤔 Thinking logs"):
                    st.markdown(think_content) # Display think logs in an expander
        # --- END MODIFICATION ---

        st.divider()
        st.subheader("Download Source")
        col1, col2, col3 = st.columns(3)
        
        safe_title = sanitize_filename(source.title or "source")

        with col1:
            st.download_button(
                label="Download TXT",
                data=source_to_txt(source),
                file_name=f"{safe_title}.txt",
                mime="text/plain",
                key=f"download_txt_src_{source.id}"
            )
            st.download_button(
                label="Download DOCX",
                data=source_to_docx_bytes(source),
                file_name=f"{safe_title}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"download_docx_src_{source.id}"
            )
            st.download_button(
                label="Download PDF",
                data=source_to_pdf_bytes(source),
                file_name=f"{safe_title}.pdf",
                mime="application/pdf",
                key=f"download_pdf_src_{source.id}"
            )
        with col2:
            st.download_button(
                label="Download MD",
                data=source_to_md(source),
                file_name=f"{safe_title}.md",
                mime="text/markdown",
                key=f"download_md_src_{source.id}"
            )
        with col3:
            st.download_button(
                label="Download JSON",
                data=source_to_json(source),
                file_name=f"{safe_title}.json",
                mime="application/json",
                key=f"download_json_src_{source.id}"
            )

        if st.button("Delete Source", key=f"delete_source_{source.id}"):
            source.delete()
            st.rerun()
