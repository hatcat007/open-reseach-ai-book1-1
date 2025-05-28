import streamlit as st
from streamlit_agraph import Node, Edge, Config, agraph # Ensure agraph and Config are imported
from open_notebook.domain.notebook import Notebook, Source, Note, SourceInsight
# from open_notebook.database.repository import NotFoundError # Removed this import

st.set_page_config(page_title="Notebook Graph", layout="wide", initial_sidebar_state="collapsed")

st.title("🔗 Notebook Connection Graph")

def display_notebook_graph(notebook_id: str):
    nodes = []
    edges = []
    current_notebook = None # Initialize to handle case where notebook is not found early

    current_notebook = Notebook.get(notebook_id)
    if not current_notebook:
        st.error(f"Notebook with ID '{notebook_id}' not found.")
        return # Exit if notebook not found

    # Notebook Node
    nodes.append(Node(id=current_notebook.id,
                      label=current_notebook.name or f"Notebook ({current_notebook.id.split(':')[-1][:6]})",
                      size=30, shape="hexagon", color="#007bff")) # Modern Blue

    # Sources and their Insights
    if current_notebook.sources:
        for source in current_notebook.sources:
            nodes.append(Node(id=source.id,
                              label=source.title or f"Source ({source.id.split(':')[-1][:6]})",
                              size=20, shape="box", color="#6c757d")) # Muted Grey
            edges.append(Edge(source=current_notebook.id, target=source.id))

            if source.insights:
                for insight in source.insights:
                    nodes.append(Node(id=insight.id,
                                      label=insight.insight_type or f"Insight ({insight.id.split(':')[-1][:6]})",
                                      size=15, shape="diamond", color="#17a2b8")) # Teal/Cyan
                    edges.append(Edge(source=source.id, target=insight.id))

    # Notes and their link to Insights (if any)
    if current_notebook.notes:
        for note in current_notebook.notes:
            note_label = note.title or f"Note ({note.id.split(':')[-1][:6]})"
            if len(note_label) > 30:
                note_label = note_label[:27] + "..."
            nodes.append(Node(id=note.id,
                              label=note_label,
                              size=20, shape="ellipse", color="#2ca02c")) # Keep Green
            edges.append(Edge(source=current_notebook.id, target=note.id))

    if len(nodes) <= 1 and not edges: # Only the notebook node itself, or notebook not found properly handled
        if current_notebook: # Check if notebook was actually found
             st.info(f"Notebook '{current_notebook.name or notebook_id}' has no connected items (sources, notes) to graph yet.")
        # If current_notebook is None, error was already shown
        return

    # Define graph configuration
    config = Config(width=900,  # Increased width
                    height=700, # Increased height 
                    directed=True, 
                    physics=True, # Simplest way to enable physics with defaults
                    # physics={  # Temporarily commenting out detailed physics 
                    #     'enabled': True,
                    #     'barnesHut': {
                    #         'gravitationalConstant': -30000,
                    #         'centralGravity': 0.1, 
                    #         'springLength': 200,
                    #         'springConstant': 0.05,
                    #         'damping': 0.09,
                    #         'avoidOverlap': 0.5
                    #     },
                    #     'minVelocity': 0.75
                    # }, 
                    hierarchical=False,
                    nodes={}, 
                    groups={}, # Explicitly provide an empty object for groups
                    interaction={ 
                        'hover': True, 
                        'hoverConnectedEdges': True,
                        'tooltipDelay': 300
                    }
                    )
    
    # Display the graph
    agraph(nodes=nodes, edges=edges, config=config)


# Main page logic - Updated to prioritize session_state for navigation
notebook_id_to_display = None

if "graph_view_target_notebook_id" in st.session_state:
    notebook_id_to_display = st.session_state.pop("graph_view_target_notebook_id")
elif st.query_params.get("notebook_id"):
    notebook_id_to_display = st.query_params.get("notebook_id")

if notebook_id_to_display:
    display_notebook_graph(notebook_id_to_display)
else:
    st.info("Please provide a 'notebook_id' in the query parameters or navigate from a notebook page to display its graph.")


# Keep the import check at the end as a fallback, though it should be fine.
# If agraph() above fails due to import, this won't be reached, but it's harmless.
try:
    pass # streamlit_agraph components already imported at the top
except ImportError:
    st.error("streamlit-agraph is not installed. Please add it to requirements.txt and install.") 