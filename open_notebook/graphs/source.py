import operator
from typing import List, Optional

from langchain_core.runnables import (
    RunnableConfig,
)
from langchain_core.documents import Document
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from loguru import logger
from typing_extensions import Annotated, TypedDict

from open_notebook.domain.notebook import Asset, Source
from open_notebook.domain.transformation import Transformation
from open_notebook.graphs.content_processor_graph import ContentState
from open_notebook.graphs.content_processor_graph import graph as content_graph
from open_notebook.graphs.transformation import graph as transform_graph
from open_notebook.utils import surreal_clean


class SourceState(TypedDict):
    content_state: Optional[ContentState] # For single item processing before staging
    content_state_for_saving: Annotated[List[Optional[ContentState]], operator.add] # Aggregated list from parallel/single processing
    processed_content_save_index: int # Index for sequential saving from content_state_for_saving
    item_payload_for_saving: Optional[dict] # Holds content_state for the item save_source will process
    _routing_decision_for_edges: Optional[str] # Temporary key for conditional edge routing
    apply_transformations: List[Transformation]
    notebook_id: str
    source: Annotated[List[Source], operator.add] # Aggregated saved sources
    transformation: Annotated[list, operator.add]
    embed: bool
    scraped_documents: Optional[List[Document]] # Input for scraping path
    current_scraped_doc_tuple: Annotated[Optional[tuple[int, Document]], lambda _, val: val] # Temp for fanning out
    bypass_llm_filter_for_scrape: Optional[bool] = False # Added for website scraping bypass


class TransformationState(TypedDict):
    source: Source
    transformation: Transformation


async def content_process(state: SourceState) -> dict:
    content_state_val = state.get("content_state") # content_state_val to avoid conflict with state key
    if not content_state_val:
        logger.error("content_process called without content_state")
        return {}
    logger.info("Content processing started for new content (e.g. URL, Upload, Text)")
    processed_state = await content_graph.ainvoke(content_state_val)
    return {"content_state": processed_state} # Puts result back into state.content_state


def prepare_single_content_for_saving_func(state: SourceState) -> dict:
    """Prepares content_state from single source processing for the sequential saving queue."""
    single_item_content_state = state.get("content_state")
    if single_item_content_state:
        logger.info("Preparing single content item for sequential saving.")
        return {
            "content_state_for_saving": [single_item_content_state], # Put it in the list
            "content_state": None  # Clear the single item state
        }
    logger.warning("prepare_single_content_for_saving_func called without content_state.")
    return {"content_state_for_saving": []} # Ensure the list is at least empty


def initiate_sequential_save_func(state: SourceState) -> dict:
    """Initializes the index for sequentially saving items from content_state_for_saving."""
    logger.info(f"Initiating sequential save for {len(state.get('content_state_for_saving', []))} items.")
    return {"processed_content_save_index": 0}


def route_save_item_or_trigger_transformations_node_action(state: SourceState) -> dict:
    """
    Determines the next step, prepares payload if saving, and sets a routing decision string in state.
    The actual routing decision for add_conditional_edges will be read from this state.
    """
    index = state.get("processed_content_save_index", 0)
    all_staged_content = state.get("content_state_for_saving", [])
    item_payload = None
    decision_str = ""

    if index < len(all_staged_content):
        current_content_item = all_staged_content[index]
        if current_content_item:
            logger.info(f"RouterNode: Preparing item {index + 1}/{len(all_staged_content)} (index {index}) for save_source.")
            item_payload = {"content_state": current_content_item, "_current_processing_index_for_debug": index}
            decision_str = "do_save_item"
        else:
            logger.warning(f"RouterNode: Skipping None item at index {index} in content_state_for_saving.")
            decision_str = "do_skip_item" # This will go to increment
    else:
        logger.info("RouterNode: All items processed. Setting decision to evaluate transformations.")
        decision_str = "do_evaluate_transformations"
    
    return {
        "item_payload_for_saving": item_payload, # Set or clear payload for save_source
        "_routing_decision_for_edges": decision_str # This key will be read by the conditional router function
    }


def route_save_item_conditional_router(state: SourceState) -> str:
    """Reads the decision string set by route_save_item_or_trigger_transformations_node_action."""
    decision = state.get("_routing_decision_for_edges")
    if not decision:
        logger.error("Routing decision not found in state, defaulting to transformations. This is unexpected.")
        return "do_evaluate_transformations" # Fallback, though should not happen
    logger.info(f"ConditionalRouter: Routing based on decision: {decision}")
    return decision


def save_source(state: SourceState) -> dict:
    payload = state.get("item_payload_for_saving")
    if not payload or not payload.get("content_state"):
        logger.warning("save_source called without valid payload in item_payload_for_saving. Skipping.")
        # Ensure item_payload_for_saving is cleared if it was somehow non-None but invalid
        return {"source": [], "item_payload_for_saving": None}

    current_item_content_state = payload["content_state"]
    notebook_id = state.get("notebook_id")
    embed_flag = state.get("embed")
    processing_error = current_item_content_state.get("error")
    bypass_filter_flag = current_item_content_state.get("bypass_llm_filter", False) # Get the flag

    # --- BEGIN DEBUG LOG ---
    raw_content_before_clean = current_item_content_state.get("content", "")
    logger.info(f"SAVE_SOURCE_NODE: Raw content before surreal_clean and Source object creation:\n{raw_content_before_clean}")
    # --- END DEBUG LOG ---

    if not current_item_content_state.get("content") and not processing_error: # Condition updated
        logger.warning(f"save_source: item has no content and no processing error. Skipping.")
        return {"source": [], "item_payload_for_saving": None}

    source_title = current_item_content_state.get("title") or "Untitled Source"
    source_asset_type = current_item_content_state.get("identified_type")

    source_url = current_item_content_state.get("url")
    source_file_path = current_item_content_state.get("file_path")

    cleaned_content_for_db = surreal_clean(current_item_content_state["content"] or "")
    cleaned_title_for_db = surreal_clean(source_title)

    # --- BEGIN DEBUG LOG ---
    logger.info(f"SAVE_SOURCE_NODE: Content AFTER surreal_clean, before Source object save:\n{cleaned_content_for_db}")
    # --- END DEBUG LOG ---

    source_obj = Source( # Renamed to source_obj to avoid conflict with state key
        asset=Asset(
            url=source_url,
            file_path=source_file_path,
            source_type=source_asset_type
        ),
        full_text=cleaned_content_for_db, # Use the cleaned content
        title=cleaned_title_for_db, # Use the cleaned title
        bypass_llm_filter=bypass_filter_flag  # Set the bypass flag on the Source object
    )
    source_obj.save()
    logger.info(f"Successfully SAVED source: {source_obj.id} - {source_obj.title}, Bypass Filter: {bypass_filter_flag}")

    if notebook_id:
        logger.debug(f"Adding source {source_obj.id} to notebook {notebook_id}")
        source_obj.add_to_notebook(notebook_id)

    if embed_flag:
        logger.debug(f"Embedding content for source {source_obj.id} for vector search")
        source_obj.vectorize()

    # save_source no longer updates/returns processed_content_save_index. Router manages it.
    return {
        "source": [source_obj],
        "content_state": None,  # Clear the single item processing slot if it was ever used (legacy)
        "item_payload_for_saving": None # IMPORTANT: Clear payload after use
    }


def increment_index_and_loop_func(state: SourceState) -> dict:
    """Increments the save index and prepares to loop back to the router."""
    current_index = state.get("processed_content_save_index", 0)
    next_index = current_index + 1
    logger.info(f"Incrementing save index from {current_index} to {next_index}.")
    return {
        "processed_content_save_index": next_index,
        "item_payload_for_saving": None # Ensure payload is cleared if skipping
    }


def trigger_transformations(state: SourceState, config: RunnableConfig) -> List[Send]:
    sources_list = state.get("source", []) # Renamed to avoid conflict
    apply_transformations_list = state.get("apply_transformations") # Renamed

    if not sources_list or not apply_transformations_list or len(apply_transformations_list) == 0:
        logger.info("No sources or no transformations to apply. Ending transformation path.")
        return [] # Empty list of Sends will lead to END if that's the only option

    sends = []
    for source_item in sources_list:
        logger.debug(f"Queueing {len(apply_transformations_list)} transformations for source {source_item.id}")
        for t in apply_transformations_list:
            sends.append(
        Send(
            "transform_content",
            {
                        "source": source_item,
                "transformation": t,
            },
        )
            )
    return sends


async def transform_content(state: TransformationState) -> Optional[dict]:
    source_obj = state["source"] # Renamed
    transformation_obj = state["transformation"] # Renamed

    content = source_obj.full_text
    if not content:
        logger.warning(f"No content in source {source_obj.id} for transformation {transformation_obj.name}")
        return None # Or {}

    logger.debug(f"Applying transformation {transformation_obj.name} to source {source_obj.id}")
    result = await transform_graph.ainvoke(
        dict(input_text=content, transformation=transformation_obj)
    )
    source_obj.add_insight(transformation_obj.title, surreal_clean(result["output"]))
    return { # Must return a dict to update state (even if empty for this node)
    }


def route_source_input(state: SourceState) -> str:
    if state.get("scraped_documents") and len(state.get("scraped_documents", [])) > 0:
        logger.info("Routing to scraped documents processing path.")
        return "initiate_scrape_processing_branch"
    elif state.get("content_state"):
        logger.info("Routing to single content processing path.")
        return "content_process_path" # Changed branch name for clarity
    else:
        logger.error("No valid input found (scraped_documents or content_state). Ending.")
        return END


def initiate_scrape_processing(state: SourceState) -> dict:
    """Node to bridge conditional routing to fan-out for scraped documents."""
    logger.info("Initiating processing for scraped documents.")
    return {}


def fan_out_scraped_documents(state: SourceState, config: RunnableConfig) -> List[Send]:
    scraped_docs = state.get("scraped_documents", [])
    sends = []
    if not scraped_docs:
        logger.warning("fan_out_scraped_documents called with no documents.")
        return [] # Will go to END if this is the only path from initiate_scrape_processing

    logger.info(f"Fanning out {len(scraped_docs)} scraped documents for content extraction.")
    for index, doc in enumerate(scraped_docs):
        sends.append(
            Send(
                "process_scraped_document_item",
                {
                    # Pass minimal, specific payload. notebook_id etc. are in global state.
                    "current_scraped_doc_tuple": (index, doc),
                    # Clear other potentially conflicting keys from payload for this branch
                    "scraped_documents": None, 
                    "source": None,
                    "transformation": [],
                    "content_state_for_saving": [],
                },
            )
        )
    return sends


def process_scraped_document_item(state: SourceState) -> dict:
    doc_tuple = state.get("current_scraped_doc_tuple")
    global_bypass_llm_filter_for_scrape = state.get("bypass_llm_filter_for_scrape", False) # Get global flag

    if not doc_tuple:
        logger.error("process_scraped_document_item called without current_scraped_doc_tuple")
        return {"content_state_for_saving": []} # Return empty list for aggregation
    
    index, doc = doc_tuple
    page_url = doc.metadata.get("source")
    page_title = doc.metadata.get("title")
    page_content = doc.page_content

    logger.info(f"Processing scraped document (Index: {index}): {page_url}, Title: {page_title}, Bypass: {global_bypass_llm_filter_for_scrape}")

    # Construct a ContentState-like dictionary for this item
    # This will be aggregated by aggregate_scraped_item_for_saving
    content_state_item_for_aggregation: ContentState = {
        "url": page_url,
        "title": page_title or page_url, # Fallback title
        "content": page_content,
        "source_type": "webpage", # All scraped docs are webpages
        "identified_type": "html_content",
        "bypass_llm_filter": global_bypass_llm_filter_for_scrape, # Pass the flag
        "error": None, # Assume success from scrape_website for now
        "file_path": None,
        "identified_provider": None,
        "metadata": {"original_url": page_url, "scraped_doc_index": index},
        "delete_source": None # Not applicable for scraped docs
    }
    
    # This node returns a list to be aggregated by the next node
    # The operator.add on content_state_for_saving handles the aggregation
    return {"content_state_for_saving": [content_state_item_for_aggregation]}


workflow = StateGraph(SourceState)

# Existing and new nodes
workflow.add_node("content_process", content_process)
workflow.add_node("prepare_single_content_for_saving", prepare_single_content_for_saving_func)
workflow.add_node("initiate_scrape_processing", initiate_scrape_processing)
workflow.add_node("fan_out_scraped_documents", fan_out_scraped_documents)
workflow.add_node("process_scraped_document_item", process_scraped_document_item)
workflow.add_node("initiate_sequential_save", initiate_sequential_save_func)
workflow.add_node("route_save_or_transform_decision", route_save_item_or_trigger_transformations_node_action)
workflow.add_node("save_source", save_source)
workflow.add_node("increment_index_and_loop", increment_index_and_loop_func)
workflow.add_node("trigger_transformations_router_entry", lambda state: {}) # Dummy node
workflow.add_node("transform_content", transform_content)


# Entry routing
workflow.add_conditional_edges(
    START,
    route_source_input,
    {
        "initiate_scrape_processing_branch": "initiate_scrape_processing",
        "content_process_path": "content_process", # Connects to single item processing
        END: END
    }
)

# Path for single content items (URL, upload, text)
workflow.add_edge("content_process", "prepare_single_content_for_saving")
workflow.add_edge("prepare_single_content_for_saving", "initiate_sequential_save")

# Path for scraped documents
workflow.add_conditional_edges(
    "initiate_scrape_processing",
    fan_out_scraped_documents, # Router function
    { # Target nodes for Send directives from fan_out_scraped_documents
        "process_scraped_document_item": "process_scraped_document_item",
        END: END # If fan_out returns empty list
    }
)
# After all process_scraped_document_item branches complete and content_state_for_saving is aggregated
workflow.add_edge("process_scraped_document_item", "initiate_sequential_save")


# Sequential saving loop
workflow.add_edge("initiate_sequential_save", "route_save_or_transform_decision")

workflow.add_conditional_edges(
    "route_save_or_transform_decision",
    route_save_item_conditional_router,  # Simple function that reads 'next_routing_decision'
    {
        "do_save_item": "save_source",
        "do_skip_item": "increment_index_and_loop",
        "do_evaluate_transformations": "trigger_transformations_router_entry",
    }
)
# save_source and increment_index_and_loop both lead back to the router decision
workflow.add_edge("save_source", "increment_index_and_loop") 
workflow.add_edge("increment_index_and_loop", "route_save_or_transform_decision")

# Transformations path (triggered after all saving is done)
workflow.add_conditional_edges(
    "trigger_transformations_router_entry", # From the dummy node
    trigger_transformations, # Existing router function for transformations
    { # Target nodes for Send directives from trigger_transformations
        "transform_content": "transform_content",
        END: END # If trigger_transformations returns empty list
    }
)

workflow.add_edge("transform_content", END) # End after individual transformation

source_graph = workflow.compile()

try:
    source_graph.get_graph().print_ascii()
except Exception as e:
    logger.error(f"Error generating graph ASCII: {e}")
