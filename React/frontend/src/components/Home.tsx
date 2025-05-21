import React from 'react';
import Card from 'react-bootstrap/Card';
// import Container from 'react-bootstrap/Container'; // If needed for more complex layout

const Home: React.FC = () => {
  return (
    <Card className="shadow-sm">
      <Card.Body>
        <Card.Title as="h2" className="mb-4">Welcome to Open Notebook AI!</Card.Title>
        <Card.Text>
          This is the new React frontend. Navigate using the links in the header.
        </Card.Text>
        {/* You could add more Bootstrap components here, like Buttons or a Jumbotron-like element */}
        {/* For example:
        <Container className="p-5 mb-4 bg-light rounded-3">
          <h1 className="display-4 fw-bold">Welcome!</h1>
          <p className="lead">This is a simple hero unit, a simple jumbotron-style component for calling extra attention to featured content or information.</p>
          <hr className="my-4" />
          <p>It uses utility classes for typography and spacing to space content out within the larger container.</p>
          <Button variant="primary" size="lg">Learn more</Button>
        </Container>
        */}
      </Card.Body>
    </Card>
  );
};

export default Home; 