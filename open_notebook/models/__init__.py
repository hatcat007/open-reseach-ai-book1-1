from typing import Dict, Type, Union, Optional

from open_notebook.models.embedding_models import (
    EmbeddingModel,
    GeminiEmbeddingModel,
    HFInferenceEmbeddingModel,
    LMStudioEmbeddingModel,
    OllamaEmbeddingModel,
    OpenAIEmbeddingModel,
    VertexEmbeddingModel,
)
from open_notebook.models.llms import (
    AnthropicLanguageModel,
    GeminiLanguageModel,
    GroqLanguageModel,
    HFInferenceLanguageModel,
    LanguageModel,
    LiteLLMLanguageModel,
    LMStudioLanguageModel,
    OllamaLanguageModel,
    OpenAILanguageModel,
    OpenRouterLanguageModel,
    VertexAILanguageModel,
    VertexAnthropicLanguageModel,
    XAILanguageModel,
)
from open_notebook.models.speech_to_text_models import (
    GroqSpeechToTextModel,
    HFInferenceSpeechToTextModel,
    OpenAISpeechToTextModel,
    SpeechToTextModel,
)
from open_notebook.models.text_to_speech_models import (
    ElevenLabsTextToSpeechModel,
    GeminiTextToSpeechModel,
    HFInferenceTextToSpeechModel,
    OpenAITextToSpeechModel,
    TextToSpeechModel,
)
from open_notebook.models.image_to_text_models import (
    ImageToTextModel,
    OpenrouterImageToTextModel,
)

ModelType = Union[LanguageModel, EmbeddingModel, SpeechToTextModel, TextToSpeechModel, ImageToTextModel]


ProviderMap = Dict[str, Type[ModelType]]

MODEL_CLASS_MAP: Dict[str, ProviderMap] = {
    "language": {
        "ollama": OllamaLanguageModel,
        "openrouter": OpenRouterLanguageModel,
        "vertexai-anthropic": VertexAnthropicLanguageModel,
        "litellm": LiteLLMLanguageModel,
        "lmstudio": LMStudioLanguageModel,
        "vertexai": VertexAILanguageModel,
        "anthropic": AnthropicLanguageModel,
        "openai": OpenAILanguageModel,
        "gemini": GeminiLanguageModel,
        "xai": XAILanguageModel,
        "groq": GroqLanguageModel,
        "huggingface": HFInferenceLanguageModel,
    },
    "embedding": {
        "openai": OpenAIEmbeddingModel,
        "gemini": GeminiEmbeddingModel,
        "vertexai": VertexEmbeddingModel,
        "ollama": OllamaEmbeddingModel,
        "lmstudio": LMStudioEmbeddingModel,
        "huggingface": HFInferenceEmbeddingModel,
    },
    "speech_to_text": {
        "openai": OpenAISpeechToTextModel,
        "groq": GroqSpeechToTextModel,
        "huggingface": HFInferenceSpeechToTextModel,
    },
    "text_to_speech": {
        "openai": OpenAITextToSpeechModel,
        "elevenlabs": ElevenLabsTextToSpeechModel,
        "gemini": GeminiTextToSpeechModel,
        "huggingface": HFInferenceTextToSpeechModel,
    },
    "image_to_text": {
        "openrouter": OpenrouterImageToTextModel,
    },
}

__all__ = [
    "MODEL_CLASS_MAP",
    "EmbeddingModel",
    "LanguageModel",
    "SpeechToTextModel",
    "TextToSpeechModel",
    "ImageToTextModel",
    "ModelType",
]
