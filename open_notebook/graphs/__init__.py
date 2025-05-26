from . import content_processor_graph
import os

# Get the absolute path of content_processor_graph.py
content_processor_graph_path = os.path.abspath(content_processor_graph.__file__)

print(f"--- IMPORTING content_processor_graph from: {content_processor_graph_path} ---")

# You can also re-export things if needed, e.g.:
# from .source import source_graph
# from .content_processor_graph import graph as content_graph # Example of re-exporting the actual graph 