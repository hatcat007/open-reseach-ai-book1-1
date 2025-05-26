from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union, Tuple, Literal
import os
from dotenv import load_dotenv
import sys
from fastapi.middleware.cors import CORSMiddleware
import datetime
from fastapi import Depends
import logging
from sblpy.async_connection import AsyncSurrealConnection as AsyncSurreal

# Add project root to sys.path to allow imports from open_notebook
# This is a common pattern when running a script from a subdirectory
# Adjust the number of '..' if the script is moved deeper
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables from .env file at the project root
# The .env file should contain SURREAL_ADDRESS, SURREAL_PORT, etc.
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

# Now we can import from open_notebook
# Assuming Note and Source are also in notebook.py or accessible via open_notebook.domain
from open_notebook.domain.notebook import Notebook, Note, Source, Asset, ChatSession, Task # Note: Source and Note are in notebook.py
from open_notebook.domain.chat import ChatMessage # Added ChatMessage
from open_notebook.domain.models import model_manager # Added model_manager
from open_notebook.exceptions import NotFoundError, DatabaseOperationError, InvalidInputError
from open_notebook.utils import generate_id # For creating new IDs if not handled by .save()
from open_notebook.models.llms import LanguageModel # Added for type hinting

# LangChain message imports
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

app = FastAPI(
    title="Open Notebook API",
    description="API for interacting with Open Notebook data (Notebooks, Sources, Notes)",
    version="0.1.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

# --- Request Models (for POST/PUT data validation) ---
class NotebookCreateRequest(BaseModel):
    name: str # Changed from title to match Notebook model field
    description: Optional[str] = None # Changed from summary

class NotebookUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    archived: Optional[bool] = None

# --- Source Request Models ---
class SourceCreateRequest(BaseModel):
    type: str # e.g., 'url', 'text', 'file' - matches Source.asset.source_type or a direct field on Source
    content: str
    title: Optional[str] = None
    # Asset related fields if type is 'file' or 'url' might be handled differently or passed here
    # For simplicity, matching React/frontend/src/services/api.ts addSource parameters

class SourceUpdateRequest(BaseModel):
    title: Optional[str] = None
    # Other updatable fields for a source?

# --- Note Request Models ---
class NoteCreateRequest(BaseModel):
    title: str
    content: str
    # note_type is likely 'human' by default when created via API like this

class NoteUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    # note_type: Optional[Literal["human", "ai"]] = None # If updatable

# --- Chat Request Models ---
class ChatSessionCreateRequest(BaseModel):
    title: Optional[str] = None # Title for the new chat session

class ChatMessageCreateRequest(BaseModel):
    content: str # Content of the user's message

# --- Task Request Models ---
class TaskCreateRequest(BaseModel):
    description: str
    notebook_id: str # To associate task with a notebook
    due_date: Optional[datetime.datetime] = None
    order: Optional[int] = None
    status: Optional[Literal["todo", "in_progress", "completed"]] = "todo"

class TaskUpdateRequest(BaseModel):
    description: Optional[str] = None
    due_date: Optional[datetime.datetime] = None
    order: Optional[int] = None
    status: Optional[Literal["todo", "in_progress", "completed"]] = None

# --- Response Models (using existing domain models directly for now) ---
# FastAPI will automatically convert Pydantic models like Notebook, Note, Source to JSON responses.
# If specific response structures are needed, define them here.

# --- Utility to get full ID ---
def get_full_id(table_name: str, id_part: str) -> str:
    # If id_part already seems to be a full ID (e.g., "table:value"), use it directly.
    # This handles cases where the client might send a full ID or just the specific part.
    if ':' in id_part:
        # Optional: could add a check here to see if id_part.startswith(table_name + ':')
        return id_part
    return f"{table_name}:{id_part}"

# --- Database Connection Dependency ---
# Global variable to hold the database client instance
_db_client: Optional[AsyncSurreal] = None

async def get_db_conn() -> AsyncSurreal:
    global _db_client
    if _db_client is None:
        host = os.getenv("SURREAL_ADDRESS", "localhost")
        # Default SurrealDB port is 8000, not 8501 (which is often for apps like Streamlit/FastAPI http)
        port = int(os.getenv("SURREAL_PORT", "8000")) 
        user = os.getenv("SURREAL_USER", "root")
        password = os.getenv("SURREAL_PASS", "root")
        db_name = os.getenv("SURREAL_DB", "open_notebook")
        namespace = os.getenv("SURREAL_NS", "open_notebook_ns")
        
        client = AsyncSurreal(f"ws://{host}:{port}/rpc")
        try:
            await client.connect()
            await client.signin({"user": user, "pass": password})
            await client.use(namespace, db_name)
            _db_client = client
            # If your ObjectModel classes expect ObjectModel.db to be set globally:
            # from open_notebook.domain.base import ObjectModel
            # ObjectModel.db = _db_client 
            # This line above is crucial if your domain methods don't use the passed `db` parameter
            # but rely on a class-level `db` attribute.
            logging.info(f"Successfully connected to SurrealDB: ns={namespace}, db={db_name}")
        except Exception as e:
            logging.error(f"Failed to connect to SurrealDB: {e}")
            # Depending on your policy, you might raise an HTTPException here
            # or let connecting endpoints fail if _db_client remains None.
            # For now, we'll let it try to connect once. If it fails, endpoints will likely fail.
            pass # Or raise HTTPException(status_code=503, detail="Database not available")
    
    if _db_client is None:
        # This means the initial connection attempt failed or was skipped.
        raise HTTPException(status_code=503, detail="Database connection is not available.")
    
    return _db_client

@app.on_event("shutdown")
async def shutdown_db_client_event():
    global _db_client
    if _db_client:
        await _db_client.close()
        _db_client = None
        logging.info("SurrealDB connection closed.")

# --- Notebook Endpoints ---
@app.post("/api/notebooks", response_model=Notebook, status_code=status.HTTP_201_CREATED)
async def create_notebook_endpoint(notebook_data: NotebookCreateRequest):
    try:
        # The Notebook model expects 'name' and 'description'
        notebook = Notebook(name=notebook_data.name, description=notebook_data.description or "")
        notebook.save() # save() method handles ID generation and timestamps
        return notebook
    except InvalidInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/notebooks", response_model=List[Notebook])
async def get_all_notebooks_endpoint():
    try:
        return Notebook.get_all()
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/notebooks/{notebook_short_id}", response_model=Notebook)
async def get_notebook_endpoint(notebook_short_id: str):
    try:
        full_id = get_full_id(Notebook.table_name, notebook_short_id)
        return Notebook.get(full_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.put("/api/notebooks/{notebook_short_id}", response_model=Notebook)
async def update_notebook_endpoint(notebook_short_id: str, notebook_data: NotebookUpdateRequest):
    try:
        full_id = get_full_id(Notebook.table_name, notebook_short_id)
        notebook = Notebook.get(full_id)
        update_data = notebook_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(notebook, key, value)
        notebook.save()
        return notebook
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.delete("/api/notebooks/{notebook_short_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook_endpoint(notebook_short_id: str):
    try:
        full_id = get_full_id(Notebook.table_name, notebook_short_id)
        notebook = Notebook.get(full_id)
        notebook.delete() # Assuming ObjectModel has a delete method
        return
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# --- Notes Endpoints ---
@app.get("/api/notebooks/{notebook_short_id}/notes", response_model=List[Note])
async def get_notes_for_notebook_endpoint(notebook_short_id: str):
    try:
        notebook_full_id = get_full_id(Notebook.table_name, notebook_short_id)
        notebook = Notebook.get(notebook_full_id) # Ensure notebook exists
        # The Notebook class has a .notes property that fetches related notes
        return notebook.notes 
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notebook not found: {str(e)}")
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/api/notebooks/{notebook_short_id}/notes", response_model=Note, status_code=status.HTTP_201_CREATED)
async def create_note_for_notebook_endpoint(notebook_short_id: str, note_data: NoteCreateRequest):
    try:
        notebook_full_id = get_full_id(Notebook.table_name, notebook_short_id)
        # Ensure notebook exists before adding a note to it
        Notebook.get(notebook_full_id) 

        note = Note(
            title=note_data.title,
            content=note_data.content,
            note_type='human' # Default for user-created notes
            # id will be generated by ObjectModel.save() or SurrealDB
        )
        note.save() # This should save the note and assign an ID
        note.add_to_notebook(notebook_full_id) # Relate it to the notebook
        return note
    except NotFoundError as e: # For notebook not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notebook not found: {str(e)}")
    except InvalidInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.put("/api/notebooks/{notebook_short_id}/notes/{note_short_id}", response_model=Note)
async def update_note_endpoint(notebook_short_id: str, note_short_id: str, note_data: NoteUpdateRequest):
    try:
        note_full_id = get_full_id(Note.table_name, note_short_id)
        note = Note.get(note_full_id)

        # Check if the note belongs to the given notebook - this might require an extra query or different logic
        # For now, assuming direct update if note is found. Add verification if needed.

        update_data = note_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(note, key, value)
        note.save()
        return note
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.delete("/api/notebooks/{notebook_short_id}/notes/{note_short_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note_endpoint(notebook_short_id: str, note_short_id: str):
    try:
        # Optional: Verify notebook exists
        # notebook_full_id = get_full_id(Notebook.table_name, notebook_short_id)
        # Notebook.get(notebook_full_id)

        note_full_id = get_full_id(Note.table_name, note_short_id)
        note = Note.get(note_full_id)
        # Consider how to handle un-relating from notebook if delete only removes the note globally.
        # The `delete()` method on ObjectModel should handle the actual deletion from the database.
        note.delete()
        return
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# --- Sources Endpoints ---
@app.get("/api/notebooks/{notebook_short_id}/sources", response_model=List[Source])
async def get_sources_for_notebook_endpoint(notebook_short_id: str):
    try:
        notebook_full_id = get_full_id(Notebook.table_name, notebook_short_id)
        notebook = Notebook.get(notebook_full_id) # Ensure notebook exists
        # The Notebook class has a .sources property that fetches related sources
        return notebook.sources
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notebook not found: {str(e)}")
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/api/notebooks/{notebook_short_id}/sources", response_model=Source, status_code=status.HTTP_201_CREATED)
async def create_source_for_notebook_endpoint(notebook_short_id: str, source_data: SourceCreateRequest):
    try:
        notebook_full_id = get_full_id(Notebook.table_name, notebook_short_id)
        # Ensure notebook exists
        Notebook.get(notebook_full_id)

        asset_data = Asset(
            source_type=source_data.type
        )
        source_instance_params = {"title": source_data.title}

        if source_data.type == 'url':
            asset_data.url = source_data.content
            # Potentially fetch content from URL and put in full_text, or leave for a background task
            # For now, full_text will be None for URL type unless content is also meant for full_text
        elif source_data.type == 'text':
            source_instance_params["full_text"] = source_data.content
        elif source_data.type == 'file':
            asset_data.file_path = source_data.content
            # File content might be processed to extract text into full_text, often a separate step
        else:
            # Handle unknown type or raise error
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported source type: {source_data.type}")

        source_instance_params["asset"] = asset_data
        
        source = Source(**source_instance_params)

        source.save() # Save the source to get an ID
        source.add_to_notebook(notebook_full_id) # Relate it to the notebook
        return source
    except NotFoundError as e: # For notebook not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notebook not found: {str(e)}")
    except InvalidInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# Minimal PUT for Source (e.g., updating title)
@app.put("/api/notebooks/{notebook_short_id}/sources/{source_short_id}", response_model=Source)
async def update_source_endpoint(notebook_short_id: str, source_short_id: str, source_data: SourceUpdateRequest):
    try:
        source_full_id = get_full_id(Source.table_name, source_short_id)
        source = Source.get(source_full_id)
        # Add verification if this source belongs to the notebook_short_id if necessary

        if source_data.title is not None:
            source.title = source_data.title
        # Add other updatable fields here
        source.save()
        return source
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.delete("/api/notebooks/{notebook_short_id}/sources/{source_short_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source_endpoint(notebook_short_id: str, source_short_id: str):
    try:
        source_full_id = get_full_id(Source.table_name, source_short_id)
        source = Source.get(source_full_id)
        # Consider how to handle un-relating from notebook if delete only removes the source globally.
        source.delete()
        return
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# --- Chat Endpoints ---

@app.post("/api/notebooks/{notebook_short_id}/chats", response_model=ChatSession, status_code=status.HTTP_201_CREATED)
async def create_chat_session_endpoint(notebook_short_id: str, chat_data: ChatSessionCreateRequest):
    try:
        notebook_full_id = get_full_id(Notebook.table_name, notebook_short_id)
        # Ensure notebook exists
        Notebook.get(notebook_full_id)

        chat_session_title = chat_data.title or f"Chat on {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        chat_session = ChatSession(title=chat_session_title)
        chat_session.save()
        chat_session.relate_to_notebook(notebook_full_id) # Relate it to the notebook
        return chat_session
    except NotFoundError as e: # For notebook not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notebook not found: {str(e)}")
    except InvalidInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/notebooks/{notebook_short_id}/chats", response_model=List[ChatSession])
async def get_chat_sessions_for_notebook_endpoint(notebook_short_id: str):
    try:
        notebook_full_id = get_full_id(Notebook.table_name, notebook_short_id)
        notebook = Notebook.get(notebook_full_id)
        return notebook.chat_sessions # This property fetches related ChatSession objects
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notebook not found: {str(e)}")
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/chats/{chat_session_short_id}/messages", response_model=List[ChatMessage])
async def get_messages_for_chat_session_endpoint(chat_session_short_id: str):
    try:
        session_full_id = get_full_id(ChatSession.table_name, chat_session_short_id)
        chat_session = ChatSession.get(session_full_id)
        return chat_session.messages # This property fetches and sorts ChatMessage objects
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat session not found: {str(e)}")
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.post("/api/chats/{chat_session_short_id}/messages", response_model=List[ChatMessage]) # Returns both user and AI message
async def send_message_to_chat_session_endpoint(chat_session_short_id: str, message_data: ChatMessageCreateRequest):
    try:
        session_full_id = get_full_id(ChatSession.table_name, chat_session_short_id)
        chat_session = ChatSession.get(session_full_id)

        # 1. Create and save user's message
        user_message = ChatMessage(
            chat_session_id=chat_session.id,
            sender="user",
            content=message_data.content
            # timestamp and order will be handled by defaults or ChatMessage logic if any
        )
        user_message.save()

        # 2. Fetch message history for context
        history_messages_domain = chat_session.messages # This gets all messages, including the new user one
        langchain_history = []
        # Exclude the last message if it's the one we just added, to avoid duplication in context to LLM
        # Or, ensure chat_session.messages property re-fetches if not automatically updated post-save.
        # For safety, let's re-fetch or filter the current user message from history sent to LLM.
        # The chat_session.messages property does a fresh DB query, so it will include the new user_message.
        
        for msg in history_messages_domain:
            if msg.sender == "user":
                langchain_history.append(HumanMessage(content=msg.content))
            elif msg.sender == "ai":
                langchain_history.append(AIMessage(content=msg.content))
        
        # The last message in langchain_history is the current user's message.
        # Some models prefer the history *before* the current human message.
        # Others take the full list including the current one. Let's pass the full list.

        # 3. Get LangChain chat model
        llm_wrapper = model_manager.get_default_model("chat")
        if not llm_wrapper:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Default chat model not configured.")
        
        langchain_chat_model = llm_wrapper.to_langchain()
        if not langchain_chat_model:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load LangChain chat model.")

        # 4. Prepare input and invoke model
        # Consider adding a SystemMessage if your application uses one.
        # For example: final_input = [SystemMessage(content="You are a helpful research assistant.")] + langchain_history
        final_input = langchain_history # Pass the full history including the latest user message

        ai_response_lc = await langchain_chat_model.ainvoke(final_input)
        ai_content = ""
        if isinstance(ai_response_lc, AIMessage):
            ai_content = ai_response_lc.content
        elif isinstance(ai_response_lc, str): # Some simpler models might return str
            ai_content = ai_response_lc
        else:
            # Handle other response types or extract content appropriately
            logging.warning(f"Unexpected AI response type: {type(ai_response_lc)}. Content: {ai_response_lc}")
            ai_content = str(ai_response_lc) # Fallback

        # 5. Create and save AI's message
        ai_message = ChatMessage(
            chat_session_id=chat_session.id,
            sender="ai",
            content=ai_content
        )
        ai_message.save()

        # Return the new user message and the new AI message
        return [user_message, ai_message]

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat session not found: {str(e)}")
    except InvalidInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logging.error(f"Unexpected error in send_message_to_chat_session_endpoint: {e}")
        logging.exception(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while processing the message.")

class TransformationRequest(BaseModel):
    type: str
    params: Optional[Dict[str, Any]] = None

# Ensure SourceResponse includes the new fields.
# If it's defined above and based on the domain model, update the domain model first.
# For this example, let's assume SourceResponse is comprehensive or we adapt it.
# A more concrete SourceResponse might look like this if not already defined:
class SourceAssetResponse(BaseModel):
    file_path: Optional[str] = None
    url: Optional[str] = None
    source_type: Optional[str] = None

    class Config:
        from_attributes = True

class SourceResponse(BaseModel): # Assuming this is your primary response model for a Source
    id: str
    # Ensure field names match what frontend expects (e.g. notebookId vs notebook_id)
    # For consistency with typical JS, using camelCase, but match your existing models.
    notebook_id: str # map from notebookId if needed
    type: str
    content: Optional[str] = None
    title: Optional[str] = None
    created_at: datetime.datetime # map from createdAt
    updated_at: datetime.datetime # map from updatedAt
    status: Optional[str] = None
    asset: Optional[SourceAssetResponse] = None # Simplified, expand as needed
    
    # New fields for transformations
    simpleSummary: Optional[str] = Field(default=None, alias="simpleSummary")
    keyInsights: Optional[Union[List[str], str]] = Field(default=None, alias="keyInsights")
    reflectionQuestions: Optional[Union[List[str], str]] = Field(default=None, alias="reflectionQuestions")

    class Config:
        from_attributes = True
        populate_by_name = True # Changed from allow_population_by_field_name

    @classmethod
    def from_domain(cls, source_domain: Source):
        # Helper to convert domain Source to Pydantic SourceResponse
        # This assumes your domain Source attributes match or are mapped here
        asset_data = source_domain.asset.model_dump() if source_domain.asset else None
        return cls(
            id=source_domain.id, # Must be the full ID
            notebook_id=source_domain.notebook_id,
            type=source_domain.type,
            content=source_domain.content or source_domain.full_text, # Prioritize content
            title=source_domain.title,
            created_at=source_domain.created_at,
            updated_at=source_domain.updated_at,
            status=source_domain.status,
            asset=SourceAssetResponse(**asset_data) if asset_data else None,
            simpleSummary=getattr(source_domain, 'simple_summary', None),
            keyInsights=getattr(source_domain, 'key_insights', None),
            reflectionQuestions=getattr(source_domain, 'reflection_questions', None)
        )

@app.post("/api/sources/{source_id}/transformations", response_model=SourceResponse)
async def run_source_transformation_endpoint(
    source_id: str,
    request: TransformationRequest,
    db: AsyncSurreal = Depends(get_db_conn)
):
    full_source_id = get_full_id(source_id, "source")
    
    try:
        # Use the domain model's get method
        source_obj = Source.get(full_source_id, db=db)
    except Exception as e: # Catch generic Exception if NotFoundError is not specific enough or not raised by get
        # Log the exception e
        raise HTTPException(status_code=404, detail=f"Source not found: {str(e)}")

    if not source_obj: # Should be caught by exception, but as a safeguard
        raise HTTPException(status_code=404, detail="Source not found")

    content_to_process = source_obj.content or source_obj.full_text # Prefer 'content' if available
    if not content_to_process and request.type in ["summarize_text", "extract_entities", "generate_questions"]:
        raise HTTPException(status_code=400, detail=f"Source has no content for transformation type '{request.type}'.")

    # LLM interaction placeholder
    llm_model_name = "chat" # Default model
    if request.type == "summarize_text":
        llm_model_name = "summarize" # Or some specific model alias
    # ... other model selections for other types

    try:
        llm: LanguageModel = model_manager.get_model(llm_model_name)
    except KeyError: # If specific model not found, try fallback
        try:
            llm: LanguageModel = model_manager.get_model("chat") 
        except KeyError:
            raise HTTPException(status_code=500, detail=f"Required LLM ('{llm_model_name}' or 'chat') not available.")

    if request.type == "summarize_text":
        # Placeholder for actual summarization
        # summary_text = await llm.ainvoke(f"Summarize this: {content_to_process}") # Conceptual
        summary_text = f"Summarized: {content_to_process[:100]}..." if content_to_process else "No content to summarize."
        source_obj.simpleSummary = summary_text
    
    elif request.type == "extract_entities":
        # Placeholder for entity extraction
        # entities = await llm.ainvoke(f"Extract entities from: {content_to_process}") # Conceptual
        source_obj.keyInsights = [f"Entity from: {content_to_process[:30]}... 1", f"Entity from: {content_to_process[:30]}... 2"] if content_to_process else ["No content for entities."]
    
    elif request.type == "generate_questions":
        # Placeholder for question generation
        # questions = await llm.ainvoke(f"Generate questions about: {content_to_process}") # Conceptual
        source_obj.reflectionQuestions = [f"Question about: {content_to_process[:30]}... 1?", f"Question about: {content_to_process[:30]}... 2?"] if content_to_process else ["No content for questions."]
    
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported transformation type: {request.type}")

    try:
        # Persist changes using the domain model's save method or similar
        # This assumes .save() handles the DB interaction and updates the object in place or returns the updated one.
        source_obj.save(db=db) # Or however your domain objects are persisted
    except Exception as e:
        # Log error e
        raise HTTPException(status_code=500, detail=f"Failed to save source after transformation: {str(e)}")

    # Return the updated source object, converted to Pydantic response model
    return SourceResponse.from_domain(source_obj)

# --- Task Endpoints ---
@app.post("/api/notebooks/{notebook_short_id}/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task_for_notebook_endpoint(notebook_short_id: str, task_data: TaskCreateRequest):
    try:
        notebook_full_id = get_full_id(Notebook.table_name, notebook_short_id)
        # Ensure notebook exists
        Notebook.get(notebook_full_id) 

        task = Task(
            description=task_data.description,
            notebook=notebook_full_id, # Assign the notebook ID
            due_date=task_data.due_date,
            order=task_data.order,
            status=task_data.status or "todo"
        )
        task.save() # This should save the task and assign an ID
        # Unlike notes/sources, Task model has notebook_id directly.
        # If an edge relation was used, an equivalent to `task.add_to_notebook(notebook_full_id)` would be here.
        return task
    except NotFoundError as e: # For notebook not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notebook not found: {str(e)}")
    except InvalidInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/notebooks/{notebook_short_id}/tasks", response_model=List[Task])
async def get_tasks_for_notebook_endpoint(notebook_short_id: str):
    try:
        notebook_full_id = get_full_id(Notebook.table_name, notebook_short_id)
        notebook = Notebook.get(notebook_full_id) # Ensure notebook exists
        # The Notebook class has a .tasks property that fetches related tasks
        return notebook.tasks 
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notebook not found: {str(e)}")
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.put("/api/tasks/{task_short_id}", response_model=Task)
async def update_task_endpoint(task_short_id: str, task_data: TaskUpdateRequest):
    try:
        full_id = get_full_id(Task.table_name, task_short_id)
        task = Task.get(full_id)
        update_data = task_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(task, key, value)
        task.save()
        return task
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidInputError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.delete("/api/tasks/{task_short_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_endpoint(task_short_id: str):
    try:
        full_id = get_full_id(Task.table_name, task_short_id)
        task = Task.get(full_id)
        task.delete()
        return
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DatabaseOperationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # This is for local development. For production, use a proper ASGI server like Gunicorn with Uvicorn workers.
    # Ensure PYTHONPATH is set correctly if running this directly and `open_notebook` is not installed as a package.
    # Example: PYTHONPATH=$PYTHONPATH:/path/to/your/project uvicorn fastapi_server.main:app --reload --port 8000
    # The React frontend expects the API on port 8501/api, so this needs adjustment or proxying.
    # For now, the API will run on 8000, and api.ts uses 8501. These need to match.
    # Let's assume for now we run this on 8501 to match React's expectation for the /api part (handled by FastAPI routes)
    uvicorn.run(app, host="0.0.0.0", port=8501, log_level="info") 