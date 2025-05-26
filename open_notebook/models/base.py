from dataclasses import dataclass
from typing import Optional

@dataclass
class BaseModel:
    """
    A base class for all model types, holding common attributes.
    """
    model_name: Optional[str] = None
    # Other common attributes can be added here later if needed 