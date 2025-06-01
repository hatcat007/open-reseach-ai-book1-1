import streamlit as st

from open_notebook.domain.transformation import DefaultPrompts, Transformation
from open_notebook.domain.notebook import Notebook, Source, Note
from open_notebook.graphs.transformation import graph as transformation_graph
from open_notebook.utils import token_count
from openai import OpenAIError
from pages.components.model_selector import model_selector
from pages.stream_app.utils import setup_page

setup_page("🧩 Transformations")

# Ensure transformations are loaded into session state
if "transformations" not in st.session_state:
    st.session_state.transformations = Transformation.get_all(order_by="name asc")
else:
    # Work-around for Streamlit losing typing on session state
    st.session_state.transformations = [
        Transformation(**trans.model_dump())
        for trans in st.session_state.transformations
    ]

# Initialize session state for notebook transformation tab if not present
if "nb_transform_selected_notebook_id" not in st.session_state:
    st.session_state.nb_transform_selected_notebook_id = None
if "nb_transform_selected_transformation_id" not in st.session_state: # For consistency, though playground might use obj
    st.session_state.nb_transform_selected_transformation_id = None
if "nb_transform_selected_model_id" not in st.session_state:
    st.session_state.nb_transform_selected_model_id = None


transformations_tab, playground_tab, notebook_transform_tab = st.tabs([
    "🧩 Transformations", 
    "🛝 Playground",
    "📓 Notebook Transformation" # New Tab
])


with transformations_tab:
    st.header("🧩 Transformations")

    st.markdown(
        "Transformations are prompts that will be used by the LLM to process a source and extract insights, summaries, etc. "
    )
    default_prompts: DefaultPrompts = DefaultPrompts()
    with st.expander("**⚙️ Default Transformation Prompt**"):
        default_prompts.transformation_instructions = st.text_area(
            "Default Transformation Prompt",
            default_prompts.transformation_instructions,
            height=300,
        )
        st.caption("This will be added to all your transformation prompts.")
        if st.button("Save", key="save_default_prompt"):
            default_prompts.update()
            st.toast("Default prompt saved successfully!")
    if st.button("Create new Transformation", icon="➕", key="new_transformation"):
        new_transformation = Transformation(
            name="New Tranformation",
            title="New Transformation Title",
            description="New Transformation Description",
            prompt="New Transformation Prompt",
            apply_default=False,
        )
        st.session_state.transformations.insert(0, new_transformation)
        st.rerun()

    st.divider()
    st.markdown("Your Transformations")
    if len(st.session_state.transformations) == 0:
        st.markdown(
            "No transformation created yet. Click 'Create new transformation' to get started."
        )
    else:
        for idx, transformation_item in enumerate(st.session_state.transformations): # Renamed to avoid conflict
            transform_expander = f"**{transformation_item.name}**" + (
                " - default" if transformation_item.apply_default else ""
            )
            with st.expander(
                transform_expander,
                expanded=(transformation_item.id is None),
            ):
                name = st.text_input(
                    "Transformation Name",
                    transformation_item.name,
                    key=f"{transformation_item.id}_name",
                )
                title = st.text_input(
                    "Card Title (this will be the title of all cards created by this transformation). ie 'Key Topics'",
                    transformation_item.title,
                    key=f"{transformation_item.id}_title",
                )
                description = st.text_area(
                    "Description (displayed as a hint in the UI so you know what you are selecting)",
                    transformation_item.description,
                    key=f"{transformation_item.id}_description",
                )
                prompt = st.text_area(
                    "Prompt",
                    transformation_item.prompt,
                    key=f"{transformation_item.id}_prompt",
                    height=300,
                )
                st.markdown(
                    "You can use the prompt to summarize, expand, extract insights and much more. Example: `Translate this text to French`. For inspiration, check out this [great resource](https://github.com/danielmiessler/fabric/tree/main/patterns)."
                )

                apply_default = st.checkbox(
                    "Suggest by default on new sources",
                    transformation_item.apply_default,
                    key=f"{transformation_item.id}_apply_default",
                )
                if st.button("Save", key=f"{transformation_item.id}_save"):
                    transformation_item.name = name
                    transformation_item.title = title
                    transformation_item.description = description
                    transformation_item.prompt = prompt
                    transformation_item.apply_default = apply_default
                    st.toast(f"Transformation '{name}' saved successfully!")
                    transformation_item.save()
                    st.rerun()

                if transformation_item.id:
                    with st.popover("Other actions"):
                        if st.button(
                            "Use in Playground",
                            icon="🛝",
                            key=f"{transformation_item.id}_playground",
                        ):
                            # This logic might need adjustment if playground uses index/object
                            st.session_state.playground_selected_transformation = transformation_item 
                            # Potentially switch to playground tab or update its selectbox
                            st.toast(f"Switched to Playground with {transformation_item.name}")
                            # st.experimental_set_query_params(tab="Playground") # Might not work as expected for tabs
                            # Simplest is to let user click tab, playground selectbox will reflect this.
                        if st.button(
                            "Delete", icon="❌", key=f"{transformation_item.id}_delete"
                        ):
                            transformation_item.delete()
                            st.session_state.transformations.remove(transformation_item)
                            st.toast(f"Transformation '{name}' deleted successfully!")
                            st.rerun()

with playground_tab:
    st.title("🛝 Playground")

    # Ensure playground_selected_transformation is initialized for the selectbox
    if 'playground_selected_transformation' not in st.session_state:
        st.session_state.playground_selected_transformation = st.session_state.transformations[0] if st.session_state.transformations else None

    selected_transformation_playground = st.selectbox( # Renamed to avoid conflict
        "Pick a transformation",
        st.session_state.transformations,
        format_func=lambda x: x.name if x else "No transformations available",
        index=st.session_state.transformations.index(st.session_state.playground_selected_transformation) if st.session_state.playground_selected_transformation and st.session_state.playground_selected_transformation in st.session_state.transformations else 0,
        key="playground_transformation_selector"
    )
    st.session_state.playground_selected_transformation = selected_transformation_playground


    selected_model_playground = model_selector( # Renamed
        "Pick a pattern model",
        key="playground_model_selector", # Unique key
        help="This is the model that will be used to run the transformation",
        model_type="language",
    )

    input_text = st.text_area("Enter some text", height=200, key="playground_input_text")

    if st.button("Run", key="playground_run_button"):
        if selected_transformation_playground and selected_model_playground and input_text:
            output = transformation_graph.invoke(
                dict(
                    input_text=input_text,
                    transformation=selected_transformation_playground,
                ),
                config=dict(configurable={"model_id": selected_model_playground.id}),
            )
            st.markdown(output["output"])
        else:
            st.warning("Please select a transformation, a model, and enter some text.")

# Helper function to aggregate content
def aggregate_notebook_content(notebook: Notebook, source_config: dict) -> str:
    """
    Aggregates content from a notebook's sources and notes based on configuration.
    Sources can be 'Insights', 'Full Content', or 'Not in Context'.
    Notes are always included with 'Full Content'.
    """
    aggregated_texts = []

    # Process Sources
    if notebook.sources:
        for source in notebook.sources:
            selection = source_config.get(str(source.id), "Not in Context") 
            
            text_to_add = None
            source_title_for_header = source.title or f"Source ID: {source.id}"

            if selection == "Insights":
                context_data = source.get_context(context_size="short") # Returns dict
                insights_list = context_data.get('insights', [])
                if insights_list:
                    insight_strings = []
                    for insight_item in insights_list:
                        # Assuming insight_item is a dict from insight.model_dump()
                        # with 'insight_type' and 'content' keys
                        insight_type = insight_item.get('insight_type', 'Insight')
                        content = insight_item.get('content', '')
                        insight_strings.append(f"- {insight_type}: {content}")
                    text_to_add = "Insights:\n" + "\n".join(insight_strings)
                else:
                    text_to_add = "No insights available for this source."
            elif selection == "Full Content":
                context_data = source.get_context(context_size="long") # Returns dict
                text_to_add = context_data.get('full_text')
            
            if text_to_add:
                aggregated_texts.append(f"--- Source: {source_title_for_header} ({selection}) ---\n{text_to_add}")

    # Process Notes (always full content)
    if notebook.notes:
        for note in notebook.notes:
            note_content = note.content # Direct access to note content
            if note_content: 
                note_title_for_header = note.title or f"Note ID: {note.id}"
                aggregated_texts.append(f"--- Note: {note_title_for_header} ---\n{note_content}")
    
    return "\n\n--------------------\n\n".join(aggregated_texts)

# --- Notebook Transformation Tab ---
with notebook_transform_tab:
    st.title("📓 Notebook Transformation")

    # Initialize the output area placeholder at the top of the tab
    if "nb_transform_output_area" not in st.session_state:
        st.session_state.nb_transform_output_area = st.empty()
    
    all_notebooks = Notebook.get_all(order_by="name asc")
    
    selected_notebook = st.selectbox(
        "Select Notebook",
        options=all_notebooks,
        format_func=lambda nb: nb.name if nb else "Select a Notebook",
        key="nb_transform_notebook_selector",
        index=None 
    )

    # Initialize or update source configuration when notebook changes
    if selected_notebook:
        if st.session_state.nb_transform_selected_notebook_id != selected_notebook.id:
            # Notebook has changed, reset or initialize source config for the new notebook
            st.session_state.nb_transform_selected_notebook_id = selected_notebook.id
            st.session_state.notebook_transform_source_config = {
                src.id: "Insights" for src in selected_notebook.sources
            } # Default to "Insights"
        elif "notebook_transform_source_config" not in st.session_state:
            # Initialize if accessing for the first time with this notebook already selected
             st.session_state.notebook_transform_source_config = {
                src.id: "Insights" for src in selected_notebook.sources
            }
        
        st.markdown(f"Selected Notebook: **{selected_notebook.name}** (ID: {selected_notebook.id})")
        
        st.markdown("---")
        st.subheader("Configure Source Content Inclusion")
        
        if not selected_notebook.sources:
            st.info("This notebook has no sources.")
        else:
            for source in selected_notebook.sources:
                # Ensure each source has an entry in the config, defaulting if somehow missed
                if source.id not in st.session_state.notebook_transform_source_config:
                    st.session_state.notebook_transform_source_config[source.id] = "Insights"

                selection_options = ["Not in Context", "Insights", "Full Content"]
                current_selection = st.session_state.notebook_transform_source_config[source.id]
                
                # Ensure current_selection is valid, otherwise default to prevent error
                try:
                    current_index = selection_options.index(current_selection)
                except ValueError:
                    current_index = 1 # Default to "Insights" index
                    st.session_state.notebook_transform_source_config[source.id] = "Insights"

                # Determine source type string, handling potential None for asset or source_type
                source_type_display = "N/A"
                if source.asset and source.asset.source_type:
                    source_type_display = source.asset.source_type.capitalize()

                chosen_option = st.radio(
                    label=f"**{source.title or f'Source ID: {source.id}'}** ({source_type_display})",
                    options=selection_options,
                    index=current_index,
                    key=f"nb_transform_src_radio_{selected_notebook.id}_{source.id}", # Ensure key is unique across notebooks
                    horizontal=True,
                )
                st.session_state.notebook_transform_source_config[source.id] = chosen_option
        st.markdown("---")

    else:
        st.session_state.nb_transform_selected_notebook_id = None
        # Clear source config if no notebook is selected
        if "notebook_transform_source_config" in st.session_state:
            # del st.session_state.notebook_transform_source_config
            # Let's keep the config around but disable/hide if no notebook is selected
            pass

    # Transformation Selector (reused pattern from playground)
    # Ensure nb_transform_selected_transformation is initialized
    if 'nb_transform_selected_transformation' not in st.session_state:
        st.session_state.nb_transform_selected_transformation = st.session_state.transformations[0] if st.session_state.transformations else None

    selected_transformation_nb = st.selectbox(
        "Pick a transformation",
        st.session_state.transformations,
        format_func=lambda x: x.name if x else "No transformations available",
        index=st.session_state.transformations.index(st.session_state.nb_transform_selected_transformation) if st.session_state.nb_transform_selected_transformation and st.session_state.nb_transform_selected_transformation in st.session_state.transformations else 0,
        key="nb_transform_transformation_selector"
    )
    if selected_transformation_nb:
        st.session_state.nb_transform_selected_transformation_id = selected_transformation_nb.id
        # Store the object for easier access, similar to playground, or just use ID
        st.session_state.nb_transform_selected_transformation = selected_transformation_nb 


    # Model Selector (reused pattern from playground)
    selected_model_nb = model_selector(
        "Pick a model for the transformation",
        key="nb_transform_model_selector", # Unique key
        help="This model will process the aggregated notebook content.",
        model_type="language",
    )
    if selected_model_nb:
        st.session_state.nb_transform_selected_model_id = selected_model_nb.id

    if st.button("Run Transformation on Notebook", key="nb_transform_run_button"):
        if selected_notebook and selected_transformation_nb and selected_model_nb:
            # Ensure source config is available; it should be due to UI flow
            source_config = st.session_state.get("notebook_transform_source_config", {})
            
            if not source_config and selected_notebook.sources: 
                st.warning("Source configuration is missing. Please re-select the notebook.")
                st.stop()

            with st.spinner(f"Aggregating content from '{selected_notebook.name}'..."):
                aggregated_text = aggregate_notebook_content(selected_notebook, source_config)
            
            if not aggregated_text:
                st.session_state.nb_transform_output_area.warning("No content was aggregated from the notebook based on current selections. Nothing to transform.")
                st.stop()

            # Check token count before sending to LLM
            try:
                # Construct the full prompt parts for accurate token counting
                # default_prompts is defined at the script level and updated by its UI
                system_prompt_text = f"{default_prompts.transformation_instructions}\n{selected_transformation_nb.prompt}"
                # aggregated_text is already defined
                
                system_tokens = token_count(system_prompt_text)
                input_tokens = token_count(aggregated_text)
                total_input_tokens = system_tokens + input_tokens
                
                MAX_ALLOWED_INPUT_TOKENS = 700000 
                st.info(f"Estimated total input tokens for LLM: {total_input_tokens} (System: {system_tokens}, User Text: {input_tokens})")

                if total_input_tokens > MAX_ALLOWED_INPUT_TOKENS:
                    st.session_state.nb_transform_output_area.error(
                        f"The combined prompt and content is too long ({total_input_tokens} tokens, estimated). "
                        f"Maximum allowed for input is approximately {MAX_ALLOWED_INPUT_TOKENS} tokens. "
                        f"(System prompt: {system_tokens} tokens, Aggregated text: {input_tokens} tokens). "
                        f"Please reduce the amount of selected content (e.g., use 'Insights' for large sources or select fewer items), "
                        f"or if the transformation prompt itself is very long, consider simplifying it."
                    )
                    st.stop()
            except Exception as e:
                st.warning(f"Could not estimate token count: {e}. Proceeding with caution.")

            st.info(f"Running '{selected_transformation_nb.name}' on aggregated content from notebook '{selected_notebook.name}' with model '{selected_model_nb.name}'.")
            with st.spinner(f"Applying transformation with {selected_model_nb.name}..."):
                try:
                    output = transformation_graph.invoke(
                        dict(
                            input_text=aggregated_text,
                            transformation=selected_transformation_nb, 
                        ),
                        config=dict(configurable={"model_id": selected_model_nb.id}),
                    )
                    output_content = output.get("output", "") # Safely get output
                    st.success("Transformation complete!")
                    st.session_state.nb_transform_output_area.markdown(f"--- Transformation Output ---\n{output_content}")
                except OpenAIError as e: # More specific error for OpenAI issues
                    if "context_length_exceeded" in str(e) or "maximum context length" in str(e).lower():
                        st.session_state.nb_transform_output_area.error(
                            f"Error during transformation: The content is too long for the selected model. "
                            f"Details: {e}"
                        )
                        st.error("The aggregated content exceeds the model's context limit. Please select less content or use 'Insights' for large sources.")
                    else:
                        st.session_state.nb_transform_output_area.error(f"An OpenAI error occurred: {e}")
                        st.error(f"An OpenAI error occurred: {e}")
                except Exception as e:
                    st.session_state.nb_transform_output_area.error(f"Error during transformation: {e}")
                    st.error(f"An unexpected error occurred: {e}")
        else:
            st.warning("Please select a notebook, a transformation, and a model.")

    # Placeholder for results display - THIS ENTIRE BLOCK IS REMOVED
    # st.markdown("--- Transformation Output ---") # Updated title
    # if "nb_transform_output_area" not in st.session_state: # ensure it's initialized
    #     st.session_state.nb_transform_output_area = st.empty()
    # # The actual st.empty() is now created earlier if it does not exist.
    # # We just refer to it here for clarity that this is where output goes.
    # # st.session_state.nb_transform_output_area.markdown("*Output will appear here*") # Optional: default message
