from typing import Optional
from open_notebook.domain.models import model_manager
from loguru import logger # Module-level logger

def speech_to_text(audio_file_path: str) -> str:
    """Transcribes an audio file using the configured speech-to-text model."""
    logger.info(f"--- speech_to_text function entered for file: {audio_file_path} ---")

    if not model_manager.speech_to_text:
        logger.warning("Speech-to-text model not selected/configured in ModelManager.")
        return "Error: Speech-to-text model not configured."
    
    speech_model = model_manager.speech_to_text
    model_identifier = getattr(speech_model, 'model_id_or_path', None) or \
                       getattr(speech_model, 'model_name', 'Unknown Model')

    logger.info(f"Processing speech_to_text for model: {model_identifier}, file: {audio_file_path}")

    transcription_result = None
    processed_text_output = None
    called_method_description = ""

    try:
        if hasattr(speech_model, 'transcribe') and callable(getattr(speech_model, 'transcribe')):
            # This will call a method like HFInferenceSpeechToTextModel.transcribe, 
            # which should handle its own client interactions and return a string (text or error).
            called_method_description = f"model object's 'transcribe' method"
            logger.info(f"Attempting transcription using {called_method_description}.")
            transcription_result = speech_model.transcribe(audio_file_path=audio_file_path)
            processed_text_output = transcription_result # Assuming model.transcribe returns string
        
        elif hasattr(speech_model, 'client') and speech_model.client:
            client = speech_model.client
            if hasattr(client, 'automatic_speech_recognition') and callable(getattr(client, 'automatic_speech_recognition')):
                called_method_description = f"client's 'automatic_speech_recognition' method"
                logger.info(f"Attempting transcription using {called_method_description} (will read file as bytes).")
                with open(audio_file_path, "rb") as f:
                    audio_data = f.read()
                # This typically returns a dict like {'text': '...'}
                transcription_result = client.automatic_speech_recognition(audio=audio_data)
                if isinstance(transcription_result, dict) and 'text' in transcription_result:
                    processed_text_output = transcription_result['text']
                elif isinstance(transcription_result, str): # Some clients might return string directly
                    processed_text_output = transcription_result
                else:
                    logger.error(f"Unexpected result format from {called_method_description} for {model_identifier}: {transcription_result!r}")
                    return f"Error: Unexpected result format from {called_method_description}."

            elif hasattr(client, 'recognize') and callable(getattr(client, 'recognize')):
                called_method_description = f"client's 'recognize' method"
                logger.info(f"Attempting transcription using {called_method_description} (passing file path).")
                # Assuming this returns a string or a dict that needs processing
                transcription_result = client.recognize(audio_file_path)
                if isinstance(transcription_result, dict) and 'text' in transcription_result: # Example handling
                    processed_text_output = transcription_result['text']
                elif isinstance(transcription_result, str):
                    processed_text_output = transcription_result
                else:
                    logger.error(f"Unexpected result format from {called_method_description} for {model_identifier}: {transcription_result!r}")
                    return f"Error: Unexpected result format from {called_method_description}."
            else:
                logger.error(f"Speech-to-text client for '{model_identifier}' does not have a recognized transcribe method (e.g., 'automatic_speech_recognition', 'recognize').")
                return "Error: Speech-to-text client method not found on client."
        else:
            logger.error(f"Speech-to-text model '{model_identifier}' has no 'transcribe' method and no configured client with known methods.")
            return "Error: No suitable transcription method found for the model."

        logger.debug(f"Raw transcription result via {called_method_description}: {transcription_result!r}")
        logger.debug(f"Processed text output: {processed_text_output!r}")

        if not isinstance(processed_text_output, str):
            logger.error(f"Processed output is not a string after {called_method_description} for {model_identifier}. Type: {type(processed_text_output)}")
            return f"Error: Transcription result processing failed."

        if processed_text_output.strip().lower().startswith("error"):
            logger.error(f"Transcription failed for {audio_file_path} using {model_identifier} (via {called_method_description}): {processed_text_output.strip()}")
            return processed_text_output.strip()
        else:
            logger.info(f"Successfully transcribed {audio_file_path} using {model_identifier} (via {called_method_description}).")
            return processed_text_output

    except Exception as e:
        logger.error(f"Exception during transcription of {audio_file_path} using {model_identifier} (attempted via {called_method_description or 'unknown method'}): {e}", exc_info=True)
        # Special handling for a common Hugging Face Inference API error string that might be returned directly
        if "Content type 'None' not supported" in str(e):
             return "Error: Transcription failed - Content type 'None' not supported by the model endpoint."
        return f"Error: Exception during transcription - {str(e)}" 