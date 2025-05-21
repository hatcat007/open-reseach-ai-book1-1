from __future__ import annotations
import datetime
from typing import TYPE_CHECKING, List, Literal, Optional
from pydantic import Field
from open_notebook.domain.base import ObjectModel
from open_notebook.database.repository import repo_query # For fetching messages
from loguru import logger
from open_notebook.exceptions import DatabaseOperationError


if TYPE_CHECKING:
    from open_notebook.domain.notebook import ChatSession # Forward reference for type hinting

class ChatMessage(ObjectModel):
    table_name: ClassVar[str] = "chat_message"
    
    chat_session_id: str # Stores the full ID of the ChatSession (e.g., "chat_session:xyz123")
    sender: Literal["user", "ai"]
    content: str
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    order: Optional[int] = None # For explicit ordering if timestamp is not enough

    # Potential property to get the ChatSession object, if needed, though not strictly necessary
    # for basic message operations if chat_session_id is always populated correctly.
    # @property
    # def session(self) -> 'ChatSession':
    #     try:
    #         # Assuming ChatSession is in notebook.py, adjust import if moved
    #         from open_notebook.domain.notebook import ChatSession 
    #         return ChatSession.get(self.chat_session_id)
    #     except Exception as e:
    #         logger.error(f"Error fetching chat session {self.chat_session_id} for message {self.id}: {e}")
    #         raise DatabaseOperationError(e)

    def __lt__(self, other):
        if self.order is not None and other.order is not None:
            return self.order < other.order
        return self.timestamp < other.timestamp

# It might be useful to have a helper function here to get all messages for a session,
# or this logic can live as a method on the ChatSession model itself.
# For now, let's plan to add a method to ChatSession. 