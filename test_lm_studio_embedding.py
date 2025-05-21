import os
import sys
from dotenv import load_dotenv
from loguru import logger

# Add the project root to the Python path to allow importing open_notebook
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
sys.path.insert(0, project_root)

try:
    from open_notebook.models.embedding_models import LMStudioEmbeddingModel
except ImportError as e:
    logger.error(f"Failed to import LMStudioEmbeddingModel: {e}")
    logger.error("Please ensure that the script is run from the root of the 'open-reseach ai book1' project,")
    logger.error("or that the open_notebook package is correctly installed and accessible in your PYTHONPATH.")
    sys.exit(1)

# Configure logger
logger.remove()  # Remove default handler
logger.add(sys.stderr, level="DEBUG") # Add a new handler with DEBUG level

def test_lm_studio_embedding():
    """
    Tests the LMStudioEmbeddingModel.
    """
    load_dotenv() # Load .env file if present, for LM_STUDIO_API_BASE

    api_base = os.environ.get("LM_STUDIO_API_BASE")
    if not api_base:
        logger.error("LM_STUDIO_API_BASE is not set. Please set it as an environment variable.")
        logger.info("For example: export LM_STUDIO_API_BASE=\"http://localhost:1234/v1\"")
        return

    logger.info(f"Using LM_STUDIO_API_BASE: {api_base}")
    
    # --- IMPORTANT: Replace this with the actual model identifier from your LM Studio ---
    # For example, if you have 'nomic-ai/nomic-embed-text-v1.5' loaded in LM Studio:
    # model_identifier = "nomic-ai/nomic-embed-text-v1.5" 
    # Or, if it's a GGUF file like 'nomic-embed-text-v1.5.Q8_0.gguf', 
    # check how it's listed in LM Studio's local server UI / model selection.
    # LiteLLM might expect just the model name without the full GGUF path/filename.
    # Sometimes, it's the folder name containing the model if LM Studio organizes it that way.
    #
    # Common models:
    # "nomic-ai/nomic-embed-text-v1.5" (if downloaded via LM Studio search)
    # "Salesforce/SFR-Embedding-Mistral" (check exact identifier in LM Studio)
    # "BAAI/bge-large-en-v1.5" (check exact identifier in LM Studio)
    #
    # Verify the exact model name available and selected in your running LM Studio instance.
    # You might need to adjust this based on what LM Studio reports or how LiteLLM needs it.
    lm_studio_model_name = "nomic-ai/nomic-embed-text-v1.5" # Replace if needed!
    # ------------------------------------------------------------------------------------

    logger.info(f"Attempting to use LM Studio model: {lm_studio_model_name}")

    try:
        # Instantiate the model
        # The model_name passed here is the specific identifier for the model in LM Studio
        embedding_model = LMStudioEmbeddingModel(model_name=lm_studio_model_name)
        
        sample_text = "Hello from the test script! This is a test for LM Studio embeddings."
        logger.info(f"Embedding sample text: \"{sample_text}\"")
        
        # Generate embedding
        embedding_vector = embedding_model.embed(sample_text)
        
        if embedding_vector:
            logger.success("Successfully generated embedding!")
            logger.info(f"Embedding vector (first 10 elements): {embedding_vector[:10]}")
            logger.info(f"Embedding vector dimension: {len(embedding_vector)}")
        else:
            logger.error("Failed to generate embedding. The result was empty.")
            
    except ValueError as ve:
        logger.error(f"ValueError during embedding test: {ve}")
        if "LM_STUDIO_API_BASE environment variable not set" in str(ve):
            logger.info("Please ensure LM_STUDIO_API_BASE is correctly set before running the script.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the embedding test: {e}")
        logger.exception("Traceback:")

if __name__ == "__main__":
    test_lm_studio_embedding() 