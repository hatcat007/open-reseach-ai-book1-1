import streamlit as st
from humanize import naturaltime

from open_notebook.domain.notebook import Notebook, Task
from pages.stream_app.chat import chat_sidebar
from pages.stream_app.note import add_note, note_card
from pages.stream_app.source import add_source, source_card
from pages.stream_app.utils import setup_page, setup_stream_state
from pages.stream_app.consts import note_context_icons, source_context_icons

setup_page("📒 Open Notebook")

def notebook_header(current_notebook: Notebook):
    # This is the ORIGINAL notebook_header function.
    c1, c2, c3 = st.columns([8, 2, 2])
    c1.header(current_notebook.name)
    if c2.button("Back to the list", icon="🔙"):
        st.session_state["current_notebook_id"] = None
        if "notebook_id" in st.query_params:
            del st.query_params["notebook_id"]
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

    action_col1, action_col2, _ = st.columns([2,2,8])
    with action_col1:
        if not current_notebook.archived:
            if st.button("Archive Notebook", icon="🗃️", use_container_width=True):
                current_notebook.archived = True
                current_notebook.save()
                st.toast("Notebook archived", icon="🗃️")
                st.rerun()
        else:
            if st.button("Unarchive Notebook", icon="🗃️", use_container_width=True):
                current_notebook.archived = False
                current_notebook.save()
                st.toast("Notebook unarchived", icon="🗃️")
                st.rerun()
    
    with action_col2:
        if st.button("Delete Forever", type="primary", icon="☠️", use_container_width=True):
            current_notebook.delete()
            st.session_state["current_notebook_id"] = None
            st.rerun()

def notebook_page(current_notebook: Notebook):
    if current_notebook.id not in st.session_state:
        st.session_state[current_notebook.id] = {"notebook": current_notebook}

    current_session = setup_stream_state(current_notebook=current_notebook)
    
    notebook_header(current_notebook)

    st.subheader("💬 Chat")
    chat_sidebar(current_notebook=current_notebook, current_session=current_session)
    st.divider()

    st.subheader("📚 Sources")
    with st.container(border=True):
        if st.button("Add Source", icon="➕"):
            add_source(current_notebook.id)
        sources = current_notebook.sources
        if not sources:
            st.info("No sources here yet. Time to add some knowledge!", icon="💡")
        for source in sources:
            source_card(source=source, notebook_id=current_notebook.id)
    st.divider()

    st.subheader("📝 Notes")
    with st.container(border=True):
        if st.button("Write a Note", icon="📝"):
            add_note(current_notebook.id)
        notes = current_notebook.notes
        if not notes:
            st.info("This notebook is looking a bit empty. Jot down some notes!", icon="✍️")
        for note in notes:
            note_card(note=note, notebook_id=current_notebook.id)
    st.divider()

    st.subheader("✅ Tasks")
    tasks = current_notebook.tasks

    with st.container(border=True):
        new_task_description = st.text_input(
            "New Task Description",
            key=f"new_task_nb_{current_notebook.id}",
            placeholder="What needs to be done?"
        )
        if st.button("Add Task", icon="➕", key=f"add_task_btn_nb_{current_notebook.id}"):
            if new_task_description:
                task = Task(notebook=current_notebook.id, description=new_task_description, status="todo")
                task.save()
                st.rerun() 
            else:
                st.warning("Task description cannot be empty.")

        if not tasks:
            st.info("No tasks yet. Add some to get started!", icon="💡")
        else:
            for i, task_item in enumerate(tasks):
                task_key_prefix = f"task_{task_item.id}_{current_notebook.id}"

                cols = st.columns([0.2, 0.5, 0.15, 0.15]) 

                with cols[0]: 
                    task_status_map = {"todo": "⚪️ Todo", "in_progress": "🟡 In Progress", "completed": "🟢 Completed"}
                    task_status_cycle = {"todo": "in_progress", "in_progress": "completed", "completed": "todo"}
                    current_status_display = task_status_map.get(task_item.status, task_item.status.capitalize())
                    if st.button(current_status_display, key=f"{task_key_prefix}_status_btn", help="Click to change status", use_container_width=True):
                        task_item.status = task_status_cycle.get(task_item.status, "todo")
                        task_item.save()
                        st.rerun()

                with cols[1]: 
                    if st.session_state.get(f"{task_key_prefix}_editing", False):
                        edited_description = st.text_input(
                            "Edit description",
                            value=task_item.description,
                            key=f"{task_key_prefix}_edit_input",
                            label_visibility="collapsed"
                        )
                        if st.button("Save", key=f"{task_key_prefix}_save_edit_btn"):
                            if edited_description:
                                task_item.description = edited_description
                                task_item.save()
                                st.session_state[f"{task_key_prefix}_editing"] = False
                                st.rerun()
                            else:
                                st.warning("Task description cannot be empty when editing.")
                    else:
                        st.markdown(f"**{task_item.description}**")
                        details = []
                        if task_item.created:
                            details.append(f"Created: {naturaltime(task_item.created)}")
                        if task_item.due_date:
                            # Assuming due_date is a date object or string that can be directly displayed
                            details.append(f"Due: {task_item.due_date.strftime('%Y-%m-%d') if hasattr(task_item.due_date, 'strftime') else task_item.due_date}")
                        if details:
                            st.caption(", ".join(details))

                with cols[2]: 
                    if not st.session_state.get(f"{task_key_prefix}_editing", False):
                        if st.button("Edit", key=f"{task_key_prefix}_edit_btn", use_container_width=True):
                            st.session_state[f"{task_key_prefix}_editing"] = True
                            st.rerun()
                    else: 
                        if st.button("Cancel", key=f"{task_key_prefix}_cancel_edit_btn", use_container_width=True):
                            st.session_state[f"{task_key_prefix}_editing"] = False
                            st.rerun()

                with cols[3]: 
                    if st.button("Delete", type="secondary", key=f"{task_key_prefix}_delete_btn", use_container_width=True):
                        task_item.delete()
                        st.rerun()
                
                if i < len(tasks) - 1:
                     st.divider()
    st.divider()

def notebook_list_item(notebook):
    # This is the ORIGINAL notebook_list_item, restored.
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
                st.query_params["notebook_id"] = notebook.id

if "current_notebook_id" not in st.session_state:
    st.session_state["current_notebook_id"] = None

# Try to load current_notebook_id from query_params if not already set or if it's None
if not st.session_state.get("current_notebook_id"):
    query_notebook_id = st.query_params.get("notebook_id")
    if query_notebook_id:
        st.session_state["current_notebook_id"] = str(query_notebook_id) # Ensure it's a string if needed

if st.session_state["current_notebook_id"]:
    try:
        current_notebook: Notebook = Notebook.get(st.session_state["current_notebook_id"])
        if not current_notebook:
            st.error(f"Notebook with ID {st.session_state['current_notebook_id']} not found.")
            st.session_state["current_notebook_id"] = None
            if "notebook_id" in st.query_params: del st.query_params["notebook_id"] # Clear invalid query param
            if st.button("Back to list (after not found)"): st.rerun()
        else:
            # Initialize context_config for this notebook if it doesn't exist
            if st.session_state["current_notebook_id"] not in st.session_state:
                st.session_state[st.session_state["current_notebook_id"]] = {}
            if "context_config" not in st.session_state[st.session_state["current_notebook_id"]]:
                st.session_state[st.session_state["current_notebook_id"]]["context_config"] = {}
            
            # Load context from query_params
            for key, value in st.query_params.items():
                if key.startswith("ctx_note_"):
                    note_id_from_param = key.split("ctx_note_")[-1]
                    if value in note_context_icons: # Validate against possible values
                        st.session_state[st.session_state["current_notebook_id"]]["context_config"][note_id_from_param] = str(value)
                elif key.startswith("ctx_source_"):
                    source_id_from_param = key.split("ctx_source_")[-1]
                    if value in source_context_icons: # Validate against possible values
                        st.session_state[st.session_state["current_notebook_id"]]["context_config"][source_id_from_param] = str(value)
            
            notebook_page(current_notebook)
    except Exception as e:
        st.error(f"Error getting notebook {st.session_state['current_notebook_id']}: {e}")
        st.session_state["current_notebook_id"] = None
        if st.button("Back to list (after error)"): st.rerun()
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

try:
    notebooks = Notebook.get_all(order_by="updated desc")
    archived_notebooks = [nb for nb in notebooks if nb.archived]

    non_archived_notebooks = [nb for nb in notebooks if not nb.archived]
    if not non_archived_notebooks:
        st.info("No active notebooks. Create one above or unarchive from below!")

    for notebook_item in non_archived_notebooks:
        notebook_list_item(notebook_item)
    
    if len(archived_notebooks) > 0:
        with st.expander(f"🗃️ The Vault of Past Glories ({len(archived_notebooks)} archived)"):
            st.write("📜 Old tales and forgotten lore slumber here, but they're not forgotten! You can still unarchive them or include them in your grand searches.")
            for notebook_item in archived_notebooks:
                notebook_list_item(notebook_item)

except Exception as e:
    st.error(f"Error fetching notebooks: {e}. Can't display notebook list.")

st.page_link("app_home.py", label="Go to Home Page")
