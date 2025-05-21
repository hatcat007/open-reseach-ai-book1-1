"""
Classes for supporting different text to speech models
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TextToSpeechModel(ABC):
    """
    Abstract base class for text to speech models.
    """

    model_name: Optional[str] = None

    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        """
        Generates audio from text.
        """
        raise NotImplementedError


@dataclass
class OpenAITextToSpeechModel(TextToSpeechModel):
    model_name: str

    def synthesize(self, text: str) -> bytes:
        # Placeholder: Actual OpenAI TTS implementation would go here
        # from openai import OpenAI
        # client = OpenAI()
        # response = client.audio.speech.create(model=self.model_name, voice="alloy", input=text)
        # return response.content
        raise NotImplementedError("OpenAI TTS not yet implemented in this stub.")


@dataclass
class ElevenLabsTextToSpeechModel(TextToSpeechModel):
    model_name: str

    def synthesize(self, text: str) -> bytes:
        # Placeholder: Actual ElevenLabs TTS implementation would go here
        # from elevenlabs import Voice, VoiceSettings, generate
        # audio = generate(text=text, voice=Voice(voice_id=self.model_name), model='eleven_multilingual_v2')
        # return audio
        raise NotImplementedError("ElevenLabs TTS not yet implemented in this stub.")


@dataclass
class GeminiTextToSpeechModel(TextToSpeechModel):
    model_name: str

    def synthesize(self, text: str) -> bytes:
        # Placeholder: Actual Gemini TTS implementation would go here
        raise NotImplementedError("Gemini TTS not yet implemented in this stub.")


@dataclass
class HFInferenceTextToSpeechModel(TextToSpeechModel):
    """
    Text-to-speech model that uses the Hugging Face Inference API.
    Requires HF_API_KEY to be set in the environment.
    """

    model_name: str  # This will be the Hugging Face model ID, e.g., "facebook/mms-tts-eng"

    def synthesize(self, text: str) -> bytes:
        """
        Synthesizes audio from text using a Hugging Face Inference API model.
        The InferenceClient by default should return raw audio bytes for TTS task.
        """
        from huggingface_hub import InferenceClient
        import os

        client = InferenceClient(
            token=os.environ.get("HF_API_KEY")
        )

        # The text_to_speech method of InferenceClient is expected to return bytes.
        # Example: client.text_to_speech("Hello world!", model="facebook/mms-tts-eng")
        audio_bytes = client.text_to_speech(
            text,
            model=self.model_name
        )
        
        if not isinstance(audio_bytes, bytes):
            print(f"Unexpected result from HF TTS: {type(audio_bytes)}")
            raise ValueError("HF Inference API TTS did not return bytes.")
            
        return audio_bytes
