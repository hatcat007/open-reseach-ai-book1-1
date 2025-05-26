import streamlit as st
from dotenv import load_dotenv

# Call st.set_page_config() as the FIRST Streamlit command
st.set_page_config(page_title="📒 Open Notebook", layout="wide", initial_sidebar_state="collapsed")

from open_notebook.domain.base import ObjectModel
from open_notebook.exceptions import NotFoundError
from pages.components import (
    note_panel,
    source_embedding_panel,
    source_insight_panel,
    source_panel,
)
from pages.stream_app.utils import setup_page

load_dotenv()
# Pass the title to setup_page for other uses if needed, but page config is already set.
setup_page("📒 Open Notebook", sidebar_state="collapsed")

if "object_id" not in st.query_params:
    st.switch_page("pages/2_📒_Notebooks.py")
    st.stop()

object_id = st.query_params["object_id"]
try:
    obj = ObjectModel.get(object_id)
except NotFoundError:
    st.switch_page("pages/2_📒_Notebooks.py")
    st.stop()

obj_type = object_id.split(":")[0]

if obj_type == "note":
    note_panel(object_id)
elif obj_type == "source":
    source_panel(object_id)
elif obj_type == "source_insight":
    source_insight_panel(object_id)
elif obj_type == "source_embedding":
    source_embedding_panel(object_id)
