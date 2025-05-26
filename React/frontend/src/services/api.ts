import type { Notebook, Source, Note, ChatSession, ChatMessage, Task } from '../types';

const API_BASE_URL = 'http://localhost:8501/api'; // Replace if your Streamlit API is elsewhere

// --- Mock Data (to be phased out) ---
/*
const mockNotebooks: Notebook[] = [
  {
    id: '1',
    title: 'My First Research Notebook',
    createdAt: '2024-05-15T10:00:00Z',
    updatedAt: '2024-05-20T14:30:00Z',
    summary: 'Initial thoughts and findings on AI-driven content generation.',
    sourceCount: 2,
    noteCount: 2,
  },
  // ... other mock notebooks
];

const mockSources: Source[] = [
  // ... mock sources
];

const mockNotes: Note[] = [
  // ... mock notes
];

// Simulate API delay
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
*/

// --- Helper function for API calls ---
async function handleApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData;
    try {
      // Try to parse JSON error, but handle cases where it might not be JSON
      if (response.headers.get('content-type')?.includes('application/json')) {
        errorData = await response.json();
      } else {
        // If not JSON, use text. Useful for HTML error pages or plain text errors.
        const textError = await response.text();
        errorData = { message: textError || `HTTP error! status: ${response.status}` }; 
      }
    } catch (e) {
      // Fallback if parsing error response itself fails
      errorData = { message: `HTTP error! status: ${response.status} and failed to parse error response.` };
    }
    throw new Error(errorData?.message || `HTTP error! status: ${response.status}`);
  }
  // For 204 No Content, we might not have a JSON body to parse
  if (response.status === 204) {
    return Promise.resolve(undefined as unknown as T); // Return undefined or a specific marker for success
  }
  return response.json() as Promise<T>;
}

// --- Notebook API Functions ---
export const fetchNotebooks = async (): Promise<Notebook[]> => {
  const response = await fetch(`${API_BASE_URL}/notebooks`);
  return handleApiResponse<Notebook[]>(response);
};

export const fetchNotebookById = async (id: string): Promise<Notebook | undefined> => {
  try {
    const response = await fetch(`${API_BASE_URL}/notebooks/${id}`);
    if (response.status === 404) {
      console.warn(`Notebook with id ${id} not found from API.`);
      return undefined;
    }
    return handleApiResponse<Notebook>(response);
  } catch (error) {
    console.error(`Failed to fetch notebook ${id}:`, error);
    throw error;
  }
};

export const createNotebook = async (name: string, description?: string): Promise<Notebook> => {
  const response = await fetch(`${API_BASE_URL}/notebooks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
  return handleApiResponse<Notebook>(response);
};

// --- Source API Functions (Still Mocked - TODO: Update these) ---
const mockSources: Source[] = [
  { id: 'src101', notebookId: '1', type: 'url', content: 'https://example.com/ai-research-paper.pdf', title: 'AI Research Paper Example', createdAt: '2024-05-16T11:00:00Z', status: 'processed' },
  { id: 'src102', notebookId: '1', type: 'scraped_web_page', content: '# Scraped Page Content\nThis is markdown content from a scraped page about LLMs.', title: 'LLM Overview - Scraped', createdAt: '2024-05-17T15:30:00Z', status: 'processed' },
  { id: 'src201', notebookId: '2', type: 'text', content: 'Initial idea: Scrape sitemaps from e-commerce sites to analyze product structures.', title: 'E-commerce Sitemap Idea', createdAt: '2024-05-18T10:00:00Z', status: 'pending' },
];
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms)); // Keep delay for remaining mock functions

export const fetchSourcesByNotebookId = async (notebookId: string): Promise<Source[]> => {
  const response = await fetch(`${API_BASE_URL}/notebooks/${notebookId}/sources`);
  return handleApiResponse<Source[]>(response);
};

export const addSource = async (notebookId: string, type: Source['type'], content: string, title?: string): Promise<Source> => {
  const response = await fetch(`${API_BASE_URL}/notebooks/${notebookId}/sources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, content, title }),
  });
  return handleApiResponse<Source>(response);
};

// --- Note API Functions (Still Mocked - TODO: Update these) ---
const mockNotes: Note[] = [
  { id: 'note1', notebookId: '1', title: 'Key Takeaways from AI Paper', content: '## Summary\n The paper discusses advanced techniques...', createdAt: '2024-05-16T14:00:00Z', updatedAt: '2024-05-16T14:30:00Z', note_type: 'human' },
  { id: 'note2', notebookId: '1', title: 'AI-Generated Summary of LLM Overview', content: 'Large Language Models (LLMs) are powerful...', createdAt: '2024-05-17T16:00:00Z', updatedAt: '2024-05-17T16:05:00Z', note_type: 'ai' },
  { id: 'note3', notebookId: '2', title: 'Brainstorm: E-commerce Site Targets', content: '- Site A\n- Site B\n- Site C (requires login, might be tricky)', createdAt: '2024-05-18T10:30:00Z', updatedAt: '2024-05-18T10:30:00Z', note_type: 'human' }
];


export const fetchNotesByNotebookId = async (notebookId: string): Promise<Note[]> => {
  const response = await fetch(`${API_BASE_URL}/notebooks/${notebookId}/notes`);
  return handleApiResponse<Note[]>(response);
};

export const addNote = async (notebookId: string, title: string, content: string): Promise<Note> => {
  const response = await fetch(`${API_BASE_URL}/api/notebooks/${notebookId}/notes`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title, content, note_type: 'human' }), // Assuming default note_type
  });
  return handleApiResponse<Note>(response);
};

export const updateNote = async (noteId: string, title: string, content: string): Promise<Note> => {
  const response = await fetch(`${API_BASE_URL}/api/notes/${noteId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title, content }),
  });
  return handleApiResponse<Note>(response);
};

export const deleteNote = async (noteId: string): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/api/notes/${noteId}`, {
    method: 'DELETE',
  });
  await handleApiResponse(response); // true if no content is expected on success
};

// --- Chat API Functions ---

// Assuming ChatSession is similar to Notebook but might have fewer fields initially
// Replace with actual ChatSession type from your types.ts if different
/*
export interface ChatSession {
  id: string;
  title: string;
  notebook_id: string; // Or however it's linked in your backend response
  created_at: string;
  updated_at: string;
}

// Assuming ChatMessage type - replace with actual from types.ts
export interface ChatMessage {
  id: string;
  chat_session_id: string;
  sender: 'user' | 'ai';
  content: string;
  timestamp: string; // Or Date
  order?: number;
}
*/

export const createChatSession = async (notebookId: string, title?: string): Promise<ChatSession> => {
  const response = await fetch(`${API_BASE_URL}/notebooks/${notebookId}/chats`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  return handleApiResponse<ChatSession>(response);
};

export const getChatSessions = async (notebookId: string): Promise<ChatSession[]> => {
  const response = await fetch(`${API_BASE_URL}/notebooks/${notebookId}/chats`);
  return handleApiResponse<ChatSession[]>(response);
};

export const getChatMessages = async (chatSessionId: string): Promise<ChatMessage[]> => {
  const response = await fetch(`${API_BASE_URL}/chats/${chatSessionId}/messages`);
  return handleApiResponse<ChatMessage[]>(response);
};

// This endpoint in FastAPI returns a list containing the user's new message and the AI's response
export const postChatMessage = async (chatSessionId: string, content: string): Promise<ChatMessage> => {
  const response = await fetch(`${API_BASE_URL}/api/chats/${chatSessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ content, sender: 'user' }),
  });
  return handleApiResponse<ChatMessage>(response);
};

// New function for deleting a source
export const deleteSource = async (sourceId: string): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/api/sources/${sourceId}`, {
    method: 'DELETE',
  });
  // Assuming backend returns 204 No Content on success, or an error object
  await handleApiResponse(response); // true indicates expecting no content on success
};

export const updateSource = async (sourceId: string, data: Partial<Source>): Promise<Source> => {
  const response = await fetch(`${API_BASE_URL}/api/sources/${sourceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleApiResponse<Source>(response);
};

export interface TransformationParams { 
  [key: string]: any; 
}

export interface TransformationResult {
  // Define a flexible structure for now, assuming it might vary
  // Or, be more specific if you know what the backend will return, e.g.:
  // insights?: string[];
  // summary?: string;
  // generatedQuestions?: string[];
  resultText?: string; // General text output for now
  message?: string; // Optional message from backend
  [key: string]: any; // Allow other properties
}

export const runSourceTransformation = async (
  sourceId: string, 
  transformationType: string, 
  params?: TransformationParams
): Promise<TransformationResult> => {
  const response = await fetch(`${API_BASE_URL}/api/sources/${sourceId}/transformations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: transformationType, params: params || {} }),
  });
  return handleApiResponse<TransformationResult>(response);
};

// --- Task API Functions ---
export const fetchTasksByNotebookId = async (notebookId: string): Promise<Task[]> => {
  const response = await fetch(`${API_BASE_URL}/notebooks/${notebookId}/tasks`);
  return handleApiResponse<Task[]>(response);
};

export const createTask = async (notebookId: string, description: string, status?: 'todo' | 'in_progress' | 'completed', due_date?: string, order?: number): Promise<Task> => {
  const response = await fetch(`${API_BASE_URL}/notebooks/${notebookId}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description, notebook_id: notebookId, due_date, order, status: status || 'todo' }),
  });
  return handleApiResponse<Task>(response);
};

export const updateTask = async (taskId: string, updates: Partial<Omit<Task, 'id' | 'notebook_id' | 'created_at' | 'updated_at'>>): Promise<Task> => {
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  return handleApiResponse<Task>(response);
};

export const deleteTask = async (taskId: string): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`, {
    method: 'DELETE',
  });
  await handleApiResponse<void>(response);
};

// We can add more mock API functions here later (e.g., fetchNotebookById, createNotebook, etc.) 