from typing import Dict, List

import streamlit as st
from streamlit_tags import st_tags

from open_notebook.domain.models import Model
from open_notebook.plugins.podcasts import (
    PodcastConfig,
    PodcastEpisode,
    conversation_styles,
    dialogue_structures,
    engagement_techniques,
    participant_roles,
)
from pages.stream_app.utils import setup_page

setup_page("🎙️ Podcasts", only_check_mandatory_models=False)

# Define callback function at the top level or ensure it's available in scope
def add_role_action(pd_config_id: str, role_type: str, input_key: str, session_state_temp_roles_key: str):
    roles_input_string = st.session_state.get(input_key, "")
    if roles_input_string and roles_input_string.strip():
        # Split the input string by commas, strip whitespace from each part, and filter out empty strings
        potential_roles = [r.strip() for r in roles_input_string.split(',') if r.strip()] 

        if session_state_temp_roles_key not in st.session_state:
            st.session_state[session_state_temp_roles_key] = [] # Initialize if not present
        
        roles_added_this_action = False
        for cleaned_new_role in potential_roles:
            # Add to the temporary list for this session if not already there
            if cleaned_new_role not in st.session_state[session_state_temp_roles_key]:
                st.session_state[session_state_temp_roles_key].append(cleaned_new_role)
                roles_added_this_action = True
        
        if roles_added_this_action:
             # If any role was actually added, we might want to ensure the UI reflects it.
             # The on_click should handle the rerun, clearing the input is main thing here.
            pass # st.rerun() is implicitly handled by on_click finishing

        # st.session_state[input_key] = "" # Removed to prevent StreamlitAPIException
        # No explicit st.rerun() here, on_click handles the rerun implicitly after the callback

text_to_speech_models = Model.get_models_by_type("text_to_speech")

provider_models: Dict[str, List[str]] = {}

for model in text_to_speech_models:
    if model.provider not in provider_models:
        provider_models[model.provider] = []
    provider_models[model.provider].append(model.name)

text_models = Model.get_models_by_type("language")

transcript_provider_models: Dict[str, List[str]] = {}

for model in text_models:
    # Allow all configured language models to be available for transcript generation
    # if model.provider not in ["gemini", "openai", "anthropic"]:
    #     continue
    if model.provider not in transcript_provider_models:
        transcript_provider_models[model.provider] = []
    transcript_provider_models[model.provider].append(model.name)


if len(text_to_speech_models) == 0:
    st.error("No text to speech models found. Please set one up in the Models page.")
    st.stop()

if len(text_models) == 0:
    st.error(
        "No language models found. Please set one up in the Models page. Only Gemini, Open AI and Anthropic models supported for transcript generation."
    )
    st.stop()

episodes_tab, templates_tab = st.tabs(["Episodes", "Templates"])

with episodes_tab:
    episodes = PodcastEpisode.get_all(order_by="created desc")
    for episode in episodes:
        with st.container(border=True):
            episode_name = episode.name if episode.name else "No Name"
            st.markdown(f"**{episode.template} - {episode_name}**")
            # st.caption(naturaltime(episode.created))
            st.write(f"Instructions: {episode.instructions}")
            try:
                st.audio(episode.audio_file, format="audio/mpeg", loop=True)
            except Exception as e:
                st.write("No audio file found")
                st.error(e)
            with st.expander("Source Content"):
                st.code(episode.text)
            if st.button("Delete Episode", key=f"btn_delete{episode.id}"):
                episode.delete()
                st.rerun()
    if len(episodes) == 0:
        st.write("No episodes yet")
with templates_tab:
    st.subheader("Podcast Templates")
    st.markdown("")
    with st.expander("**Create new Template**"):
        pd_cfg = {}
        pd_cfg["name"] = st.text_input("Template Name")
        pd_cfg["podcast_name"] = st.text_input("Podcast Name")
        pd_cfg["podcast_tagline"] = st.text_input("Podcast Tagline")
        pd_cfg["output_language"] = st.text_input("Language", value="English")
        pd_cfg["user_instructions"] = st.text_input(
            "User Instructions",
            help="Any additional intructions to pass to the LLM that will generate the transcript",
        )
        pd_cfg["person1_role"] = st_tags(
            [], participant_roles, "Person 1 roles", key="person1_roles"
        )
        st.caption(f"Suggestions:{', '.join(participant_roles)}")
        pd_cfg["person2_role"] = st_tags(
            [], participant_roles, "Person 2 roles", key="person2_roles"
        )
        pd_cfg["conversation_style"] = st_tags(
            [], conversation_styles, "Conversation Style", key="conversation_styles"
        )
        st.caption(f"Suggestions:{', '.join(conversation_styles)}")
        pd_cfg["engagement_technique"] = st_tags(
            [],
            engagement_techniques,
            "Engagement Techniques",
            key="engagement_techniques",
        )
        st.caption(f"Suggestions:{', '.join(engagement_techniques)}")
        pd_cfg["dialogue_structure"] = st.text_input(
            "Dialogue Structure", 
            key="dialogue_structures_new", 
            help="Describe the dialogue structure (e.g., Interview, Debate, Monologue)."
        ) 
        pd_cfg["creativity"] = st.slider(
            "Creativity", min_value=0.0, max_value=1.0, step=0.05
        )
        pd_cfg["ending_message"] = st.text_input(
            "Ending Message", placeholder="Thank you for listening!"
        )
        pd_cfg["transcript_model_provider"] = st.selectbox(
            "Transcript Model Provider", transcript_provider_models.keys()
        )

        # Safely get transcript models based on the selected provider
        selected_transcript_provider = pd_cfg.get("transcript_model_provider")
        available_transcript_models = []
        if selected_transcript_provider and selected_transcript_provider in transcript_provider_models:
            available_transcript_models = transcript_provider_models[selected_transcript_provider]
        elif selected_transcript_provider:
            st.warning(f"Transcript provider '{selected_transcript_provider}' not found. Please check configuration.")
        # If selected_transcript_provider is None (e.g., no providers available or none selected),
        # available_transcript_models remains empty, and the selectbox below will show no options.
            
        pd_cfg["transcript_model"] = st.selectbox(
            "Transcript Model",
            available_transcript_models, # Use the safely prepared list
        )

        pd_cfg["provider"] = st.selectbox(
            "Audio Model Provider", provider_models.keys()
        )
        pd_cfg["model"] = st.selectbox(
            "Audio Model", provider_models[pd_cfg["provider"]]
        )
        st.caption(
            "OpenAI: tts-1 or tts-1-hd, Elevenlabs: eleven_multilingual_v2, eleven_turbo_v2_5"
        )
        pd_cfg["voice1"] = st.text_input(
            "Voice 1", help="You can use Elevenlabs voice ID"
        )
        st.caption("Voice names are case sensitive. Be sure to add the exact name.")

        st.markdown(
            "Sample voices from: [Open AI](https://platform.openai.com/docs/guides/text-to-speech), [Gemini](https://cloud.google.com/text-to-speech/docs/voices), [Elevenlabs](https://elevenlabs.io/text-to-speech)"
        )

        pd_cfg["voice2"] = st.text_input(
            "Voice 2", help="You can use Elevenlabs voice ID"
        )

        if st.button("Save"):
            try:
                pd = PodcastConfig(**pd_cfg)
                pd_cfg = {}
                pd.save()
            except Exception as e:
                st.error(e)

    for pd_config in PodcastConfig.get_all(order_by="created desc"):
        with st.expander(pd_config.name):
            pd_config.name = st.text_input(
                "Template Name", value=pd_config.name, key=f"name_{pd_config.id}"
            )
            pd_config.podcast_name = st.text_input(
                "Podcast Name",
                value=pd_config.podcast_name,
                key=f"podcast_name_{pd_config.id}",
            )
            pd_config.podcast_tagline = st.text_input(
                "Podcast Tagline",
                value=pd_config.podcast_tagline,
                key=f"podcast_tagline_{pd_config.id}",
            )
            pd_config.user_instructions = st.text_input(
                "User Instructions",
                value=pd_config.user_instructions,
                help="Any additional intructions to pass to the LLM that will generate the transcript",
                key=f"user_instructions_{pd_config.id}",
            )

            pd_config.output_language = st.text_input(
                "Language",
                value=pd_config.output_language,
                key=f"output_language_{pd_config.id}",
            )
            
            # --- Person 1 Roles --- 
            st.markdown("#### Person 1 Roles")
            field_key_prefix_p1 = "p1_roles" 
            key_p1_new_item_input = f"new_item_input_{field_key_prefix_p1}_{pd_config.id}"
            key_p1_add_item_button = f"add_item_button_{field_key_prefix_p1}_{pd_config.id}"
            session_state_temp_p1_items_key = f"temp_items_{field_key_prefix_p1}_{pd_config.id}"

            if session_state_temp_p1_items_key not in st.session_state:
                st.session_state[session_state_temp_p1_items_key] = []

            col1_p1, col2_p1 = st.columns([3, 1])
            with col1_p1:
                st.text_input(
                    "Add new P1 role(s) (comma-separated)", # Not visible due to collapsed label
                    key=key_p1_new_item_input,
                    label_visibility="collapsed",
                    placeholder="Add new P1 role(s), e.g., Host, Expert"
                )
            with col2_p1:
                st.button(
                    "Add",
                    key=key_p1_add_item_button,
                    on_click=add_role_action, 
                    args=(pd_config.id, field_key_prefix_p1, key_p1_new_item_input, session_state_temp_p1_items_key),
                    use_container_width=True
                )

            current_p1_roles_from_db = list(pd_config.person1_role)
            dynamically_added_p1_roles = list(st.session_state.get(session_state_temp_p1_items_key, []))
            p1_role_options = sorted(list(set(participant_roles + current_p1_roles_from_db + dynamically_added_p1_roles)))
            default_selected_p1_roles = sorted(list(set(current_p1_roles_from_db + dynamically_added_p1_roles)))
            
            key_p1_roles_multiselect = f"multiselect_{field_key_prefix_p1}_{pd_config.id}"
            pd_config.person1_role = st.multiselect(
                label="Selected P1 Roles",
                options=p1_role_options,
                default=default_selected_p1_roles,
                key=key_p1_roles_multiselect
            )
            
            # --- Person 2 Roles ---
            st.markdown("#### Person 2 Roles")
            field_key_prefix_p2 = "p2_roles"
            key_p2_new_item_input = f"new_item_input_{field_key_prefix_p2}_{pd_config.id}"
            key_p2_add_item_button = f"add_item_button_{field_key_prefix_p2}_{pd_config.id}"
            session_state_temp_p2_items_key = f"temp_items_{field_key_prefix_p2}_{pd_config.id}"

            if session_state_temp_p2_items_key not in st.session_state:
                st.session_state[session_state_temp_p2_items_key] = []
            
            col1_p2, col2_p2 = st.columns([3,1])
            with col1_p2:
                st.text_input(
                    "Add new P2 role(s) (comma-separated)",
                    key=key_p2_new_item_input,
                    label_visibility="collapsed",
                    placeholder="Add new P2 role(s), e.g., Interviewee, Analyst"
                )
            with col2_p2:
                st.button(
                    "Add",
                    key=key_p2_add_item_button,
                    on_click=add_role_action,
                    args=(pd_config.id, field_key_prefix_p2, key_p2_new_item_input, session_state_temp_p2_items_key),
                    use_container_width=True
                )

            current_p2_roles_from_db = list(pd_config.person2_role)
            dynamically_added_p2_roles = list(st.session_state.get(session_state_temp_p2_items_key, []))
            p2_role_options = sorted(list(set(participant_roles + current_p2_roles_from_db + dynamically_added_p2_roles)))
            default_selected_p2_roles = sorted(list(set(current_p2_roles_from_db + dynamically_added_p2_roles)))

            key_p2_roles_multiselect = f"multiselect_{field_key_prefix_p2}_{pd_config.id}"
            pd_config.person2_role = st.multiselect(
                label="Selected P2 Roles",
                options=p2_role_options,
                default=default_selected_p2_roles,
                key=key_p2_roles_multiselect
            )

            # --- Conversation Style ---
            st.markdown("#### Conversation Styles")
            field_key_prefix_cs = "conv_style"
            key_cs_new_item_input = f"new_item_input_{field_key_prefix_cs}_{pd_config.id}"
            key_cs_add_item_button = f"add_item_button_{field_key_prefix_cs}_{pd_config.id}"
            session_state_temp_cs_items_key = f"temp_items_{field_key_prefix_cs}_{pd_config.id}"

            if session_state_temp_cs_items_key not in st.session_state:
                st.session_state[session_state_temp_cs_items_key] = []

            col1_cs, col2_cs = st.columns([3,1])
            with col1_cs:
                st.text_input(
                    "Add new conversation style(s) (comma-separated)",
                    key=key_cs_new_item_input,
                    label_visibility="collapsed",
                    placeholder="Add new style(s), e.g., Formal, Casual"
                )
            with col2_cs:
                st.button(
                    "Add",
                    key=key_cs_add_item_button,
                    on_click=add_role_action,
                    args=(pd_config.id, field_key_prefix_cs, key_cs_new_item_input, session_state_temp_cs_items_key),
                    use_container_width=True
                )
            
            current_cs_from_db = list(pd_config.conversation_style)
            dynamically_added_cs = list(st.session_state.get(session_state_temp_cs_items_key, []))
            cs_options = sorted(list(set(conversation_styles + current_cs_from_db + dynamically_added_cs)))
            default_selected_cs = sorted(list(set(current_cs_from_db + dynamically_added_cs)))

            key_cs_multiselect = f"multiselect_{field_key_prefix_cs}_{pd_config.id}"
            pd_config.conversation_style = st.multiselect(
                label="Selected Conversation Styles",
                options=cs_options,
                default=default_selected_cs,
                key=key_cs_multiselect
            )
            
            # --- Engagement Techniques ---
            st.markdown("#### Engagement Techniques")
            field_key_prefix_et = "eng_tech"
            key_et_new_item_input = f"new_item_input_{field_key_prefix_et}_{pd_config.id}"
            key_et_add_item_button = f"add_item_button_{field_key_prefix_et}_{pd_config.id}"
            session_state_temp_et_items_key = f"temp_items_{field_key_prefix_et}_{pd_config.id}"

            if session_state_temp_et_items_key not in st.session_state:
                st.session_state[session_state_temp_et_items_key] = []

            col1_et, col2_et = st.columns([3,1])
            with col1_et:
                st.text_input(
                    "Add new engagement technique(s) (comma-separated)",
                    key=key_et_new_item_input,
                    label_visibility="collapsed",
                    placeholder="Add new technique(s), e.g., Storytelling, Q&A"
                )
            with col2_et:
                st.button(
                    "Add",
                    key=key_et_add_item_button,
                    on_click=add_role_action,
                    args=(pd_config.id, field_key_prefix_et, key_et_new_item_input, session_state_temp_et_items_key),
                    use_container_width=True
                )

            current_et_from_db = list(pd_config.engagement_technique)
            dynamically_added_et = list(st.session_state.get(session_state_temp_et_items_key, []))
            et_options = sorted(list(set(engagement_techniques + current_et_from_db + dynamically_added_et)))
            default_selected_et = sorted(list(set(current_et_from_db + dynamically_added_et)))

            key_et_multiselect = f"multiselect_{field_key_prefix_et}_{pd_config.id}"
            pd_config.engagement_technique = st.multiselect(
                label="Selected Engagement Techniques",
                options=et_options,
                default=default_selected_et,
                key=key_et_multiselect
            )

            # --- Dialogue Structure ---
            st.markdown("#### Dialogue Structures")
            pd_config.dialogue_structure = st.text_input(
                label="Dialogue Structure",
                value=pd_config.dialogue_structure if pd_config.dialogue_structure is not None else "", # Use directly, ensure None is handled
                key=f"dialogue_structure_{pd_config.id}",
                help="Describe the dialogue structure (e.g., Interview, Debate, Monologue)."
            )

            st.divider() # Visual separator before other fields
            pd_config.creativity = st.slider(
                "Creativity",
                min_value=0.0,
                max_value=1.0,
                step=0.05,
                value=pd_config.creativity,
                key=f"creativity_{pd_config.id}",
            )
            pd_config.ending_message = st.text_input(
                "Ending Message",
                value=pd_config.ending_message,
                placeholder="Thank you for listening!",
                key=f"ending_message_{pd_config.id}",
            )

            # Determine index for Transcript Model Provider selectbox
            current_transcript_provider = pd_config.transcript_model_provider
            provider_keys = list(transcript_provider_models.keys())
            try:
                provider_index = provider_keys.index(current_transcript_provider) if current_transcript_provider in provider_keys else 0
            except ValueError:
                provider_index = 0 # Default to first if current value is somehow not in keys
                if current_transcript_provider is not None: # Only warn if it was set to something invalid
                    st.warning(f"Saved transcript provider '{current_transcript_provider}' for template '{pd_config.name}' is no longer valid. Defaulting selection.")
                    pd_config.transcript_model_provider = provider_keys[0] if provider_keys else None # Reset to a valid one or None

            pd_config.transcript_model_provider = st.selectbox(
                "Transcript Model Provider",
                provider_keys,
                index=provider_index,
                key=f"transcript_provider_{pd_config.id}",
            )

            # Safely get available transcript models for the currently selected provider for this config
            models_for_selected_provider = []
            if pd_config.transcript_model_provider and pd_config.transcript_model_provider in transcript_provider_models:
                models_for_selected_provider = transcript_provider_models[pd_config.transcript_model_provider]
            elif pd_config.transcript_model_provider: # Provider selected but not in our map
                 st.warning(f"Transcript provider '{pd_config.transcript_model_provider}' for template '{pd_config.name}' not found in model map. Cannot list models.")

            # Determine index for Transcript Model selectbox
            current_transcript_model = pd_config.transcript_model
            model_index = 0
            if models_for_selected_provider: # Only try to find index if there are models to select from
                try:
                    model_index = models_for_selected_provider.index(current_transcript_model) if current_transcript_model in models_for_selected_provider else 0
                except ValueError:
                    model_index = 0 # Default to first model
                    if current_transcript_model is not None:
                        st.warning(f"Saved transcript model '{current_transcript_model}' for template '{pd_config.name}' is no longer valid for the selected provider. Defaulting selection.")
                        pd_config.transcript_model = models_for_selected_provider[0] if models_for_selected_provider else None # Reset to a valid one or None
            elif current_transcript_model: # No models for provider, but a model was saved
                st.warning(f"Saved transcript model '{current_transcript_model}' for template '{pd_config.name}' but current provider has no models or is invalid.")
                pd_config.transcript_model = None # Clear invalid model

            pd_config.transcript_model = st.selectbox(
                "Transcript Model",
                models_for_selected_provider,
                index=model_index,
                key=f"transcript_model_{pd_config.id}",
            )

            pd_config.provider = st.selectbox(
                "Audio Model Provider",
                list(provider_models.keys()),
                index=list(provider_models.keys()).index(pd_config.provider),
                key=f"provider_{pd_config.id}",
            )
            if pd_config.model not in provider_models[pd_config.provider]:
                index = 0
            else:
                index = provider_models[pd_config.provider].index(pd_config.model)
            pd_config.model = st.selectbox(
                "Model",
                provider_models[pd_config.provider],
                index=index,
                key=f"model_{pd_config.id}",
            )
            st.caption(
                "OpenAI: tts-1 or tts-1-hd, Elevenlabs: eleven_multilingual_v2, eleven_turbo_v2_5"
            )
            pd_config.voice1 = st.text_input(
                "Voice 1",
                value=pd_config.voice1,
                key=f"voice1_{pd_config.id}",
                help="You can use Elevenlabs voice ID",
            )
            st.caption("Voice names are case sensitive. Be sure to add the exact name.")
            st.markdown(
                "Sample voices from: [Open AI](https://platform.openai.com/docs/guides/text-to-speech), [Gemini](https://cloud.google.com/text-to-speech/docs/voices), [Elevenlabs](https://elevenlabs.io/text-to-speech)"
            )

            pd_config.voice2 = st.text_input(
                "Voice 2",
                value=pd_config.voice2,
                key=f"voice2_{pd_config.id}",
                help="You can use Elevenlabs voice ID",
            )

            if st.button("Save Config", key=f"btn_save{pd_config.id}"):
                try:
                    # pd_config attributes are already updated by st.multiselect direct assignment

                    # Debug prints (reading directly from pd_config)
                    st.write(f"DEBUG (Using st.multiselect): Saving template '{pd_config.name}' (ID: {pd_config.id})")
                    st.write(f"DEBUG (Using st.multiselect): Person 1 Roles: {pd_config.person1_role}")
                    st.write(f"DEBUG (Using st.multiselect): Person 2 Roles: {pd_config.person2_role}")
                    st.write(f"DEBUG (Using st.multiselect): Conversation Style: {pd_config.conversation_style}")
                    st.write(f"DEBUG (Using st.multiselect): Engagement Techniques: {pd_config.engagement_technique}")
                    st.write(f"DEBUG: Dialogue Structure: {pd_config.dialogue_structure}")
                    
                    pd_config.save()
                    st.toast("Podcast template saved")
                except Exception as e:
                    st.error(e)

            if st.button("Duplicate Config", key=f"btn_duplicate{pd_config.id}"):
                pd_config.name = f"{pd_config.name} - Copy"
                pd_config.id = None
                pd_config.save()
                st.rerun()

            if st.button("Delete Config", key=f"btn_delete{pd_config.id}"):
                pd_config.delete()
                st.rerun()
