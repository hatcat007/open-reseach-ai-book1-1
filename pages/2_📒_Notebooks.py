import streamlit as st
from humanize import naturaltime

from open_notebook.domain.notebook import Notebook
from pages.stream_app.chat import chat_sidebar
from pages.stream_app.note import add_note, note_card
from pages.stream_app.source import add_source, source_card
from pages.stream_app.utils import setup_page, setup_stream_state

setup_page("📒 Open Notebook", only_check_mandatory_models=True)


def notebook_header(current_notebook: Notebook):
    """
    Defines the header of the notebook page, including the ability to edit the notebook's name and description.
    """
    c1, c2, c3 = st.columns([8, 2, 2])
    c1.header(current_notebook.name)
    if c2.button("Back to the list", icon="🔙"):
        st.session_state["current_notebook_id"] = None
        st.rerun()

    if c3.button("Refresh", icon="🔄"):
        st.rerun()
    current_description = current_notebook.description
    with st.expander(
        current_notebook.description
        if len(current_description) > 0
        else "click to add a description"
    ):
        notebook_name = st.text_input("Name", value=current_notebook.name)
        notebook_description = st.text_area(
            "Description",
            value=current_description,
            placeholder="Spill the beans! What's this notebook's grand purpose? The more context you give the AI, the smarter its insights (and the less it has to guess... it hates guessing).",
        )
        if st.button("Save Changes", icon="💾", key="edit_notebook_save_button"):
            current_notebook.name = notebook_name
            current_notebook.description = notebook_description
            current_notebook.save()
            st.rerun()

    # New columns for Archive and Delete buttons, placed outside the expander
    action_col1, action_col2, _ = st.columns([2,2,8]) # Adjust ratios as needed, leaving space
    with action_col1:
        if not current_notebook.archived:
            if st.button("Archive Notebook", icon="🗃️", use_container_width=True):
                current_notebook.archived = True
                current_notebook.save()
                st.toast("Notebook archived", icon="🗃️")
                st.rerun() # Rerun to reflect archived state potentially on different page view
        else:
            if st.button("Unarchive Notebook", icon="🗃️", use_container_width=True):
                current_notebook.archived = False
                current_notebook.save()
                st.toast("Notebook unarchived", icon="🗃️")
                st.rerun()
    
    with action_col2:
        if st.button("Delete Forever", type="primary", icon="☠️", use_container_width=True):
            # Consider adding a confirmation dialog here for destructive actions
            current_notebook.delete()
            st.session_state["current_notebook_id"] = None
            st.rerun()


def notebook_page(current_notebook: Notebook):
    # Guarantees that we have an entry for this notebook in the session state
    if current_notebook.id not in st.session_state:
        st.session_state[current_notebook.id] = {"notebook": current_notebook}

    # sets up the active session
    current_session = setup_stream_state(
        current_notebook=current_notebook,
    )

    sources = current_notebook.sources
    notes = current_notebook.notes

    notebook_header(current_notebook)

    # New Full-Width Layout
    st.subheader("💬 Chat")
    chat_sidebar(current_notebook=current_notebook, current_session=current_session)

    st.divider()

    st.subheader("📚 Sources")
    with st.container(border=True):
        if st.button("Add Source", icon="➕"):
            add_source(current_notebook.id)
        if not sources:
            st.info("No sources here yet. Time to add some knowledge!", icon="💡")
        for source in sources:
            source_card(source=source, notebook_id=current_notebook.id)

    st.divider()

    st.subheader("📝 Notes")
    with st.container(border=True):
        if st.button("Write a Note", icon="📝"):
            add_note(current_notebook.id)
        if not notes:
            st.info("This notebook is looking a bit empty. Jot down some notes!", icon="✍️")
        for note in notes:
            note_card(note=note, notebook_id=current_notebook.id)


def notebook_list_item(notebook):
    with st.container(border=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.subheader(notebook.name)
            st.caption(
                f"Created: {naturaltime(notebook.created)}, updated: {naturaltime(notebook.updated)}"
            )
            st.write(notebook.description or "This notebook is currently a mysterious enigma... 🤫 Add a description to spill its secrets!")
        with col2:
            if st.button("Open", key=f"open_notebook_{notebook.id}", use_container_width=True):
                st.session_state["current_notebook_id"] = notebook.id
                st.rerun()


if "current_notebook_id" not in st.session_state:
    st.session_state["current_notebook_id"] = None

# todo: get the notebook, check if it exists and if it's archived
if st.session_state["current_notebook_id"]:
    current_notebook: Notebook = Notebook.get(st.session_state["current_notebook_id"])
    if not current_notebook:
        st.error("Notebook not found")
        st.stop()
    notebook_page(current_notebook)
    st.stop()

st.title("📒 My Notebooks")
st.caption(
    "Behold! Your digital brain extension. Notebooks: where brilliant ideas (and random shower thoughts) find a home. Dive in or create a new one – your future self will thank you (probably)."
)

with st.expander("✨ Conjure a New Notebook"):
    new_notebook_title = st.text_input("New Notebook Name")
    new_notebook_description = st.text_area(
        "Description",
        placeholder="What's this notebook all about? Spill the beans! Is it for world domination plans, secret cookie recipes, or just your brilliant musings? The AI is curious (and a bit nosey).",
    )
    if st.button("Create a new Notebook", icon="➕"):
        notebook = Notebook(
            name=new_notebook_title, description=new_notebook_description
        )
        notebook.save()
        st.toast("Notebook created successfully", icon="📒")

notebooks = Notebook.get_all(order_by="updated desc")
archived_notebooks = [nb for nb in notebooks if nb.archived]

for notebook in notebooks:
    if notebook.archived:
        continue
    notebook_list_item(notebook)

if len(archived_notebooks) > 0:
    with st.expander(f"🗃️ The Vault of Past Glories ({len(archived_notebooks)} archived)"):
        st.write("📜 Old tales and forgotten lore slumber here, but they're not forgotten! You can still unarchive them or include them in your grand searches.")
        for notebook in archived_notebooks:
            notebook_list_item(notebook)
