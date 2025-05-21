import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import { fetchNotebookById, fetchSourcesByNotebookId, fetchNotesByNotebookId, getChatSessions, createChatSession } from '../services/api';
import type { Notebook, Source, Note, ChatSession as ChatSessionType } from '../types';
import SourceList from './SourceList';
import NoteList from './NoteList';
import ChatInterface from './ChatInterface';
import {
  Spinner,
  Alert,
  Row,
  Col,
  Card,
  Tabs,
  Tab,
  Breadcrumb,
  Stack,
  Button,
  ListGroup,
  Form,
  Modal
} from 'react-bootstrap';

const NotebookDetail: React.FC = () => {
  const { notebookId } = useParams<{ notebookId: string }>();
  const [notebook, setNotebook] = useState<Notebook | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('sources');

  const [chatSessions, setChatSessions] = useState<ChatSessionType[]>([]);
  const [loadingChatSessions, setLoadingChatSessions] = useState<boolean>(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [selectedChatSessionId, setSelectedChatSessionId] = useState<string | null>(null);
  const [showCreateChatModal, setShowCreateChatModal] = useState<boolean>(false);
  const [newChatSessionTitle, setNewChatSessionTitle] = useState<string>('');

  const loadNotebookDetails = useCallback(async () => {
    if (!notebookId) return;
    setLoading(true);
    try {
      const fetchedNotebook = await fetchNotebookById(notebookId);
      if (fetchedNotebook) {
        setNotebook(fetchedNotebook);
      } else {
        setError('Notebook not found.');
      }
    } catch (err) {
      setError('Failed to fetch notebook details.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [notebookId]);

  const loadChatSessions = useCallback(async () => {
    if (!notebookId) return;
    setLoadingChatSessions(true);
    setChatError(null);
    try {
      const sessions = await getChatSessions(notebookId);
      setChatSessions(sessions);
    } catch (err) {
      setChatError('Failed to load chat sessions.');
      console.error(err);
    } finally {
      setLoadingChatSessions(false);
    }
  }, [notebookId]);

  useEffect(() => {
    loadNotebookDetails();
  }, [loadNotebookDetails]);

  useEffect(() => {
    if (activeTab === 'chat') {
      loadChatSessions();
    }
  }, [activeTab, loadChatSessions]);

  const handleCreateChatSession = async () => {
    if (!notebookId) return;
    const titleToUse = newChatSessionTitle.trim() || undefined; 
    try {
      const newSession = await createChatSession(notebookId, titleToUse);
      setChatSessions(prevSessions => [newSession, ...prevSessions]);
      setSelectedChatSessionId(newSession.id);
      setShowCreateChatModal(false);
      setNewChatSessionTitle('');
      setChatError(null);
    } catch (err) {
      setChatError('Failed to create chat session.');
      console.error(err);
    }
  };

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '200px' }}>
        <Spinner animation="border" variant="primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
      </div>
    );
  }

  if (error) {
    return <Alert variant="danger">{error}</Alert>;
  }

  if (!notebook) {
    return <Alert variant="warning">Notebook not found.</Alert>;
  }

  return (
    <Stack gap={3}>
      <Breadcrumb>
        <Breadcrumb.Item linkAs={RouterLink} linkProps={{ to: "/notebooks" }}>
          &larr; Back to Notebooks
        </Breadcrumb.Item>
        <Breadcrumb.Item active>{notebook.name}</Breadcrumb.Item>
      </Breadcrumb>

      <Card className="shadow-sm w-100">
        <Card.Header as="h1" className="h3">{notebook.name}</Card.Header>
        <Card.Body>
          <Row className="mb-3 g-3">
            <Col md={4}>
              <Card bg="light" className="h-100">
                <Card.Body>
                  <Card.Subtitle className="mb-2 text-muted">Created</Card.Subtitle>
                  <Card.Text>{new Date(notebook.createdAt).toLocaleString()}</Card.Text>
                </Card.Body>
              </Card>
            </Col>
            <Col md={4}>
              <Card bg="light" className="h-100">
                <Card.Body>
                  <Card.Subtitle className="mb-2 text-muted">Last Updated</Card.Subtitle>
                  <Card.Text>{new Date(notebook.updatedAt).toLocaleString()}</Card.Text>
                </Card.Body>
              </Card>
            </Col>
            <Col md={4}>
              <Card bg="light" className="h-100">
                <Card.Body>
                  <Card.Subtitle className="mb-2 text-muted">Stats</Card.Subtitle>
                  <Card.Text className="mb-0">Sources: {notebook.sourceCount ?? 0}</Card.Text>
                  <Card.Text>Notes: {notebook.noteCount ?? 0}</Card.Text>
                </Card.Body>
              </Card>
            </Col>
          </Row>

          {notebook.description && (
            <div className="mb-4">
              <h2 className="h5">Description</h2>
              <p className="text-muted" style={{ whiteSpace: 'pre-wrap' }}>{notebook.description}</p>
            </div>
          )}

          <Tabs defaultActiveKey="sources" id="notebook-detail-tabs" className="mb-3" justify activeKey={activeTab} onSelect={(k) => setActiveTab(k || 'sources')}>
            <Tab eventKey="sources" title={`Sources (${notebook.sourceCount ?? 0})`}>
              {activeTab === 'sources' && notebookId && <SourceList notebookId={notebookId} />}
            </Tab>
            <Tab eventKey="notes" title={`Notes (${notebook.noteCount ?? 0})`}>
              {activeTab === 'notes' && notebookId && <NoteList notebookId={notebookId} />}
            </Tab>
            <Tab eventKey="chat" title="Chat">
              {activeTab === 'chat' && notebookId && (
                <Stack gap={3} className="mt-3">
                  <h4>Chat Sessions</h4>
                  {chatError && <Alert variant="danger">{chatError}</Alert>}
                  <Stack gap={2} className="mb-2 flex-column flex-sm-row">
                    <Button variant="primary" onClick={() => setShowCreateChatModal(true)} className="w-100 w-sm-auto">
                      + New Chat Session
                    </Button>
                    <Button variant="outline-secondary" onClick={loadChatSessions} disabled={loadingChatSessions} className="w-100 w-sm-auto">
                      {loadingChatSessions ? <Spinner as="span" animation="border" size="sm" /> : 'Refresh Chats'}
                    </Button>
                  </Stack>

                  <Modal show={showCreateChatModal} onHide={() => setShowCreateChatModal(false)} centered>
                    <Modal.Header closeButton>
                      <Modal.Title>New Chat Session</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                      <Form.Group controlId="newChatSessionTitle">
                        <Form.Label>Session Title (Optional)</Form.Label>
                        <Form.Control 
                          type="text"
                          value={newChatSessionTitle}
                          onChange={(e) => setNewChatSessionTitle(e.target.value)}
                        />
                      </Form.Group>
                    </Modal.Body>
                    <Modal.Footer>
                      <Button variant="secondary" onClick={() => setShowCreateChatModal(false)}>Cancel</Button>
                      <Button variant="primary" onClick={handleCreateChatSession}>Create</Button>
                    </Modal.Footer>
                  </Modal>

                  {loadingChatSessions && <Spinner animation="border" variant="primary" />}
                  {!loadingChatSessions && chatSessions.length === 0 && !chatError && (
                    <p>No chat sessions yet. Start a new one!</p>
                  )}
                  {chatSessions.length > 0 && (
                    <ListGroup>
                      {chatSessions.map(session => (
                        <ListGroup.Item 
                          key={session.id} 
                          action 
                          onClick={() => setSelectedChatSessionId(session.id)}
                          active={selectedChatSessionId === session.id}
                        >
                          {session.title || `Chat on ${new Date(session.created_at).toLocaleString()}`}
                          <br />
                          <small className="text-muted">ID: {session.id} | Updated: {new Date(session.updated_at).toLocaleDateString()}</small>
                        </ListGroup.Item>
                      ))}
                    </ListGroup>
                  )}

                  {selectedChatSessionId && (
                    <Card className="mt-3">
                      <Card.Header>Chat Interface for: {selectedChatSessionId}</Card.Header>
                      <Card.Body>
                        <ChatInterface chatSessionId={selectedChatSessionId} />
                      </Card.Body>
                    </Card>
                  )}
                </Stack>
              )}
            </Tab>
          </Tabs>
        </Card.Body>
      </Card>
    </Stack>
  );
};

export default NotebookDetail; 