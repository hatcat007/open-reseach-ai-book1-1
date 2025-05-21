import os
from typing import Dict, List

import streamlit as st

from open_notebook.config import CONFIG
from open_notebook.domain.models import DefaultModels, Model, model_manager
from open_notebook.models import MODEL_CLASS_MAP
from pages.components.model_selector import model_selector
from pages.stream_app.utils import setup_page

setup_page("🤖 Models", only_check_mandatory_models=False, stop_on_model_error=False)


st.title("🤖 Models")

model_tab, model_defaults_tab = st.tabs(["Models", "Model Defaults"])

provider_status = {}

model_types = [
    # "vision",
    "language",
    "embedding",
    "text_to_speech",
    "speech_to_text",
]

provider_status["ollama"] = os.environ.get("OLLAMA_API_BASE") is not None
provider_status["openai"] = os.environ.get("OPENAI_API_KEY") is not None
provider_status["groq"] = os.environ.get("GROQ_API_KEY") is not None
provider_status["xai"] = os.environ.get("XAI_API_KEY") is not None
provider_status["vertexai"] = (
    os.environ.get("VERTEX_PROJECT") is not None
    and os.environ.get("VERTEX_LOCATION") is not None
    and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") is not None
)
provider_status["vertexai-anthropic"] = (
    os.environ.get("VERTEX_PROJECT") is not None
    and os.environ.get("VERTEX_LOCATION") is not None
    and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") is not None
)
provider_status["gemini"] = os.environ.get("GEMINI_API_KEY") is not None
provider_status["openrouter"] = (
    os.environ.get("OPENROUTER_API_KEY") is not None
    and os.environ.get("OPENAI_API_KEY") is not None
    and os.environ.get("OPENROUTER_BASE_URL") is not None
)
provider_status["anthropic"] = os.environ.get("ANTHROPIC_API_KEY") is not None
provider_status["elevenlabs"] = os.environ.get("ELEVENLABS_API_KEY") is not None
provider_status["lmstudio"] = os.environ.get("LM_STUDIO_API_BASE") is not None
provider_status["huggingface"] = os.environ.get("HF_API_KEY") is not None
provider_status["litellm"] = (
    provider_status["ollama"]
    or provider_status["vertexai"]
    or provider_status["vertexai-anthropic"]
    or provider_status["anthropic"]
    or provider_status["openai"]
    or provider_status["gemini"]
)

available_providers = [k for k, v in provider_status.items() if v]
unavailable_providers = [k for k, v in provider_status.items() if not v]


def generate_new_models(models, suggested_models):
    # Create a set of existing model keys for efficient lookup
    existing_model_keys = {
        f"{model.provider}-{model.name}-{model.type}" for model in models
    }

    new_models = []

    # Iterate through suggested models by provider
    for provider, types in suggested_models.items():
        # Iterate through each type (language, embedding, etc.)
        for type_, model_list in types.items():
            for model_name in model_list:
                model_key = f"{provider}-{model_name}-{type_}"

                # Check if model already exists
                if model_key not in existing_model_keys:
                    if provider_status.get(provider):
                        new_models.append(
                            {
                                "name": model_name,
                                "type": type_,
                                "provider": provider,
                            }
                        )

    return new_models


default_models = DefaultModels()
all_models = Model.get_all()

with model_tab:
    st.subheader("Add Model")

    provider = st.selectbox("Provider", available_providers)
    if len(unavailable_providers) > 0:
        st.caption(
            f"Unavailable Providers: {', '.join(unavailable_providers)}. Please check docs page if you wish to enable them."
        )

    # Filter model types based on provider availability in MODEL_CLASS_MAP
    available_model_types = []
    for model_type in model_types:
        if model_type in MODEL_CLASS_MAP and provider in MODEL_CLASS_MAP[model_type]:
            available_model_types.append(model_type)

    if not available_model_types:
        st.error(f"No compatible model types available for provider: {provider}")
    else:
        model_type = st.selectbox(
            "Model Type",
            available_model_types,
            help="Use language for text generation models, text_to_speech for TTS models for generating podcasts, etc.",
        )
        if model_type == "text_to_speech" and provider == "gemini":
            model_name = "gemini-default"
            st.markdown("Gemini models are pre-configured. Using the default model.")
        else:
            model_name = st.text_input(
                "Model Name", "", help="gpt-4o-mini, claude, gemini, llama3, etc"
            )
        if st.button("Save"):
            model = Model(name=model_name, provider=provider, type=model_type)
            model.save()
            st.success("Saved")

    st.divider()
    suggested_models = CONFIG.get("suggested_models", [])
    recommendations = generate_new_models(all_models, suggested_models)
    if len(recommendations) > 0:
        with st.expander("💁‍♂️ Recommended models to get you started.."):
            for recommendation in recommendations:
                st.markdown(
                    f"**{recommendation['name']}** ({recommendation['provider']}, {recommendation['type']})"
                )
                if st.button("Add", key=f"add_{recommendation['name']}"):
                    new_model = Model(**recommendation)
                    new_model.save()
                    st.rerun()
    st.subheader("Configured Models")
    model_types_available = {
        # "vision": False,
        "language": False,
        "embedding": False,
        "text_to_speech": False,
        "speech_to_text": False,
    }
    for model in all_models:
        model_types_available[model.type] = True
        with st.container(border=True):
            st.markdown(f"{model.name} ({model.provider}, {model.type})")
            if st.button("Delete", key=f"delete_{model.id}"):
                model.delete()
                st.rerun()

    for model_type, available in model_types_available.items():
        if not available:
            st.warning(f"No models available for {model_type}")

with model_defaults_tab:
    # Prepare transcript_provider_models dictionary
    all_language_models = [model for model in all_models if model.type == "language"]
    transcript_provider_models: Dict[str, List[str]] = {}
    for model in all_language_models:
        if model.provider not in transcript_provider_models:
            transcript_provider_models[model.provider] = []
        transcript_provider_models[model.provider].append(model.name)

    text_generation_models = [model for model in all_models if model.type == "language"]

    text_to_speech_models = [
        model for model in all_models if model.type == "text_to_speech"
    ]

    speech_to_text_models = [
        model for model in all_models if model.type == "speech_to_text"
    ]
    vision_models = [model for model in all_models if model.type == "vision"]
    embedding_models = [model for model in all_models if model.type == "embedding"]
    st.write(
        "In this section, you can select the default models to be used on the various content operations done by Open Notebook. Some of these can be overriden in the different modules."
    )
    defs = {}
    # Handle chat model selection
    selected_model = model_selector(
        "Default Chat Model",
        "default_chat_model",
        selected_id=default_models.default_chat_model,
        help="This model will be used for chat.",
        model_type="language",
    )
    if selected_model:
        default_models.default_chat_model = selected_model.id
    st.divider()
    # Handle transformation model selection
    selected_model = model_selector(
        "Default Transformation Model",
        "default_transformation_model",
        selected_id=default_models.default_transformation_model,
        help="This model will be used for text transformations such as summaries, insights, etc.",
        model_type="language",
    )
    if selected_model:
        default_models.default_transformation_model = selected_model.id
    st.caption("You can use a cheap model here like gpt-4o-mini, llama3, etc.")
    st.divider()

    # Handle tools model selection
    selected_model = model_selector(
        "Default Tools Model",
        "default_tools_model",
        selected_id=default_models.default_tools_model,
        help="This model will be used for calling tools. Currently, it's best to use Open AI and Anthropic for this.",
        model_type="language",
    )
    if selected_model:
        default_models.default_tools_model = selected_model.id
    st.caption("Recommended to use a capable model here, like gpt-4o, claude, etc.")
    st.divider()

    # Handle large context model selection
    selected_model = model_selector(
        "Large Context Model",
        "large_context_model",
        selected_id=default_models.large_context_model,
        help="This model will be used for larger context generation -- recommended: Gemini",
        model_type="language",
    )
    if selected_model:
        default_models.large_context_model = selected_model.id
    st.caption("Recommended to use Gemini models for larger context processing")
    st.divider()

    # Handle text-to-speech model selection
    selected_model = model_selector(
        "Default Text to Speech Model",
        "default_text_to_speech_model",
        selected_id=default_models.default_text_to_speech_model,
        help="This is the default model for converting text to speech (podcasts, etc)",
        model_type="text_to_speech",
    )
    st.caption("You can override this model on different podcasts")
    if selected_model:
        default_models.default_text_to_speech_model = selected_model.id
    st.divider()

    # Handle speech-to-text model selection
    selected_model = model_selector(
        "Default Speech to Text Model",
        selected_id=default_models.default_speech_to_text_model,
        help="This is the default model for converting speech to text (audio transcriptions, etc)",
        model_type="speech_to_text",
        key="default_speech_to_text_model",
    )

    if selected_model:
        default_models.default_speech_to_text_model = selected_model.id

    # ---- Add Default Transcript Model Provider and Model ----
    st.divider()
    st.subheader("Default Transcript Generation Models")
    st.caption("These models will be used for generating podcast transcripts if not specified in a podcast template.")

    # Get current selections or set to None if not yet defined
    current_default_transcript_provider = default_models.default_transcript_model_provider
    current_default_transcript_model = default_models.default_transcript_model

    # Selectbox for Default Transcript Model Provider
    prov_options = list(transcript_provider_models.keys())
    prov_index = 0
    if current_default_transcript_provider in prov_options:
        prov_index = prov_options.index(current_default_transcript_provider)
    elif prov_options: # If current default is None or invalid, but there are options, select the first
        current_default_transcript_provider = prov_options[0]
    else: # No providers available
        current_default_transcript_provider = None

    selected_transcript_provider = st.selectbox(
        "Default Transcript Model Provider",
        options=prov_options,
        index=prov_index,
        key="default_transcript_provider_selector",
        help="Select the default provider for transcript generation."
    )
    default_models.default_transcript_model_provider = selected_transcript_provider # Update immediately

    # Selectbox for Default Transcript Model (dependent on provider)
    available_transcript_models_for_provider = []
    if selected_transcript_provider and selected_transcript_provider in transcript_provider_models:
        available_transcript_models_for_provider = transcript_provider_models[selected_transcript_provider]
    
    model_index = 0
    if available_transcript_models_for_provider: # Only proceed if there are models for the selected provider
        if current_default_transcript_model in available_transcript_models_for_provider and default_models.default_transcript_model_provider == selected_transcript_provider:
            model_index = available_transcript_models_for_provider.index(current_default_transcript_model)
        elif available_transcript_models_for_provider: # If current default is None/invalid or provider changed, select first model
            current_default_transcript_model = available_transcript_models_for_provider[0]
            # default_models.default_transcript_model = current_default_transcript_model # Update this when saving
    else: # No models for this provider, or no provider selected
        current_default_transcript_model = None
        # default_models.default_transcript_model = None # Update this when saving

    selected_transcript_model = st.selectbox(
        "Default Transcript Model",
        options=available_transcript_models_for_provider,
        index=model_index,
        key="default_transcript_model_selector",
        help="Select the default model for transcript generation from the chosen provider."
    )
    # We will assign this to default_models.default_transcript_model before saving via the button.
    # This avoids issues if the user changes provider and this model becomes invalid temporarily.

    # ---- End of Default Transcript Model Provider and Model ----
    st.divider()
    # Handle embedding model selection
    selected_model = model_selector(
        "Default Speech to Text Model",
        "default_embedding_model",
        selected_id=default_models.default_embedding_model,
        help="This is the default model for embeddings (semantic search, etc)",
        model_type="embedding",
    )
    if selected_model:
        default_models.default_embedding_model = selected_model.id
    st.warning(
        "Caution: you cannot change the embedding model once there is embeddings or they will need to be regenerated"
    )

    for k, v in defs.items():
        if v:
            defs[k] = v.id

    if st.button("Save Defaults"):
        # Ensure the latest selections for transcript models are captured before patching
        defs["default_transcript_model_provider"] = st.session_state.default_transcript_provider_selector
        # Only set default_transcript_model if a provider and model are actually selected
        if st.session_state.default_transcript_provider_selector and st.session_state.default_transcript_model_selector:
            defs["default_transcript_model"] = st.session_state.default_transcript_model_selector
        else:
            defs["default_transcript_model"] = None # Explicitly set to None if not fully selected
            
        default_models.patch(defs)
        model_manager.refresh_defaults()
        st.success("Saved")
