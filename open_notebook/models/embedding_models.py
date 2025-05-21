"""
Classes for supporting different embedding models
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import requests
from loguru import logger
from litellm import embedding

# todo: add support for multiple embeddings (array)


@dataclass
class EmbeddingModel(ABC):
    """
    Abstract base class for language models.
    """

    model_name: Optional[str] = None

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        Generates an embedding
        """
        raise NotImplementedError


@dataclass
class OllamaEmbeddingModel(EmbeddingModel):
    model_name: str
    base_url: str = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")

    def __post_init__(self):
        if self.base_url is None:
            self.base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def embed(self, text: str) -> List[float]:
        """
        Embeds the content using Open AI embedding
        """
        text = text.replace("\n", " ")
        response = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model_name, "input": [text]},
        )
        return response.json()["embeddings"][0]


@dataclass
class GeminiEmbeddingModel(EmbeddingModel):
    model_name: str

    def embed(self, text: str) -> List[float]:
        import google.generativeai as genai

        """
        Embeds the content using Open AI embedding
        """
        model_name = (
            self.model_name
            if self.model_name.startswith("models/")
            else f"models/{self.model_name}"
        )
        result = genai.embed_content(model=model_name, content=text)

        return result["embedding"]


@dataclass
class VertexEmbeddingModel(EmbeddingModel):
    model_name: str = "textembedding-gecko@001"

    def embed(self, text: str) -> List[float]:
        from langchain_google_vertexai import VertexAIEmbeddings

        client = VertexAIEmbeddings(model_name=self.model_name)
        return client.embed_query(text)


@dataclass
class OpenAIEmbeddingModel(EmbeddingModel):
    model_name: str = "text-embedding-ada-002"

    def embed(self, text: str) -> List[float]:
        from openai import OpenAI

        """
        Embeds the content using Open AI embedding
        """
        # todo: make this Singleton
        client = OpenAI()
        text = text.replace("\n", " ")
        return (
            client.embeddings.create(input=[text], model=self.model_name)
            .data[0]
            .embedding
        )


@dataclass
class LMStudioEmbeddingModel(EmbeddingModel):
    """
    Embedding model that uses LM Studio via LiteLLM directly.
    Requires LM_STUDIO_API_BASE to be set in the environment,
    e.g., http://localhost:1234/v1
    The model_name should be the specific model identifier available in LM Studio,
    e.g., "nomic-ai/nomic-embed-text-v1.5".
    """

    model_name: str  # This will be the model identifier from LM Studio.

    def embed(self, text: str) -> List[float]:
        """
        Generates an embedding using an LM Studio model via LiteLLM.
        """
        api_base_url = os.environ.get("LM_STUDIO_API_BASE")
        if not api_base_url:
            logger.error("LM_STUDIO_API_BASE environment variable not set.")
            raise ValueError(
                "LM_STUDIO_API_BASE environment variable not set. "
                "Please set it to your LM Studio server address (e.g., http://localhost:1234/v1)"
            )

        # LiteLLM expects the model name to be prefixed with "lmstudio/" for LM Studio.
        # self.model_name will be the name as known in LM Studio, e.g., "nomic-ai/nomic-embed-text-v1.5"
        litellm_model_name = f"lmstudio/{self.model_name}"
        
        # For LM Studio, the API key is often optional or a placeholder like "lm-studio".
        # LiteLLM's documentation suggests setting api_key="lm-studio" if no specific key is required by the server.
        # If LM_STUDIO_API_KEY is set in the environment, use that.
        api_key_to_use = os.environ.get("LM_STUDIO_API_KEY", "lm-studio") # Using "lm-studio" as a fallback

        # Prefix model with 'openai/' when treating LM Studio as an OpenAI-compatible endpoint
        qualified_model_name = f"openai/{self.model_name}"

        logger.info(f"Attempting LM Studio embedding with model='{qualified_model_name}', api_base='{api_base_url}'")
        
        try:
            response = embedding(
                model=qualified_model_name, # Use openai/ prefix
                input=[text],
                api_base=api_base_url,
                api_key=api_key_to_use
            )
            logger.debug(f"Raw response from LM Studio embedding: {response}")
        except Exception as e:
            logger.error(f"Error during litellm.embedding call for LM Studio: {e}")
            # You might want to reraise or handle specific LiteLLM exceptions here
            raise

        # According to LiteLLM documentation, the response object for embeddings has a 'data' attribute,
        # which is a list of objects, each having an 'embedding' attribute.
        if response and hasattr(response, 'data') and response.data and len(response.data) > 0:
            first_embedding_object = response.data[0]
            if hasattr(first_embedding_object, "embedding") and isinstance(first_embedding_object.embedding, list):
                return first_embedding_object.embedding
            # Sometimes, the embedding might be directly in first_embedding_object if it's a dict (less common for new versions)
            elif isinstance(first_embedding_object, dict) and "embedding" in first_embedding_object and isinstance(first_embedding_object["embedding"], list):
                 return first_embedding_object["embedding"]
        
        logger.error(f"Failed to extract embedding from LM Studio response. Response structure not as expected: {response}")
        raise ValueError(f"Failed to extract embedding from LM Studio response. Unexpected data format or empty response: {response}")


@dataclass
class HFInferenceEmbeddingModel(EmbeddingModel):
    """
    Embedding model that uses the Hugging Face Inference API.
    Requires HF_API_KEY (or HUGGING_FACE_HUB_TOKEN) to be set in the environment.
    """

    model_name: str  # This will be the Hugging Face model ID, e.g., "sentence-transformers/all-MiniLM-L6-v2"

    def embed(self, text: str) -> List[float]:
        """
        Generates an embedding using a Hugging Face Inference API model.
        """
        from langchain_huggingface import HuggingFaceEndpointEmbeddings
        import os

        api_key = os.environ.get("HF_API_KEY") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        if not api_key:
            raise ValueError("HF_API_KEY or HUGGING_FACE_HUB_TOKEN environment variable not set.")

        client = HuggingFaceEndpointEmbeddings(
            huggingfacehub_api_token=api_key,
            model=self.model_name
        )
        return client.embed_query(text)
