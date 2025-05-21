"""
Classes for supporting different transcription models
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


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

    def transcribe(self, audio_file_path: str) -> str:
        """
        Transcribes an audio file using a Hugging Face Inference API model.
        """
        from huggingface_hub import InferenceClient
        import os

        client = InferenceClient(
            token=os.environ.get("HF_API_KEY")
        )

        # The InferenceClient for ASR expects bytes or a file path.
        # The example in HF docs for HF Inference provider shows passing the filepath directly.
        # client.automatic_speech_recognition("sample1.flac", model="openai/whisper-large-v3")
        # The output structure is like: `{"text": "Transcription result"}`
        
        # Ensure audio_file_path is a string, not a file-like object if it ever changes upstream
        if not isinstance(audio_file_path, str):
            # This would be an unexpected input type based on current usage
            # but good to be defensive. We might need to save a temp file if it's bytes.
            raise TypeError("audio_file_path must be a string path to the audio file for HFInferenceClient ASR.")

        result = client.automatic_speech_recognition(
            audio_file_path, 
            model=self.model_name
        )
        if isinstance(result, dict) and "text" in result:
            return result["text"]
        elif isinstance(result, str): # Some models/client versions might return str directly
            return result
        else:
            # Log the unexpected result or raise a more specific error
            print(f"Unexpected result from HF ASR: {result}")
            raise ValueError("Failed to transcribe audio or unexpected response format from HF Inference API.")
