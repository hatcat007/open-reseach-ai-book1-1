import React, { useEffect, useState, type FormEvent } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { fetchNotebooks, createNotebook } from '../services/api';
import type { Notebook } from '../types';
import {
  Button,
  Card,
  Spinner,
  Alert,
  Modal,
  Form,
  Row,
  Col,
  Stack
} from 'react-bootstrap';

const Notebooks: React.FC = () => {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newNotebookName, setNewNotebookName] = useState<string>('');
  const [newNotebookDescription, setNewNotebookDescription] = useState<string>('');
  const [isCreating, setIsCreating] = useState<boolean>(false);

  const navigate = useNavigate();

  const loadNotebooks = async () => {
    try {
      setLoading(true);
      const data = await fetchNotebooks();
      setNotebooks(data);
      setError(null);
    } catch (err) {
      setError('Failed to fetch notebooks. Please try again later.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNotebooks();
  }, []);

  const handleCreateNotebook = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!newNotebookName.trim()) {
      alert('Name is required.');
      return;
    }
    setIsCreating(true);
    try {
      const newNotebook = await createNotebook(newNotebookName, newNotebookDescription);
      setShowCreateModal(false);
      setNewNotebookName('');
      setNewNotebookDescription('');
      navigate(`/notebooks/${newNotebook.id}`);
    } catch (err) {
      setError('Failed to create notebook.'); // Consider showing this error in the modal or as a toast
      console.error(err);
    } finally {
      setIsCreating(false);
    }
  };

  if (loading && !isCreating) {
    return (
      <div className="d-flex justify-content-center align-items-center vh-50">
        <Spinner animation="border" variant="primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
      </div>
    );
  }

  if (error && !showCreateModal) { // Don't show main page error if modal is open and might have its own error
    return <Alert variant="danger">{error}</Alert>;
  }

  return (
    <Stack gap={3}>
      <Row className="align-items-center mb-3">
        <Col xs={12} md="auto" className="mb-2 mb-md-0">
          <h2 className="mb-0">My Notebooks</h2>
        </Col>
        <Col xs={12} md="auto" className="ms-md-auto">
          <Button variant="primary" onClick={() => setShowCreateModal(true)} className="w-100 w-md-auto">
            + Create New Notebook
          </Button>
        </Col>
      </Row>

      <Modal show={showCreateModal} onHide={() => setShowCreateModal(false)} centered>
        <Modal.Header closeButton>
          <Modal.Title>Create New Notebook</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {error && showCreateModal && <Alert variant="danger">{error}</Alert>} {/* Error specific to modal */}
          <Form onSubmit={handleCreateNotebook}>
            <Form.Group className="mb-3" controlId="notebookName">
              <Form.Label>Name <span className="text-danger">*</span></Form.Label>
              <Form.Control 
                type="text" 
                value={newNotebookName}
                onChange={(e) => setNewNotebookName(e.target.value)}
                required
                disabled={isCreating}
              />
            </Form.Group>
            <Form.Group className="mb-3" controlId="notebookDescription">
              <Form.Label>Description (Optional)</Form.Label>
              <Form.Control 
                as="textarea" 
                rows={4}
                value={newNotebookDescription}
                onChange={(e) => setNewNotebookDescription(e.target.value)}
                disabled={isCreating}
              />
            </Form.Group>
            <Stack direction="horizontal" gap={2} className="justify-content-end">
              <Button variant="secondary" onClick={() => {setShowCreateModal(false); setError(null);}} disabled={isCreating}>
                Cancel
              </Button>
              <Button variant="primary" type="submit" disabled={isCreating}>
                {isCreating ? (
                  <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" className="me-1"/>
                ) : null}
                {isCreating ? 'Creating...' : 'Create Notebook'}
              </Button>
            </Stack>
          </Form>
        </Modal.Body>
      </Modal>

      {(!loading || isCreating) && notebooks.length === 0 && !error && (
         <div className="text-center text-muted py-5">
          <p className="h4">No notebooks found.</p>
          <p>Get started by creating a new one!</p>
        </div>
      )}
      {notebooks.length > 0 && (
        <Row xs={1} md={2} lg={3} className="g-4">
          {notebooks.map((notebook) => (
            <Col key={notebook.id}>
              <Card className="h-100 shadow-sm">
                <Card.Body className="d-flex flex-column">
                  <Card.Title className="mb-2 text-truncate" title={notebook.name}>{notebook.name}</Card.Title>
                  {notebook.description && (
                    <Card.Text className="text-muted small mb-3">
                      {notebook.description}
                    </Card.Text>
                  )}
                  <div className="text-muted small mb-2">
                    <p className="mb-0">Sources: <span className="fw-medium">{notebook.sourceCount ?? 0}</span></p>
                    <p className="mb-0">Notes: <span className="fw-medium">{notebook.noteCount ?? 0}</span></p>
                  </div>
                  <div className="mt-auto">
                    <div className="text-muted x-small mb-2">
                      <p className="mb-0">Updated: {new Date(notebook.updatedAt).toLocaleDateString()}</p>
                      <p className="mb-0">Created: {new Date(notebook.createdAt).toLocaleDateString()}</p>
                    </div>
                    <Button variant="success" as={RouterLink as any} to={`/notebooks/${notebook.id}`} className="w-100">
                      Open Notebook
                    </Button>
                  </div>
                </Card.Body>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </Stack>
  );
};

export default Notebooks; 