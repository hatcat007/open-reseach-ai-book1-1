"""
Classes for supporting different transcription models
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any, Dict
import os

from huggingface_hub import InferenceClient
from loguru import logger # Add logger import


@dataclass
class SpeechToTextModel(ABC):
    """
    Abstract base class for speech to text models.
    """

    model_name: Optional[str] = None

    @abstractmethod
    def transcribe(self, audio_file_path: str) -> str:
        """
        Generates a text transcription from audio
        """
        raise NotImplementedError


@dataclass
class OpenAISpeechToTextModel(SpeechToTextModel):
    model_name: str

    def transcribe(self, audio_file_path: str) -> str:
        """
        Transcribes an audio file into text
        """
        from openai import OpenAI

        # todo: make this Singleton
        client = OpenAI()
        with open(audio_file_path, "rb") as audio:
            transcription = client.audio.transcriptions.create(
                model=self.model_name, file=audio
            )
            return transcription.text


@dataclass
class GroqSpeechToTextModel(SpeechToTextModel):
    model_name: str

    def transcribe(self, audio_file_path: str) -> str:
        """
        Transcribes an audio file into text
        """
        from groq import Groq

        # todo: make this Singleton
        client = Groq()
        with open(audio_file_path, "rb") as audio:
            transcription = client.audio.transcriptions.create(
                model=self.model_name, file=audio
            )
            return transcription.text


@dataclass
class HFInferenceSpeechToTextModel(SpeechToTextModel):
    """
    Speech-to-text model that uses the Hugging Face Inference API.
    Requires HF_API_KEY to be set in the environment.
    """

    model_name: str  # This will be the Hugging Face model ID, e.g., "openai/whisper-large-v3"
    client: any = None # Initialize client attribute
    model_id_or_path: Optional[str] = None # Store the model identifier

    def __post_init__(self):
        from huggingface_hub import InferenceClient
        from loguru import logger # Import logger
        import os # Ensure os is available

        api_key = os.getenv("HF_API_KEY")
        if not api_key:
            logger.error("HF_API_KEY not found in environment variables.")
            self.client = None
            return
        
        # Ensure model_name is set, fallback to model_id_or_path if necessary
        if not self.model_name and self.model_id_or_path:
            self.model_name = self.model_id_or_path
        elif not self.model_name:
            logger.error("Model name or ID is not set for HFInferenceSpeechToTextModel.")
            self.client = None
            return

        try:
            logger.info(f"Initializing InferenceClient for model: {self.model_name} with provider 'hf-inference' and Content-Type 'audio/mpeg'")
            self.client = InferenceClient(
                model=self.model_name, 
                token=api_key, 
                provider="hf-inference",
                headers={"Content-Type": "audio/mpeg"} # Explicitly set Content-Type
            )
        except Exception as e:
            logger.error(f"Failed to initialize InferenceClient for model {self.model_name}: {e}")
            self.client = None

    def transcribe(self, audio_file_path: str) -> str | None:
        if not self.client:
            logger.error(f"Speech-to-text client for model {self.model_name} is not available.")
            return "Speech-to-text client not available."

        try:
            with open(audio_file_path, "rb") as f:
                audio_data_bytes = f.read()
            
            logger.info(f"Transcribing audio file: {audio_file_path} using model {self.model_name}")
            
            # Call automatic_speech_recognition without the model argument here
            response = self.client.automatic_speech_recognition(audio_data_bytes)
            
            if isinstance(response, dict) and 'text' in response:
                transcript = response['text']
                logger.info(f"Successfully transcribed audio from {audio_file_path}")
                return transcript
            elif isinstance(response, str): # Sometimes it might directly return text or an error string
                 logger.warning(f"Transcription for {audio_file_path} returned a string: {response}")
                 # Check if the string response is the error message we've been seeing
                 if "Content type 'None' not supported" in response:
                     logger.error(f"Still receiving 'Content type None not supported' for {self.model_name}")
                     return f"Error: {response}"
                 return response # Assuming it's a direct transcript
            else:
                logger.error(f"Unexpected response format from transcription model {self.model_name} for {audio_file_path}: {response}")
                return f"Unexpected response format: {type(response)}"

        except Exception as e:
            # Check if the exception message itself contains the "Content type 'None' not supported"
            # This can help confirm if the issue persists even with the dedicated method.
            if "Content type 'None' not supported" in str(e):
                logger.error(f"HF ASR 'Content type None not supported' error persist for {self.model_name} with file {audio_file_path} using dedicated method (client initialized with model): {e}", exc_info=True)
            else:
                logger.error(f"Error during HF ASR transcription for {self.model_name} with file {audio_file_path} (client initialized with model): {e}", exc_info=True)
            return f"Error during transcription: {str(e)}"
