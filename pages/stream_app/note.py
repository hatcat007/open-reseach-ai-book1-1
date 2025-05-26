from typing import Optional

import streamlit as st
from humanize import naturaltime

from open_notebook.domain.models import model_manager
from open_notebook.domain.notebook import Note
from open_notebook.graphs.prompt import graph as prompt_graph
from open_notebook.utils import surreal_clean
from pages.components import note_panel

from .consts import note_context_icons
from .utils import extract_plain_think_block, extract_xml_think_block


@st.dialog("Write a Note", width="large")
def add_note(notebook_id):
    if not model_manager.embedding_model:
        st.warning(
            "Since there is no embedding model selected, your note will be saved but not searchable."
        )
    note_title = st.text_input("Title")
    note_content = st.text_area("Content")
    if st.button("Save", key="add_note"):
        note = Note(title=note_title, content=note_content, note_type="human")
        note.save()
        note.add_to_notebook(notebook_id)
        st.rerun()


@st.dialog("Add a Note", width="large")
def note_panel_dialog(note: Optional[Note] = None, notebook_id=None):
    note_panel(note_id=note.id, notebook_id=notebook_id)


def make_note_from_chat(content, notebook_id=None):
    # todo: make this more efficient
    prompt = "Based on the Note below, please provide a Title for this content, with max 15 words"
    output = prompt_graph.invoke(dict(input_text=content, prompt=prompt))
    title = surreal_clean(output["output"])

    note = Note(
        title=title,
        content=content,
        note_type="ai",
    )
    note.save()
    if notebook_id:
        note.add_to_notebook(notebook_id)

    st.rerun()


def note_card(note, notebook_id):
    if note.note_type == "human":
        icon = "🤵"
    else:
        icon = "🤖"

    # Ensure session state structure for context_config exists
    if notebook_id not in st.session_state:
        st.session_state[notebook_id] = {}
    if "context_config" not in st.session_state[notebook_id]:
        st.session_state[notebook_id]["context_config"] = {}

    default_note_display_value = note_context_icons[1]  # Changed from 0 to 1 ("🟢 full content")

    # Get the current selection for this note from session_state, which should be populated from query_params on page load
    current_selection_value = st.session_state[notebook_id]["context_config"].get(note.id, default_note_display_value)
    
    try:
        current_display_index = note_context_icons.index(current_selection_value)
    except ValueError:
        current_display_index = note_context_icons.index(default_note_display_value)
        # If value was invalid, correct it in session_state and query_params
        st.session_state[notebook_id]["context_config"][note.id] = default_note_display_value
        st.query_params[f"ctx_note_{note.id}"] = default_note_display_value

    def on_note_context_change():
        new_value = st.session_state[f"note_select_{note.id}"]
        st.session_state[notebook_id]["context_config"][note.id] = new_value
        st.query_params[f"ctx_note_{note.id}"] = new_value
        # No st.rerun() needed here as st.query_params change triggers it.

    with st.container(border=True):
        st.markdown((f"{icon} **{note.title if note.title else 'No Title'}**"))
        st.selectbox(
            "Context",
            label_visibility="collapsed",
            options=note_context_icons,
            index=current_display_index,
            key=f"note_select_{note.id}", # Unique key for selectbox widget
            on_change=on_note_context_change
        )
        st.caption(f"Updated: {naturaltime(note.updated)}")

        if st.button("Expand", icon="📝", key=f"edit_note_{note.id}"):
            note_panel_dialog(notebook_id=notebook_id, note=note)


def note_list_item(note_id, score=None):
    note: Note = Note.get(note_id)
    if note.note_type == "human":
        icon = "🤵"
    else:
        icon = "🤖"

    with st.expander(
        f"{icon} [{score:.2f}] **{note.title}** {naturaltime(note.updated)}"
    ):
        # Try plain think block first
        processed_content, think_content = extract_plain_think_block(note.content or "")
        if not think_content: # If plain block not found, try XML style
            processed_content, think_content = extract_xml_think_block(note.content or "")
        st.markdown(processed_content)
        if think_content:
            with st.expander("🤔 Thinking logs"):
                st.text(think_content)

        if st.button("Edit Note", icon="📝", key=f"x_edit_note_{note.id}"):
            note_panel_dialog(note=note)
