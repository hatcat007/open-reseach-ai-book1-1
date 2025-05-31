import os

import yaml
from loguru import logger

# --- BEGIN PyTorch path patch ---
import torch
if hasattr(torch, 'classes'): # Check if torch.classes exists
    if hasattr(torch.classes, '__file__') and torch.classes.__file__ is not None: # Check if __file__ exists and is not None
        # More robust way if torch.classes.__file__ is available
        torch.classes.__path__ = [os.path.join(torch.__path__[0], torch.classes.__file__)]
    else:
        # Fallback if torch.classes.__file__ is not available or is None
        torch.classes.__path__ = []
# --- END PyTorch path patch ---

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
config_path = os.path.join(project_root, "open_notebook_config.yaml")

try:
    with open(config_path, "r") as file:
        CONFIG = yaml.safe_load(file)
except Exception:
    logger.critical("Config file not found, using empty defaults")
    logger.debug(f"Looked in {config_path}")
    CONFIG = {}

# ROOT DATA FOLDER
DATA_FOLDER = "./data"

# LANGGRAPH CHECKPOINT FILE
sqlite_folder = f"{DATA_FOLDER}/sqlite-db"
os.makedirs(sqlite_folder, exist_ok=True)
LANGGRAPH_CHECKPOINT_FILE = f"{sqlite_folder}/checkpoints.sqlite"

# UPLOADS FOLDER
UPLOADS_FOLDER = f"{DATA_FOLDER}/uploads"
os.makedirs(UPLOADS_FOLDER, exist_ok=True)
