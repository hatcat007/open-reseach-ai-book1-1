import React from 'react';
import { Card } from 'react-bootstrap';

const Models: React.FC = () => {
  return (
    <Card className="mt-3">
      <Card.Body>
        <Card.Title as="h2">AI Models</Card.Title>
        <Card.Text>
          Models configuration and management will go here. This will replicate the Streamlit Models page.
        </Card.Text>
        {/* Placeholder for model selection, API keys, etc. */}
      </Card.Body>
    </Card>
  );
};

export default Models; 