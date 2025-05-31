from loguru import logger
from typing import List, Optional
from langchain_core.documents import Document # Using LangChain's Document
from langchain_unstructured import UnstructuredLoader # Updated import

# Define a simple Document-like structure for the placeholder
class Document:
    def __init__(self, page_content: str, metadata: dict = None):
        self.page_content = page_content
        self.metadata = metadata or {}

def load_file_content(file_path: str, file_name: Optional[str] = None) -> List[Document]:
    """Loads content from a file using UnstructuredFileLoader and returns a list of Document objects."""
    try:
        logger.info(f"Loading file content from: {file_path} using UnstructuredLoader") # Updated class name in log
        loader = UnstructuredLoader(file_path) # Use the new UnstructuredLoader
        documents = loader.load()
        logger.info(f"Successfully loaded {len(documents)} document(s) from {file_path}")
        
        # If file_name is provided, add it to the metadata of each document
        if file_name:
            for doc in documents:
                doc.metadata = doc.metadata or {} # Ensure metadata dict exists
                doc.metadata['source'] = file_name # Use 'source' as it's a common convention
                doc.metadata['file_path'] = file_path 
        elif documents: # Ensure documents list is not empty
             for doc in documents:
                doc.metadata = doc.metadata or {}
                doc.metadata['file_path'] = file_path # Keep file_path if no specific name given

        return documents
    except Exception as e:
        logger.error(f"Error loading file {file_path}: {e}")
        # Return a single document with error information
        return [Document(page_content=f"Error processing file {file_path}: {e}", metadata={"source": file_path, "error": str(e)})]

def load_pdf_content(file_path: str) -> List[Document]:
    """This function is a placeholder for PDF-specific loading if UnstructuredFileLoader isn't sufficient."""
    # Currently, UnstructuredFileLoader handles PDFs well.
    # If specific PDF processing is needed later, it can be implemented here.
    logger.info(f"Using generic load_file_content for PDF: {file_path}")
    return load_file_content(file_path) 