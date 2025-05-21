export interface Notebook {
  id: string;
  name: string;
  createdAt: string; // Or Date, if you prefer to parse it
  updatedAt: string; // Or Date
  description?: string;
  sourceCount?: number; // Optional count of sources
  noteCount?: number; // Optional count of notes
}

export interface Source {
  id: string;
  notebookId: string; // To link it back to a notebook
  type: 'url' | 'file' | 'text' | 'scraped_web_page';
  content?: string; // Made optional. Could be URL, file path, text content, or markdown from scrape
  title?: string; // Optional title, e.g., from webpage scrape
  createdAt: string;
  status?: 'processed' | 'pending' | 'error';
  // Add fields from the backend Asset model if they need to be directly accessed
  asset?: { // To mirror backend structure more closely for fallback
    file_path?: string;
    url?: string;
    source_type?: string; // This is already top-level as `type`
  };
  // Fields for processed data, to be displayed in accordions
  keyInsights?: string[] | string; // Can be a list of insights or a single block of text
  simpleSummary?: string;
  reflectionQuestions?: string[] | string; // Can be a list of questions or a single block of text
}

export interface Note {
  id: string;
  notebookId: string;
  title: string;
  content: string; // Markdown content
  createdAt: string;
  updatedAt: string;
  note_type?: 'ai' | 'human'; // To match your existing Python model
  // Add any other relevant fields, e.g., tags, summary_of_summary
}

export interface ChatSession {
  id: string; // Full ID, e.g., "chat_session:xyz123"
  title: string;
  // notebook_id is not directly on the ChatSession from backend, relation is via Notebook.chat_sessions
  created_at: string; // Assuming backend provides these (from ObjectModel)
  updated_at: string; // Assuming backend provides these (from ObjectModel)
  // Add other fields if your backend model for ChatSession has more
}

export interface ChatMessage {
  id: string; // Full ID, e.g., "chat_message:abc789"
  chat_session_id: string; // Full ID of the parent chat session
  sender: 'user' | 'ai';
  content: string;
  timestamp: string; // Or Date, if parsed. Backend uses datetime.datetime
  order?: number; // Optional explicit ordering
  // Add other fields if your backend model for ChatMessage has more
} 