"""
Classes for supporting different language models
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatLiteLLM
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import ChatVertexAI
from langchain_google_vertexai.model_garden import ChatAnthropicVertex
from langchain_groq import ChatGroq
from langchain_ollama.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from pydantic import SecretStr
from loguru import logger

# future: is there a value on returning langchain specific models?


@dataclass
class LanguageModel(ABC):
    """
    Abstract base class for language models.
    """

    model_name: Optional[str] = None
    max_tokens: Optional[int] = 850
    temperature: Optional[float] = 1.0
    streaming: bool = True
    top_p: Optional[float] = 0.9
    kwargs: Dict[str, Any] = field(default_factory=dict)
    json: bool = False

    @abstractmethod
    def to_langchain(self) -> BaseChatModel:
        """
        Convert the language model to a LangChain chat model.
        """
        raise NotImplementedError


@dataclass
class OllamaLanguageModel(LanguageModel):
    """
    Language model that uses the Ollama chat model.
    """

    model_name: str
    base_url: str = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
    max_tokens: Optional[int] = 650
    json: bool = False

    def to_langchain(self) -> ChatOllama:
        """
        Convert the language model to a LangChain chat model.
        """
        return ChatOllama(
            # api_key="ollama",
            model=self.model_name,
            base_url=self.base_url,
            # keep_alive="10m",
            num_predict=self.max_tokens,
            temperature=self.temperature or 0.5,
            verbose=True,
            top_p=self.top_p,
        )


@dataclass
class VertexAnthropicLanguageModel(LanguageModel):
    """
    Language model that uses the Vertex Anthropic chat model.
    """

    model_name: str
    project: Optional[str] = os.environ.get("VERTEX_PROJECT", "no-project")
    location: Optional[str] = os.environ.get("VERTEX_LOCATION", "us-central1")

    def to_langchain(self) -> ChatAnthropicVertex:
        """
        Convert the language model to a LangChain chat model.
        """
        return ChatAnthropicVertex(
            model=self.model_name,
            project=self.project,
            location=self.location,
            max_tokens=self.max_tokens,
            streaming=False,
            kwargs=self.kwargs,
            top_p=self.top_p,
            temperature=self.temperature or 0.5,
        )


@dataclass
class LiteLLMLanguageModel(LanguageModel):
    """
    Language model that uses the LiteLLM chat model.
    """

    model_name: str

    def to_langchain(self) -> ChatLiteLLM:
        """
        Convert the language model to a LangChain chat model.
        """
        return ChatLiteLLM(
            model=self.model_name,
            temperature=self.temperature or 0.5,
            max_tokens=self.max_tokens,
            streaming=self.streaming,
            top_p=self.top_p,
        )


@dataclass
class VertexAILanguageModel(LanguageModel):
    """
    Language model that uses the Vertex AI chat model.
    """

    model_name: str
    project: Optional[str] = os.environ.get("VERTEX_PROJECT", "no-project")
    location: Optional[str] = os.environ.get("VERTEX_LOCATION", "us-central1")

    def to_langchain(self) -> ChatVertexAI:
        """
        Convert the language model to a LangChain chat model.
        """
        return ChatVertexAI(
            model=self.model_name,
            streaming=self.streaming,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            location=self.location,
            project=self.project,
            safety_settings=None,
            temperature=self.temperature or 0.5,
        )


@dataclass
class GeminiLanguageModel(LanguageModel):
    """
    Language model that uses the Gemini Family of chat models.
    """

    model_name: str

    def to_langchain(self) -> ChatGoogleGenerativeAI:
        """
        Convert the language model to a LangChain chat model.
        """
        return ChatGoogleGenerativeAI(
            model=self.model_name,
            max_tokens=self.max_tokens,
            temperature=self.temperature or 0.5,
        )


@dataclass
class OpenRouterLanguageModel(LanguageModel):
    """
    Language model that uses the OpenAI chat model.
    """

    model_name: str

    def to_langchain(self) -> ChatOpenAI:
        """
        Convert the language model to a LangChain chat model for Open Router.
        """
        kwargs = self.kwargs
        if self.json:
            kwargs["response_format"] = {"type": "json_object"}

        return ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature or 0.5,
            base_url=os.environ.get(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ),
            max_tokens=self.max_tokens,
            model_kwargs=kwargs,
            streaming=self.streaming,
            api_key=SecretStr(os.environ.get("OPENROUTER_API_KEY", "openrouter")),
            top_p=self.top_p,
        )


@dataclass
class GroqLanguageModel(LanguageModel):
    """
    Language model that uses the Groq chat model.
    """

    model_name: str

    def to_langchain(self) -> ChatGroq:
        """
        Convert the language model to a LangChain chat model for Groq.
        """
        kwargs = self.kwargs
        kwargs["top_p"] = self.top_p

        return ChatGroq(
            model=self.model_name,
            temperature=self.temperature or 0.5,
            max_tokens=self.max_tokens,
            model_kwargs=kwargs,
            stop_sequences=None,
        )


@dataclass
class XAILanguageModel(LanguageModel):
    """
    Language model that uses the OpenAI chat model for X.AI.
    """

    model_name: str

    def to_langchain(self) -> ChatOpenAI:
        """
        Convert the language model to a LangChain chat model.
        """
        kwargs = self.kwargs
        if self.json:
            kwargs["response_format"] = {"type": "json_object"}

        return ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature or 0.5,
            base_url=os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1"),
            max_tokens=self.max_tokens,
            model_kwargs=kwargs,
            streaming=self.streaming,
            api_key=SecretStr(os.environ.get("XAI_API_KEY", "xai")),
            top_p=self.top_p,
        )


@dataclass
class AnthropicLanguageModel(LanguageModel):
    """
    Language model that uses the Anthropic chat model.
    """

    model_name: str

    def to_langchain(self) -> ChatAnthropic:
        """
        Convert the language model to a LangChain chat model.
        """
        return ChatAnthropic(  # type: ignore[call-arg]
            model_name=self.model_name,
            max_tokens_to_sample=self.max_tokens or 850,
            model_kwargs=self.kwargs,
            streaming=False,
            timeout=30,
            top_p=self.top_p,
            temperature=self.temperature or 0.5,
        )


@dataclass
class OpenAILanguageModel(LanguageModel):
    """
    Language model that uses the OpenAI chat model.
    """

    model_name: str

    def to_langchain(self) -> ChatOpenAI:
        """
        Convert the language model to a LangChain chat model.
        """

        kwargs = self.kwargs.copy()  # Make a copy to avoid modifying the original
        if self.json:
            kwargs["response_format"] = {"type": "json_object"}

        return ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature or 0.5,
            streaming=self.streaming,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            model_kwargs=kwargs,
        )


@dataclass
class LMStudioLanguageModel(LanguageModel):
    """
    Language model that uses LM Studio via LiteLLM.
    """

    model_name: str  # This will be the model identifier within LM Studio, e.g., "llama-3-8b-instruct"

    def to_langchain(self) -> ChatLiteLLM:
        """
        Convert the language model to a LangChain chat model for LM Studio.
        LM_STUDIO_API_BASE environment variable should be set to the LM Studio server address.
        (e.g., http://localhost:1234/v1)
        """
        # LiteLLM will automatically pick up LM_STUDIO_API_BASE from environment variables
        # The API key LM_STUDIO_API_KEY is optional and also picked up from env if set.
        return ChatLiteLLM(
            model=f"lm_studio/{self.model_name}",
            temperature=self.temperature or 0.5,
            max_tokens=self.max_tokens,
            streaming=self.streaming,
            top_p=self.top_p,
            # LiteLLM handles api_base and api_key via environment variables for LM Studio
        )


@dataclass
class HFInferenceLanguageModel(LanguageModel):
    """
    Language model that uses the Hugging Face Inference API.
    Requires HF_API_KEY (or HUGGING_FACE_HUB_TOKEN) to be set in the environment.
    """

    model_name: str # This will be the Hugging Face model ID, e.g., "mistralai/Mistral-7B-Instruct-v0.1"
    # streaming is not reliably supported by all models on HF Inference API through ChatHuggingFace in the same way
    # It's better to set it to False for now or handle it carefully if a specific model supports it.
    streaming: bool = False # Default to False for HF Inference API general use

    def to_langchain(self) -> BaseChatModel:
        """
        Convert the language model to a LangChain chat model for Hugging Face Inference API.
        """
        hf_api_key = os.environ.get("HF_API_KEY") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        if not hf_api_key:
            # It's good practice to raise an error or log a warning if the key is missing,
            # as ChatHuggingFace might not complain immediately but fail at runtime.
            logger.warning("HF_API_KEY or HUGGING_FACE_HUB_TOKEN not found in environment for HFInferenceLanguageModel.")
            # Or raise ValueError("HF API Key not found")

        # Instantiate HuggingFaceEndpoint first
        endpoint_llm = HuggingFaceEndpoint(
            repo_id=self.model_name,
            task="text-generation", # Can also be "conversational" for some models
            huggingfacehub_api_token=hf_api_key, 
            temperature=self.temperature or 0.5,
            max_new_tokens=self.max_tokens,
            top_p=self.top_p,
            model_kwargs=self.kwargs,
            # streaming=self.streaming, # streaming for HuggingFaceEndpoint is handled differently if needed
        )
        
        # Then pass it to ChatHuggingFace
        return ChatHuggingFace(llm=endpoint_llm)
