import streamlit as st
from loguru import logger
from streamlit_monaco import st_monaco  # type: ignore

from open_notebook.domain.models import model_manager
from open_notebook.domain.notebook import Note
from pages.stream_app.utils import convert_source_references
from pages.stream_app.utils import extract_plain_think_block, extract_xml_think_block


def note_panel(note_id, notebook_id=None):
    if not model_manager.embedding_model:
        st.warning(
            "Since there is no embedding model selected, your note will be saved but not searchable."
        )
    note: Note = Note.get(note_id)
    if not note:
        raise ValueError(f"Note not fonud {note_id}")
    t_preview, t_edit = st.tabs(["Preview", "Edit"])
    with t_preview:
        st.subheader(note.title)
        processed_content, think_content = extract_plain_think_block(note.content or "")
        if not think_content:
            processed_content, think_content = extract_xml_think_block(note.content or "")
        st.markdown(convert_source_references(processed_content))
        if think_content:
            with st.expander("🤔 Thinking logs"):
                st.text(think_content)
    with t_edit:
        note.title = st.text_input("Title", value=note.title)
        note.content = st_monaco(
            value=note.content, height="300px", language="markdown"
        )
        b1, b2 = st.columns(2)
        if b1.button("Save", key=f"pn_edit_note_{note.id or 'new'}"):
            logger.debug("Editing note")
            note.save()
            if not note.id and notebook_id:
                note.add_to_notebook(notebook_id)
            st.rerun()
    if b2.button("Delete", type="primary", key=f"delete_note_{note.id or 'new'}"):
        logger.debug("Deleting note")
        note.delete()
        st.rerun()
