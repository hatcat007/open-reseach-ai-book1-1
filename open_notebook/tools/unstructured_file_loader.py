from loguru import logger
from typing import List
from langchain_core.documents import Document # Using LangChain's Document
from langchain_community.document_loaders import UnstructuredFileLoader

# Define a simple Document-like structure for the placeholder
class Document:
    def __init__(self, page_content: str, metadata: dict = None):
        self.page_content = page_content
        self.metadata = metadata or {}

def load_file_content(file_path: str) -> List[Document]:
    """Loads content from various unstructured file types using UnstructuredFileLoader."""
    logger.info(f"Loading file content from: {file_path} using UnstructuredFileLoader")
    try:
        loader = UnstructuredFileLoader(file_path)
        documents = loader.load()
        logger.info(f"Successfully loaded {len(documents)} document(s) from {file_path}")
        return documents
    except Exception as e:
        logger.error(f"Error loading file {file_path} with UnstructuredFileLoader: {e}")
        # Return an empty list or a Document with error information, 
        # consistent with how other tools might handle failures.
        return [Document(page_content=f"Error processing file {file_path}: {e}", metadata={"source": file_path, "error": str(e)})] 