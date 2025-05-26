from open_notebook.domain.models import model_manager
from open_notebook.models.image_to_text_models import ImageToTextModel
from loguru import logger

def get_text_from_image(image_path: str, prompt: str, mime_type: str = "image/jpeg") -> str:
    """
    Generates a textual description of an image using the configured Image-to-Text model.

    Args:
        image_path: The local path to the image file.
        prompt: The prompt to guide the image description.
        mime_type: The MIME type of the image (e.g., "image/jpeg", "image/png").

    Returns:
        The generated text description or an error message if processing fails.
    """
    try:
        image_model = model_manager.image_to_text_model # Accesses the default via ModelManager
        if not image_model:
            logger.warning("No Image-to-Text model is configured as default.")
            return "Error: No Image-to-Text model configured."

        if not isinstance(image_model, ImageToTextModel):
            logger.error(f"Configured default image model is not an ImageToTextModel instance: {type(image_model)}")
            return "Error: Invalid Image-to-Text model configuration."

        logger.info(f"Using Image-to-Text model: {image_model.model_name} for image: {image_path} with prompt: '{prompt}'")
        description = image_model.generate_text_from_image(image_path=image_path, prompt=prompt, mime_type=mime_type)
        logger.info(f"Generated description: {description[:100]}...") # Log a snippet
        return description

    except ValueError as ve:
        logger.error(f"ValueError in image-to-text tool: {ve}")
        return f"Error: {str(ve)}"
    except Exception as e:
        logger.error(f"Unexpected error in image-to-text tool processing {image_path}: {e}", exc_info=True)
        return f"Error: An unexpected error occurred while processing the image."

# Example (for direct testing if needed):
# if __name__ == '__main__':
#     # This requires your environment to be set up (e.g., OPENROUTER_API_KEY)
#     # and a default image-to-text model to be configured in your database via the UI.
#     # You would also need a dummy image file, e.g., create 'test_image.jpg'.
#     # with open("test_image.jpg", "wb") as f:
#     #     # A tiny valid JPEG (1x1 pixel black)
#     #     f.write(bytes.fromhex("FFD8FFE000104A46494600010100000100010000FFDB0043000101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101FFC00011080001000103012200021101031101FFC4001F0000010501010101010100000000000000000102030405060708090A0BFFDA000C03010002110311003F00F7B1BFD9"))
#     print(get_text_from_image("test_image.jpg", "Describe this image.", "image/jpeg")) 