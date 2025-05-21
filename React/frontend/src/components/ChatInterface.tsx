import React, { useEffect, useState, useCallback, useRef } from 'react';
import { getChatMessages, postChatMessage } from '../services/api';
import type { ChatMessage as ChatMessageType } from '../types'; // Renamed to avoid conflict
import {
  Spinner,
  Alert,
  Form,
  Button,
  Stack,
  ListGroup,
  Card
} from 'react-bootstrap';

interface ChatInterfaceProps {
  chatSessionId: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ chatSessionId }) => {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [loadingMessages, setLoadingMessages] = useState<boolean>(false);
  const [messageError, setMessageError] = useState<string | null>(null);
  const [newMessageContent, setNewMessageContent] = useState<string>('');
  const [isSending, setIsSending] = useState<boolean>(false);

  const messagesEndRef = useRef<null | HTMLDivElement>(null); // For auto-scrolling

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const loadMessages = useCallback(async () => {
    if (!chatSessionId) return;
    setLoadingMessages(true);
    setMessageError(null);
    try {
      const fetchedMessages = await getChatMessages(chatSessionId);
      setMessages(fetchedMessages);
    } catch (err) {
      setMessageError('Failed to load messages.');
      console.error(err);
    } finally {
      setLoadingMessages(false);
    }
  }, [chatSessionId]);

  useEffect(() => {
    loadMessages();
  }, [loadMessages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]); // Scroll when new messages are added

  const handleSendMessage = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!newMessageContent.trim() || !chatSessionId) return;

    setIsSending(true);
    setMessageError(null);

    // Optimistically add user's message (optional, but good for UX)
    // const optimisticUserMessage: ChatMessageType = {
    //   id: `temp-${Date.now()}`,
    //   chat_session_id: chatSessionId,
    //   sender: 'user',
    //   content: newMessageContent,
    //   timestamp: new Date().toISOString(),
    // };
    // setMessages(prev => [...prev, optimisticUserMessage]);

    try {
      const responseMessages = await postChatMessage(chatSessionId, newMessageContent);
      // Backend returns both user and AI message, or just AI message depending on impl.
      // Assuming backend returns array with [userMessage, aiMessage]
      // Replace optimistic message with actual from backend if used, or just add new ones.
      // For now, we'll just re-fetch all messages to ensure consistency.
      // A more optimized approach would be to append the new messages from the response.
      setMessages(prevMessages => [...prevMessages, ...responseMessages]);
      setNewMessageContent('');
    } catch (err) {
      setMessageError('Failed to send message.');
      // setMessages(prev => prev.filter(msg => msg.id !== optimisticUserMessage.id)); // Rollback optimistic update
      console.error(err);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <Stack gap={3} style={{ height: 'calc(100vh - 300px)', overflowY: 'hidden' }}> {/* Adjust height as needed */}
      {messageError && <Alert variant="danger" onClose={() => setMessageError(null)} dismissible>{messageError}</Alert>}
      
      <div style={{ flexGrow: 1, overflowY: 'auto', paddingRight: '15px' }}> {/* Scrollable message list */}
        {loadingMessages && <div className="text-center p-3"><Spinner animation="border" /></div>}
        {!loadingMessages && messages.length === 0 && !messageError && (
          <p className="text-center text-muted p-3">No messages yet. Send a message to start the conversation!</p>
        )}
        <ListGroup variant="flush">
          {messages.map((msg) => (
            <ListGroup.Item 
              key={msg.id} 
              className={`d-flex ${msg.sender === 'user' ? 'justify-content-end' : 'justify-content-start'}`}
              style={{ borderBottom: 'none', paddingBottom: '0.25rem', paddingTop: '0.25rem' }}
            >
              <Card 
                bg={msg.sender === 'user' ? 'primary' : 'light'} 
                text={msg.sender === 'user' ? 'white' : 'dark'}
                style={{ maxWidth: '70%', borderRadius: '15px' }}
                className="p-2 px-3 shadow-sm"
              >
                <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{msg.content}</div>
                <small className={`text-xs ${msg.sender === 'user' ? 'text-white-50' : 'text-muted'} mt-1 d-block text-end`}>
                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </small>
              </Card>
            </ListGroup.Item>
          ))}
          <div ref={messagesEndRef} /> {/* Anchor for scrolling to bottom */}
        </ListGroup>
      </div>

      <Form onSubmit={handleSendMessage} className="mt-auto p-2 border-top">
        <Stack direction="horizontal" gap={2}>
          <Form.Control
            as="textarea"
            rows={1}
            value={newMessageContent}
            onChange={(e) => setNewMessageContent(e.target.value)}
            placeholder="Type your message..."
            disabled={isSending || loadingMessages}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!isSending) handleSendMessage(e as any); // Submit form
              }
            }}
            style={{ resize: 'none' }}
          />
          <Button variant="primary" type="submit" disabled={isSending || loadingMessages || !newMessageContent.trim()}>
            {isSending ? <Spinner as="span" animation="border" size="sm" /> : 'Send'}
          </Button>
        </Stack>
      </Form>
    </Stack>
  );
};

export default ChatInterface; 