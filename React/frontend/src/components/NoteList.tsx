import React, { useEffect, useState, type FormEvent } from 'react';
import { fetchNotesByNotebookId, addNote, deleteNote, updateNote } from '../services/api';
import type { Note } from '../types';
import { Spinner, Alert, Button, Card, Stack, Modal, Form } from 'react-bootstrap';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface NoteListProps {
  notebookId: string;
}

const NoteList: React.FC<NoteListProps> = ({ notebookId }) => {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddNoteModal, setShowAddNoteModal] = useState<boolean>(false);
  const [newNoteTitle, setNewNoteTitle] = useState<string>('');
  const [newNoteContent, setNewNoteContent] = useState<string>('');
  const [isAddingNote, setIsAddingNote] = useState<boolean>(false);
  const [addNoteError, setAddNoteError] = useState<string | null>(null); // For add note modal

  const [showEditNoteModal, setShowEditNoteModal] = useState<boolean>(false);
  const [noteToEdit, setNoteToEdit] = useState<Note | null>(null);
  const [editNoteTitle, setEditNoteTitle] = useState<string>('');
  const [editNoteContent, setEditNoteContent] = useState<string>('');
  const [isEditingNote, setIsEditingNote] = useState<boolean>(false);
  const [editNoteError, setEditNoteError] = useState<string | null>(null);

  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState<boolean>(false);
  const [noteToDelete, setNoteToDelete] = useState<Note | null>(null);
  const [isDeletingNote, setIsDeletingNote] = useState<boolean>(false);
  const [deleteNoteError, setDeleteNoteError] = useState<string | null>(null);

  const loadNotes = async () => {
    if (!notebookId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchNotesByNotebookId(notebookId);
      setNotes(data);
    } catch (err) {
      setError('Failed to fetch notes.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNotes();
  }, [notebookId]);

  const handleShowAddNoteModal = () => {
    setAddNoteError(null);
    setNewNoteTitle('');
    setNewNoteContent('');
    setShowAddNoteModal(true);
  };

  const handleCloseAddNoteModal = () => {
    setShowAddNoteModal(false);
    setAddNoteError(null);
  };

  const handleAddNote = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!newNoteTitle.trim()) {
      setAddNoteError('Title is required.');
      return;
    }
    if (!newNoteContent.trim()) {
      setAddNoteError('Content is required.');
      return;
    }

    setIsAddingNote(true);
    setAddNoteError(null);

    try {
      await addNote(notebookId, newNoteTitle, newNoteContent);
      handleCloseAddNoteModal();
      await loadNotes(); // Reload notes to show the new one
    } catch (err) {
      setAddNoteError('Failed to add note. Please try again.');
      console.error(err);
    } finally {
      setIsAddingNote(false);
    }
  };

  const handleShowEditNoteModal = (note: Note) => {
    setNoteToEdit(note);
    setEditNoteTitle(note.title);
    setEditNoteContent(note.content);
    setEditNoteError(null);
    setShowEditNoteModal(true);
  };

  const handleCloseEditNoteModal = () => {
    setShowEditNoteModal(false);
    setNoteToEdit(null);
    setEditNoteError(null);
  };

  const handleUpdateNote = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!noteToEdit) {
      setEditNoteError('No note selected for editing.');
      return;
    }
    if (!editNoteTitle.trim()) {
      setEditNoteError('Title is required.');
      return;
    }
    if (!editNoteContent.trim()) {
      setEditNoteError('Content is required.');
      return;
    }

    setIsEditingNote(true);
    setEditNoteError(null);

    try {
      await updateNote(noteToEdit.id, editNoteTitle, editNoteContent);
      handleCloseEditNoteModal();
      await loadNotes();
    } catch (err) {
      setEditNoteError('Failed to update note. Please try again.');
      console.error(err);
    } finally {
      setIsEditingNote(false);
    }
  };

  const handleShowDeleteConfirmModal = (note: Note) => {
    setNoteToDelete(note);
    setDeleteNoteError(null);
    setShowDeleteConfirmModal(true);
  };

  const handleCloseDeleteConfirmModal = () => {
    setShowDeleteConfirmModal(false);
    setNoteToDelete(null);
    setDeleteNoteError(null);
  };

  const handleDeleteNote = async () => {
    if (!noteToDelete || !notebookId) return;
    setIsDeletingNote(true);
    setDeleteNoteError(null);
    try {
      await deleteNote(noteToDelete.id);
      handleCloseDeleteConfirmModal();
      await loadNotes();
    } catch (err) {
      setDeleteNoteError('Failed to delete note. Please try again.');
      console.error(err);
    } finally {
      setIsDeletingNote(false);
    }
  };

  if (loading && notes.length === 0) { // Show main loader only if no notes yet and not adding
    return (
      <div className="d-flex justify-content-center align-items-center py-5">
        <Spinner animation="border" variant="primary" role="status">
          <span className="visually-hidden">Loading notes...</span>
        </Spinner>
      </div>
    );
  }

  if (error && !showAddNoteModal && !showEditNoteModal && !showDeleteConfirmModal) { // Don't show main page error if modal is open
    return <Alert variant="danger">{error}</Alert>;
  }

  const getNoteTypeIcon = (type?: 'ai' | 'human') => {
    if (type === 'ai') return '🤖';
    if (type === 'human') return '🧑‍💻'; // Or '🤵' as you had
    return '📝'; // Default
  };

  return (
    <div className="mt-3">
      <Stack gap={3} className="mb-3 align-items-center flex-column flex-sm-row align-items-sm-center">
        <h3 className="mb-2 mb-sm-0">Notes</h3>
        <Button 
          variant="primary" 
          size="sm" 
          onClick={handleShowAddNoteModal}
          className="ms-sm-auto w-100 w-sm-auto"
        >
          <i className="bi bi-plus-lg me-1"></i> Add Note
        </Button>
      </Stack>

      <Modal show={showAddNoteModal} onHide={handleCloseAddNoteModal} centered backdrop="static">
        <Modal.Header closeButton>
          <Modal.Title>Add New Note</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {addNoteError && <Alert variant="danger" onClose={() => setAddNoteError(null)} dismissible>{addNoteError}</Alert>}
          <Form onSubmit={handleAddNote}>
            <Form.Group className="mb-3" controlId="noteTitle">
              <Form.Label>Title <span className="text-danger">*</span></Form.Label>
              <Form.Control 
                type="text" 
                value={newNoteTitle}
                onChange={(e) => setNewNoteTitle(e.target.value)}
                required
                disabled={isAddingNote}
                placeholder="Enter note title"
              />
            </Form.Group>
            <Form.Group className="mb-3" controlId="noteContent">
              <Form.Label>Content <span className="text-danger">*</span></Form.Label>
              <Form.Control 
                as="textarea" 
                rows={5}
                value={newNoteContent}
                onChange={(e) => setNewNoteContent(e.target.value)}
                required
                disabled={isAddingNote}
                placeholder="Enter note content (Markdown supported for display)"
              />
            </Form.Group>
            <Stack direction="horizontal" gap={2} className="justify-content-end">
              <Button variant="secondary" onClick={handleCloseAddNoteModal} disabled={isAddingNote}>
                Cancel
              </Button>
              <Button variant="primary" type="submit" disabled={isAddingNote}>
                {isAddingNote ? (
                  <>
                    <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" className="me-1"/>
                    Adding Note...
                  </>
                ) : 'Add Note'}
              </Button>
            </Stack>
          </Form>
        </Modal.Body>
      </Modal>

      <Modal show={showEditNoteModal} onHide={handleCloseEditNoteModal} centered backdrop="static">
        <Modal.Header closeButton>
          <Modal.Title>Edit Note</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {editNoteError && <Alert variant="danger" onClose={() => setEditNoteError(null)} dismissible>{editNoteError}</Alert>}
          <Form onSubmit={handleUpdateNote}>
            <Form.Group className="mb-3" controlId="editNoteTitle">
              <Form.Label>Title <span className="text-danger">*</span></Form.Label>
              <Form.Control 
                type="text" 
                value={editNoteTitle}
                onChange={(e) => setEditNoteTitle(e.target.value)}
                required
                disabled={isEditingNote}
              />
            </Form.Group>
            <Form.Group className="mb-3" controlId="editNoteContent">
              <Form.Label>Content <span className="text-danger">*</span></Form.Label>
              <Form.Control 
                as="textarea" 
                rows={5}
                value={editNoteContent}
                onChange={(e) => setEditNoteContent(e.target.value)}
                required
                disabled={isEditingNote}
              />
            </Form.Group>
            <Stack direction="horizontal" gap={2} className="justify-content-end">
              <Button variant="secondary" onClick={handleCloseEditNoteModal} disabled={isEditingNote}>
                Cancel
              </Button>
              <Button variant="primary" type="submit" disabled={isEditingNote}>
                {isEditingNote ? (
                  <>
                    <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" className="me-1"/>
                    Saving...
                  </>
                ) : 'Save Changes'}
              </Button>
            </Stack>
          </Form>
        </Modal.Body>
      </Modal>

      <Modal show={showDeleteConfirmModal} onHide={handleCloseDeleteConfirmModal} centered>
        <Modal.Header closeButton>
          <Modal.Title>Confirm Deletion</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {deleteNoteError && <Alert variant="danger" onClose={() => setDeleteNoteError(null)} dismissible>{deleteNoteError}</Alert>}
          <p>Are you sure you want to delete the note "<strong>{noteToDelete?.title}</strong>"?</p>
          <p className="text-muted small">This action cannot be undone.</p>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={handleCloseDeleteConfirmModal} disabled={isDeletingNote}>Cancel</Button>
          <Button variant="danger" onClick={handleDeleteNote} disabled={isDeletingNote}>
            {isDeletingNote ? (<><Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" className="me-1"/> Deleting...</>) : 'Delete Note'}
          </Button>
        </Modal.Footer>
      </Modal>

      {(() => {
        if (notes.length === 0 && !loading && !error) {
          return <Alert variant="info">No notes found for this notebook. Click "+ Add Note" to create one.</Alert>;
        }
        if (notes.length > 0) {
          return (
            <Stack gap={3}>
              {notes.map((note) => (
                <Card key={note.id}>
                  <Card.Header>
                    <Stack direction="horizontal" gap={2} className="align-items-start">
                      <span className="fs-5 me-2">{getNoteTypeIcon(note.note_type)}</span>
                      <Card.Title as="h5" className="mb-0 flex-grow-1 text-primary">
                        {note.title}
                      </Card.Title>
                      <small className="text-muted">
                        Updated: {new Date(note.updatedAt).toLocaleDateString()}
                      </small>
                    </Stack>
                  </Card.Header>
                  <Card.Body>
                    <Card.Text as="div" className="markdown-content" style={{ maxHeight: '15em', overflowY: 'auto' }}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{note.content}</ReactMarkdown>
                    </Card.Text>
                  </Card.Body>
                  <Card.Footer className="text-end">
                    <Stack gap={2} className="justify-content-end flex-column flex-sm-row">
                      <Button variant="outline-primary" size="sm" className="w-100 w-sm-auto" onClick={() => handleShowEditNoteModal(note)}>View/Edit</Button>
                      <Button variant="outline-danger" size="sm" className="w-100 w-sm-auto" onClick={() => handleShowDeleteConfirmModal(note)}>Delete</Button>
                    </Stack>
                  </Card.Footer>
                </Card>
              ))}
            </Stack>
          );
        }
        return null; // Fallback, though loading/initial error states are handled above
      })()}
    </div>
  );
};

export default NoteList; 