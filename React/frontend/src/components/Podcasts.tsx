import React from 'react';
import { Card } from 'react-bootstrap';

const Podcasts: React.FC = () => {
  return (
    <Card className="mt-3">
      <Card.Body>
        <Card.Title as="h2">Podcasts</Card.Title>
        <Card.Text>
          Podcast generation and management will go here. This will replicate the Streamlit Podcasts page.
        </Card.Text>
        {/* Placeholder for podcast listing, generation forms, etc. */}
      </Card.Body>
    </Card>
  );
};

export default Podcasts; 