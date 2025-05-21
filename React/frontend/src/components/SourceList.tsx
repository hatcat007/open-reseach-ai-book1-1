import React, { useEffect, useState, useCallback } from 'react';
import type { FormEvent } from 'react';
import { fetchSourcesByNotebookId, addSource, deleteSource as apiDeleteSource, updateSource as apiUpdateSource, runSourceTransformation as apiRunSourceTransformation, type TransformationParams as ApiTransformationParams, type TransformationResult as ApiTransformationResult } from '../services/api';
import type { Source } from '../types';
import { Button, Modal, Form, Spinner, Alert, ListGroup, Badge, Stack, CloseButton, Tabs, Tab, Row, Col, Accordion, Card, InputGroup } from 'react-bootstrap';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface SourceListProps {
  notebookId: string;
}

const SourceList: React.FC<SourceListProps> = ({ notebookId }) => {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddSourceModal, setShowAddSourceModal] = useState<boolean>(false);
  const [newSourceType, setNewSourceType] = useState<Source['type']>('url');
  const [newSourceContent, setNewSourceContent] = useState<string>('');
  const [newSourceTitle, setNewSourceTitle] = useState<string>('');
  const [isAddingSource, setIsAddingSource] = useState<boolean>(false);

  const [selectedSourceForView, setSelectedSourceForView] = useState<Source | null>(null);
  const [showViewSourceModal, setShowViewSourceModal] = useState<boolean>(false);
  const [activeSourceViewTab, setActiveSourceViewTab] = useState<string>('process');

  const [sourceToDelete, setSourceToDelete] = useState<Source | null>(null);
  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState<boolean>(false);
  const [isDeletingSource, setIsDeletingSource] = useState<boolean>(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // State for editing title
  const [editableSourceTitle, setEditableSourceTitle] = useState<string>('');
  const [isEditingTitle, setIsEditingTitle] = useState<boolean>(false);
  const [isSavingTitle, setIsSavingTitle] = useState<boolean>(false);
  const [titleError, setTitleError] = useState<string | null>(null);

  // State for Transformations
  const [selectedTransformationType, setSelectedTransformationType] = useState<string>('analyze_debate');
  const [isTransforming, setIsTransforming] = useState<boolean>(false);
  const [transformationResult, setTransformationResult] = useState<ApiTransformationResult | null>(null);
  const [transformationError, setTransformationError] = useState<string | null>(null);

  const transformationDescriptions: Record<string, string> = {
    analyze_debate: "A neutral and objective entity whose sole purpose is to help humans understand debates to broaden their own views.",
    summarize_text: "Generates a concise summary of the source content, highlighting key points.",
    extract_entities: "Identifies and extracts named entities (people, organizations, locations, etc.) from the text.",
    generate_questions: "Creates a list of relevant questions based on the source material to aid understanding or further research."
  };

  const loadSources = async () => {
    if (!notebookId) return;
    try {
      setLoading(true);
      setError(null); // Clear previous errors
      const data = await fetchSourcesByNotebookId(notebookId);
      setSources(data);
    } catch (err) {
      setError('Failed to fetch sources.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSources();
  }, [notebookId]);

  const handleAddSource = async (e: FormEvent) => {
    e.preventDefault();
    if (!newSourceContent.trim()) {
      // This validation could be improved with Form.Control.Feedback in Bootstrap
      alert('Content/URL is required.');
      return;
    }
    setIsAddingSource(true);
    setError(null); // Clear previous error before attempting to add
    try {
      await addSource(notebookId, newSourceType, newSourceContent, newSourceTitle);
      setShowAddSourceModal(false);
      setNewSourceType('url');
      setNewSourceContent('');
      setNewSourceTitle('');
      await loadSources(); // Reload sources to show the new one
    } catch (err) {
      setError('Failed to add source. Please try again.'); // Set error to be displayed in the modal
      console.error(err);
    } finally {
      setIsAddingSource(false);
    }
  };

  const handleCloseModal = () => {
    setShowAddSourceModal(false);
    setError(null); // Clear any errors when modal is dismissed
    // Reset form fields if needed, though they are reset on successful submission
    setNewSourceType('url');
    setNewSourceContent('');
    setNewSourceTitle('');
  };
  
  const handleOpenViewModal = (source: Source) => {
    setSelectedSourceForView(source);
    setShowViewSourceModal(true);
    setEditableSourceTitle(source.title || ''); // Initialize for editing
    setIsEditingTitle(false); // Reset edit mode
    setTitleError(null); // Clear previous title errors
    // Reset transformation state when opening modal for a new source
    setSelectedTransformationType('analyze_debate');
    setTransformationResult(null);
    setTransformationError(null);
  };

  const handleCloseViewModal = () => {
    setShowViewSourceModal(false);
    setSelectedSourceForView(null);
    setActiveSourceViewTab('process'); // Reset tab to default
    setIsEditingTitle(false); // Ensure edit mode is off when modal closes
    setTitleError(null);
    // Reset transformation state on close
    setTransformationResult(null);
    setTransformationError(null);
  };

  const handleShowDeleteConfirm = (source: Source) => {
    setSourceToDelete(source);
    setShowDeleteConfirmModal(true);
    setDeleteError(null); // Clear previous errors
  };

  const handleHideDeleteConfirm = () => {
    setShowDeleteConfirmModal(false);
    setSourceToDelete(null);
    setDeleteError(null);
  };

  const handleConfirmDeleteSource = async () => {
    if (!sourceToDelete) return;

    setIsDeletingSource(true);
    setDeleteError(null);
    try {
      await apiDeleteSource(sourceToDelete.id);
      setShowDeleteConfirmModal(false); // Close confirmation modal
      setShowViewSourceModal(false); // Close the main view modal if open
      setSelectedSourceForView(null); 
      setSourceToDelete(null);
      await loadSources(); // Refresh the list
    } catch (err) {
      console.error('Failed to delete source:', err);
      setDeleteError(err instanceof Error ? err.message : 'An unknown error occurred while deleting the source.');
    } finally {
      setIsDeletingSource(false);
    }
  };

  const handleEditTitleClick = () => {
    if (!selectedSourceForView) return;
    setEditableSourceTitle(selectedSourceForView.title || '');
    setIsEditingTitle(true);
    setTitleError(null);
  };

  const handleCancelEditTitleClick = () => {
    setIsEditingTitle(false);
    setTitleError(null);
    if (selectedSourceForView) {
      setEditableSourceTitle(selectedSourceForView.title || ''); // Reset to original
    }
  };

  const handleSaveTitleClick = async () => {
    if (!selectedSourceForView) return;

    setIsSavingTitle(true);
    setTitleError(null);
    try {
      const updatedSource = await apiUpdateSource(selectedSourceForView.id, { title: editableSourceTitle });
      setSelectedSourceForView(updatedSource); // Update the view with the full response
      setIsEditingTitle(false);
      await loadSources(); // Reload the main list to reflect changes
    } catch (err) {
      console.error('Failed to update source title:', err);
      setTitleError(err instanceof Error ? err.message : 'An unknown error occurred while updating the title.');
    } finally {
      setIsSavingTitle(false);
    }
  };

  const handleRunTransformation = async () => {
    if (!selectedSourceForView || !selectedTransformationType) return;

    setIsTransforming(true);
    setTransformationResult(null);
    setTransformationError(null);
    try {
      // For now, params are empty. This can be expanded later.
      const result = await apiRunSourceTransformation(selectedSourceForView.id, selectedTransformationType, {}); 
      setTransformationResult(result);
      // Optionally, if the transformation updates insights/summary directly on the source model:
      // await loadSources(); // to refresh the main list
      // or update selectedSourceForView if the result contains the full updated source
      // For now, we just display the direct resultText if available.
    } catch (err) {
      console.error('Failed to run transformation:', err);
      setTransformationError(err instanceof Error ? err.message : 'An unknown error occurred while running the transformation.');
    } finally {
      setIsTransforming(false);
    }
  };

  const getStatusVariant = (status?: 'processed' | 'pending' | 'error') => {
    switch (status) {
      case 'processed': return 'success';
      case 'pending': return 'warning';
      case 'error': return 'danger';
      default: return 'secondary';
    }
  };

  if (loading && !isAddingSource && sources.length === 0) { // Show main loader only if no sources yet
    return (
      <div className="d-flex justify-content-center align-items-center py-5">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading sources...</span>
        </Spinner>
      </div>
    );
  }

  // Display general error for loading sources (not for adding source, that's in modal)
  if (error && !showAddSourceModal && !isAddingSource) {
    return <Alert variant="danger">{error}</Alert>;
  }

  return (
    <div className="mt-3">
      <Stack gap={3} className="mb-3 align-items-center flex-column flex-sm-row align-items-sm-center">
        <h3 className="mb-2 mb-sm-0">Sources</h3>
        <Button variant="primary" size="sm" onClick={() => { setError(null); setShowAddSourceModal(true); }} className="ms-sm-auto w-100 w-sm-auto">
          <i className="bi bi-plus-lg me-1"></i> Add Source
        </Button>
      </Stack>

      <Modal show={showAddSourceModal} onHide={handleCloseModal} centered>
        <Modal.Header closeButton>
          <Modal.Title>Add New Source</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {error && showAddSourceModal && <Alert variant="danger" onClose={() => setError(null)} dismissible className="mb-3">{error}</Alert>}
          <Form onSubmit={handleAddSource}>
            <Form.Group className="mb-3" controlId="sourceType">
              <Form.Label>Source Type</Form.Label>
              <Form.Select 
                value={newSourceType} 
                onChange={(e) => setNewSourceType(e.target.value as Source['type'])}
                disabled={isAddingSource}
              >
                <option value="url">URL</option>
                <option value="text">Text</option>
                <option value="file">File (Placeholder)</option>
                <option value="scraped_web_page">Scrape Website (Placeholder)</option>
              </Form.Select>
            </Form.Group>

            <Form.Group className="mb-3" controlId="sourceContent">
              <Form.Label>
                {newSourceType === 'url' ? 'URL' : 'Content'} <span className="text-danger">*</span>
              </Form.Label>
              <Form.Control 
                as="textarea"
                value={newSourceContent}
                onChange={(e) => setNewSourceContent(e.target.value)}
                rows={newSourceType === 'text' || newSourceType === 'scraped_web_page' ? 6 : 2}
                required
                placeholder={newSourceType === 'url' ? 'https://example.com' : 'Paste your text content here...'}
                disabled={isAddingSource}
              />
            </Form.Group>
            
            {(newSourceType === 'url' || newSourceType === 'scraped_web_page' || newSourceType === 'file') && (
              <Form.Group className="mb-3" controlId="sourceTitle">
                <Form.Label>Title (Optional)</Form.Label>
                <Form.Control 
                  type="text" 
                  value={newSourceTitle}
                  onChange={(e) => setNewSourceTitle(e.target.value)}
                  placeholder="e.g., My Awesome Research Paper"
                  disabled={isAddingSource}
                />
              </Form.Group>
            )}
            <Stack direction="horizontal" gap={2} className="justify-content-end mt-4">
              <Button variant="secondary" onClick={handleCloseModal} disabled={isAddingSource}>
                Cancel
              </Button>
              <Button variant="primary" type="submit" disabled={isAddingSource}>
                {isAddingSource ? (
                  <>
                    <Spinner
                      as="span"
                      animation="border"
                      size="sm"
                      role="status"
                      aria-hidden="true"
                      className="me-2"
                    />
                    Adding...
                  </>
                ) : 'Add Source'}
              </Button>
            </Stack>
          </Form>
        </Modal.Body>
      </Modal>

      {selectedSourceForView && (
        <Modal show={showViewSourceModal} onHide={handleCloseViewModal} size="xl" centered>
          <Modal.Header closeButton>
            <Modal.Title>Source</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            {titleError && <Alert variant="danger" onClose={() => setTitleError(null)} dismissible>{titleError}</Alert>}
            <Form.Group className="mb-3">
              <Form.Label>Title</Form.Label>
              <InputGroup>
                <Form.Control 
                  type="text" 
                  value={editableSourceTitle}
                  onChange={(e) => setEditableSourceTitle(e.target.value)}
                  readOnly={!isEditingTitle || isSavingTitle}
                  placeholder="Enter source title"
                />
                {isEditingTitle ? (
                  <>
                    <Button variant="outline-success" onClick={handleSaveTitleClick} disabled={isSavingTitle || !editableSourceTitle.trim()}>
                      {isSavingTitle ? <Spinner as="span" animation="border" size="sm" /> : 'Save'}
                    </Button>
                    <Button variant="outline-secondary" onClick={handleCancelEditTitleClick} disabled={isSavingTitle}>
                      Cancel
                    </Button>
                  </>
                ) : (
                  <Button variant="outline-secondary" onClick={handleEditTitleClick}>
                    Edit
                  </Button>
                )}
              </InputGroup>
              {isEditingTitle && !editableSourceTitle.trim() && <Form.Text className="text-danger">Title cannot be empty.</Form.Text>}
            </Form.Group>

            <Tabs activeKey={activeSourceViewTab} onSelect={(k) => setActiveSourceViewTab(k || 'process')} id="source-view-tabs" className="mb-3" justify>
              <Tab eventKey="process" title="Process">
                <Row>
                  <Col md={8}>
                    <Stack gap={3}>
                      <h4>{selectedSourceForView.title || 'Untitled Source'}</h4>
                      <p className="text-muted">
                        Created: {(() => {
                          if (!selectedSourceForView.createdAt) return 'N/A';
                          const date = new Date(selectedSourceForView.createdAt);
                          return date.toString() === 'Invalid Date' ? 'Invalid Date (check source data)' : date.toLocaleString();
                        })()}
                        {selectedSourceForView.type === 'url' && selectedSourceForView.asset?.url && (
                          <>, from URL: <a href={selectedSourceForView.asset.url} target="_blank" rel="noopener noreferrer">{selectedSourceForView.asset.url}</a></>
                        )}
                      </p>
                      
                      <Accordion defaultActiveKey={[]} alwaysOpen>
                        <Accordion.Item eventKey="0">
                          <Accordion.Header>Key Insights</Accordion.Header>
                          <Accordion.Body>
                            {selectedSourceForView?.keyInsights ? (
                              Array.isArray(selectedSourceForView.keyInsights) ? (
                                <ListGroup variant="flush">
                                  {selectedSourceForView.keyInsights.map((insight, index) => (
                                    <ListGroup.Item key={index} className="px-0">
                                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{insight}</ReactMarkdown>
                                    </ListGroup.Item>
                                  ))}
                                </ListGroup>
                              ) : (
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{selectedSourceForView.keyInsights}</ReactMarkdown>
                              )
                            ) : (
                              <p className="text-muted">No key insights processed for this source yet.</p>
                            )}
                          </Accordion.Body>
                        </Accordion.Item>
                        <Accordion.Item eventKey="1">
                          <Accordion.Header>Simple Summary</Accordion.Header>
                          <Accordion.Body>
                            {selectedSourceForView?.simpleSummary ? (
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{selectedSourceForView.simpleSummary}</ReactMarkdown>
                            ) : (
                              <p className="text-muted">No summary processed for this source yet.</p>
                            )}
                          </Accordion.Body>
                        </Accordion.Item>
                        <Accordion.Item eventKey="2">
                          <Accordion.Header>Reflection Questions</Accordion.Header>
                          <Accordion.Body>
                            {selectedSourceForView?.reflectionQuestions ? (
                              Array.isArray(selectedSourceForView.reflectionQuestions) ? (
                                <ListGroup variant="flush">
                                  {selectedSourceForView.reflectionQuestions.map((question, index) => (
                                    <ListGroup.Item key={index} className="px-0">
                                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{question}</ReactMarkdown>
                                    </ListGroup.Item>
                                  ))}
                                </ListGroup>
                              ) : (
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{selectedSourceForView.reflectionQuestions}</ReactMarkdown>
                              )
                            ) : (
                              <p className="text-muted">No reflection questions processed for this source yet.</p>
                            )}
                          </Accordion.Body>
                        </Accordion.Item>
                      </Accordion>
                    </Stack>
                  </Col>
                  <Col md={4}>
                    <Card>
                      <Card.Body>
                        <Card.Title className="mb-3">Run a transformation</Card.Title>
                        <Form.Group className="mb-2">
                          <Form.Select 
                            value={selectedTransformationType} 
                            onChange={(e) => {
                              setSelectedTransformationType(e.target.value);
                              setTransformationResult(null); // Clear previous results when type changes
                              setTransformationError(null);
                            }}
                            disabled={isTransforming}
                          >
                            <option value="analyze_debate">Analyze Debate</option>
                            <option value="summarize_text">Summarize Text</option>
                            <option value="extract_entities">Extract Entities</option>
                            <option value="generate_questions">Generate Questions</option>
                          </Form.Select>
                        </Form.Group>
                        <Card.Text className="text-muted small mb-3" style={{ minHeight: '50px' }}>
                          {transformationDescriptions[selectedTransformationType] || 'Select a transformation to see its description.'}
                        </Card.Text>
                        <Button 
                          variant="primary" 
                          className="w-100 mb-2" 
                          disabled={isTransforming || !selectedSourceForView || !selectedTransformationType}
                          onClick={handleRunTransformation}
                        >
                          {isTransforming ? (
                            <><Spinner as="span" animation="border" size="sm" /> Running...</>
                          ) : 'Run'}
                        </Button>
                        {transformationError && (
                          <Alert variant="danger" onClose={() => setTransformationError(null)} dismissible className="mt-2">
                            {transformationError}
                          </Alert>
                        )}
                        {transformationResult && (
                          <Alert variant="success" onClose={() => setTransformationResult(null)} dismissible className="mt-2">
                            <strong>Success!</strong> {transformationResult.message || 'Transformation complete.'}
                            {transformationResult.resultText && <pre className="mt-2" style={{whiteSpace: 'pre-wrap', maxHeight: '150px', overflowY: 'auto'}}>{transformationResult.resultText}</pre>}
                          </Alert>
                        )}
                      </Card.Body>
                    </Card>
                    <Card className="mt-3">
                      <Card.Body className="text-center">
                        <p className="text-muted small">Deleting the source will also delete all its insights and embeddings.</p>
                        <Button variant="danger" onClick={() => selectedSourceForView && handleShowDeleteConfirm(selectedSourceForView)} disabled={!selectedSourceForView || isDeletingSource}>
                          {isDeletingSource && sourceToDelete?.id === selectedSourceForView?.id ? (
                            <><Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> Deleting...</>
                          ) : 'Delete'}
                        </Button>
                      </Card.Body>
                    </Card>
                  </Col>
                </Row>
              </Tab>
              <Tab eventKey="source" title="Source Details">
                <Stack gap={3} className="mt-3">
                  <div>
                    <strong>ID:</strong> <span className="text-muted">{selectedSourceForView.id}</span>
                  </div>
                  <div>
                    <strong>Type:</strong> <Badge bg="info">{selectedSourceForView.type || 'N/A'}</Badge>
                  </div>
                  {selectedSourceForView.status && (
                    <div>
                      <strong>Status:</strong> <Badge bg={getStatusVariant(selectedSourceForView.status)}>{selectedSourceForView.status}</Badge>
                    </div>
                  )}
                  
                  {(selectedSourceForView.type === 'url' && selectedSourceForView.asset?.url) && (
                    <div>
                      <strong>URL:</strong> <a href={selectedSourceForView.asset.url} target="_blank" rel="noopener noreferrer">{selectedSourceForView.asset.url}</a>
                    </div>
                  )}
                  {(selectedSourceForView.type === 'file' && selectedSourceForView.asset?.file_path) && (
                    <div>
                      <strong>File Path:</strong> <span className="font-monospace">{selectedSourceForView.asset.file_path}</span>
                    </div>
                  )}
                  
                  {typeof selectedSourceForView.content === 'string' && selectedSourceForView.content.trim() !== '' && (
                    <div>
                      <strong>Content:</strong>
                      <pre style={{ whiteSpace: 'pre-wrap', maxHeight: '300px', overflowY: 'auto', background: '#f8f9fa', padding: '10px', borderRadius: '4px' }}>
                        {selectedSourceForView.content}
                      </pre>
                    </div>
                  )}

                  {!(selectedSourceForView.type === 'url' && selectedSourceForView.asset?.url) && 
                   !(selectedSourceForView.type === 'file' && selectedSourceForView.asset?.file_path) && 
                   !(typeof selectedSourceForView.content === 'string' && selectedSourceForView.content.trim() !== '') && (
                    <Alert variant="light">No direct content, URL, or file path to display for this source type.</Alert>
                  )}
                </Stack>
              </Tab>
            </Tabs>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={handleCloseViewModal}>
              Close
            </Button>
            {(selectedSourceForView.type === 'url' && selectedSourceForView.asset?.url && activeSourceViewTab === 'source') && (
                <Button variant="primary" href={selectedSourceForView.asset.url} target="_blank" rel="noopener noreferrer">\
                    Open URL
                </Button>
            )}
          </Modal.Footer>
        </Modal>
      )}

      {sourceToDelete && (
        <Modal show={showDeleteConfirmModal} onHide={handleHideDeleteConfirm} centered size="sm">
          <Modal.Header closeButton>
            <Modal.Title>Confirm Delete</Modal.Title>
          </Modal.Header>
          <Modal.Body>
            {deleteError && <Alert variant="danger">{deleteError}</Alert>}
            <p>Are you sure you want to delete the source titled "<strong>{sourceToDelete.title || sourceToDelete.id}</strong>"?</p>
            <p className="text-muted small">This action cannot be undone and will remove all associated insights and embeddings.</p>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onClick={handleHideDeleteConfirm} disabled={isDeletingSource}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleConfirmDeleteSource} disabled={isDeletingSource}>
              {isDeletingSource ? (
                <><Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> Deleting...</>
              ) : 'Delete Source'}
            </Button>
          </Modal.Footer>
        </Modal>
      )}

      {sources.length === 0 && !loading && !error && (
        <Alert variant="info">No sources found for this notebook.</Alert>
      )}

      {sources.length > 0 && (
        <ListGroup variant="flush">
          {sources.map((source) => {
            // Determine display title and content preview safely
            let displayTitle = source.title || '';
            let contentPreview = '';
            let mainIdentifier = ''; // Used for display if title is missing

            if (source.type === 'url' && source.asset?.url) {
              mainIdentifier = source.asset.url;
            } else if (source.type === 'file' && source.asset?.file_path) {
              mainIdentifier = source.asset.file_path;
            } else if (typeof source.content === 'string' && source.content.trim() !== '') {
              mainIdentifier = source.content;
            }

            if (!displayTitle) {
              if (mainIdentifier) {
                displayTitle = mainIdentifier.substring(0, 100) + (mainIdentifier.length > 100 ? '...' : '');
              } else {
                displayTitle = 'Untitled Source';
              }
            }

            if (typeof source.content === 'string' && source.content.trim() !== '') {
              contentPreview = source.content.substring(0, 100) + (source.content.length > 100 ? '...' : '');
            } else if (mainIdentifier && mainIdentifier !== displayTitle) {
              // If title was set from source.title, and mainIdentifier is different (e.g. URL/path), show mainIdentifier as preview
              contentPreview = mainIdentifier; 
            } else {
              contentPreview = 'No additional content preview available.';
            }
            
            return (
              <ListGroup.Item key={source.id} className="px-0 py-3">
                <Stack gap={3} className="mb-3 flex-column flex-sm-row">
                  <div className="flex-grow-1 mb-2 mb-sm-0">
                    <h6 className="mb-0 text-primary" title={source.title || mainIdentifier || 'Untitled Source'}>
                      {displayTitle}
                    </h6>
                    <small className="text-muted">
                      Type: <span className="fw-semibold">{source.type}</span> | Added: {new Date(source.createdAt).toLocaleDateString()}
                    </small>
                    {/* Optionally show a snippet of content if different from title */}
                    { (typeof source.content === 'string' && source.content.trim() !== '' && (!source.title || source.content !== source.title)) &&
                      (mainIdentifier !== contentPreview || source.title) && /* Avoid redundant preview if title is already the content */ (
                        <p className="text-muted x-small mb-0 mt-1 fst-italic">
                            Preview: {source.content.substring(0, 70) + (source.content.length > 70 ? '...' : '')}
                        </p>
                    )}
                  </div>
                  <div className="flex-shrink-0 d-flex flex-column flex-sm-row align-items-stretch align-items-sm-center w-100 w-sm-auto">
                    {source.status && (
                       <Badge bg={getStatusVariant(source.status)} pill className="me-sm-2 mb-2 mb-sm-0 align-self-center align-self-sm-auto">
                         {source.status}
                       </Badge>
                    )}
                    {/* Using btn-link for a less intrusive look, or small buttons */}
                    <Button variant="link" size="sm" className="p-1 me-sm-1 text-decoration-none mb-1 mb-sm-0 w-100 w-sm-auto text-start text-sm-center" onClick={() => handleOpenViewModal(source)}>View</Button>
                    <Button variant="link" size="sm" className="p-1 text-danger text-decoration-none w-100 w-sm-auto text-start text-sm-center" onClick={() => handleShowDeleteConfirm(source)} disabled={isDeletingSource && sourceToDelete?.id === source.id }>
                      {isDeletingSource && sourceToDelete?.id === source.id ? (
                        <Spinner as="span" animation="border" size="sm" />
                       ) : 'Delete'}
                    </Button>
                  </div>
                </Stack>
              </ListGroup.Item>
            );
          })}
        </ListGroup>
      )}
    </div>
  );
};

export default SourceList; 