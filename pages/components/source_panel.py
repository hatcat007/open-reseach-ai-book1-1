import asyncio

import streamlit as st
import streamlit_scrollable_textbox as stx  # type: ignore
from humanize import naturaltime

from open_notebook.domain.models import model_manager
from open_notebook.domain.notebook import Source
from open_notebook.domain.transformation import Transformation
from open_notebook.graphs.transformation import graph as transform_graph
from pages.stream_app.utils import check_models
from pages.stream_app.utils import extract_plain_think_block, extract_xml_think_block


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
                with st.expander(f"**{insight.insight_type}**"):
                    processed_insight_content, think_insight_content = extract_plain_think_block(insight.content or "")
                    if not think_insight_content:
                        processed_insight_content, think_insight_content = extract_xml_think_block(insight.content or "")

                    st.markdown(processed_insight_content)
                    if think_insight_content:
                        st.markdown("___")
                        st.subheader("🤔 Thinking Process")
                        st.text(think_insight_content)
                    
                    x1, x2 = st.columns(2)
                    if x1.button(
                        "Delete", type="primary", key=f"delete_insight_{insight.id}"
                    ):
                        insight.delete()
                        st.rerun(scope="fragment" if modal else "app")
                        st.toast("Source deleted")
                    if notebook_id:
                        if x2.button(
                            "Save as Note", icon="📝", key=f"save_note_{insight.id}"
                        ):
                            insight.save_as_note(notebook_id)
                            st.toast("Saved as Note. Refresh the Notebook to see it.")

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
        processed_content, think_content = extract_plain_think_block(source.full_text or "")
        if not think_content:
            processed_content, think_content = extract_xml_think_block(source.full_text or "")
        
        stx.scrollableTextbox(processed_content, height=300)

        if think_content:
            with st.expander("🤔 Thinking logs"):
                st.text(think_content)
