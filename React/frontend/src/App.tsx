import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link as RouterLink } from 'react-router-dom';
import Container from 'react-bootstrap/Container';
import Navbar from 'react-bootstrap/Navbar';
import Nav from 'react-bootstrap/Nav';

import Home from './components/Home';
import Notebooks from './components/Notebooks';
import Models from './components/Models';
import Podcasts from './components/Podcasts';
import NotebookDetail from './components/NotebookDetail';

function App() {
  return (
    <Router>
      <div className="d-flex flex-column min-vh-100">
        <Navbar bg="primary" variant="dark" expand="lg">
          <Container>
            <Navbar.Brand as={RouterLink} to="/">Open Notebook AI</Navbar.Brand>
            <Navbar.Toggle aria-controls="basic-navbar-nav" />
            <Navbar.Collapse id="basic-navbar-nav">
              <Nav className="ms-auto">
                <Nav.Link as={RouterLink} to="/notebooks">Notebooks</Nav.Link>
                <Nav.Link as={RouterLink} to="/models">Models</Nav.Link>
                <Nav.Link as={RouterLink} to="/podcasts">Podcasts</Nav.Link>
              </Nav>
            </Navbar.Collapse>
          </Container>
        </Navbar>

        <Container fluid as="main" className="flex-grow-1 py-4">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/notebooks" element={<Notebooks />} />
            <Route path="/notebooks/:notebookId" element={<NotebookDetail />} />
            <Route path="/models" element={<Models />} />
            <Route path="/podcasts" element={<Podcasts />} />
          </Routes>
        </Container>

        <footer className="bg-light text-center p-3 mt-auto">
          <Container>
            <p className="mb-0">&copy; {new Date().getFullYear()} Open Notebook AI. All rights reserved.</p>
          </Container>
        </footer>
      </div>
    </Router>
  );
}

export default App;
