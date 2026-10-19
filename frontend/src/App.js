import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import valaLogo from './assets/vala-logo.png';
import agentAvatar from './assets/agent-avatar.jpg';
import chatWallpaper from './assets/chat-wallpaper.jpg';
import './App.css';

// Injectée au build (ARG REACT_APP_API_URL dans le Dockerfile, ou .env.local en dev)
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const formatTime = () =>
  new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

function App() {
  const [email, setEmail] = useState('');
  const [messages, setMessages] = useState([
    { type: 'agent', text: 'Bonjour! Comment puis-je vous aider ?', time: formatTime() }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesRef = useRef(null);

  const scrollToBottom = () => {
    const el = messagesRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = input;
    setInput('');
    setMessages(prev => [...prev, { type: 'user', text: userMessage, time: formatTime() }]);
    setLoading(true);

    try {
      const response = await axios.post(`${API_URL}/chat`, {
        client_email: email,
        message: userMessage
      });

      setMessages(prev => [
        ...prev,
        { type: 'agent', text: response.data.response, time: formatTime() }
      ]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        { type: 'agent', text: 'Erreur: Impossible de se connecter à l\'agent. Vérifiez que le backend fonctionne.', time: formatTime() }
      ]);
    }

    setLoading(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="App">
      <div className="ambient-glow ambient-glow--one" />
      <div className="ambient-glow ambient-glow--two" />

      <div className="chat-container">
        <div className="chat-header">
          <div className="header-left">
            <div className="brand-logo-wrap">
              <img src={valaLogo} alt="VALA" className="brand-logo" />
            </div>
            <span className="header-divider" />
            <div className="agent-avatar-ring">
              <img src={agentAvatar} alt="Agent VALA" className="agent-avatar" />
            </div>
            <div className="header-text">
              <span className="header-title">Vala Support Agent</span>
              <div className="status-row">
                <span className={`status-dot ${loading ? 'status-dot--busy' : 'status-dot--online'}`} />
                <span className="status-text">
                  {loading ? "En train d'écrire…" : 'En ligne · réponse immédiate'}
                </span>
              </div>
            </div>
          </div>

          <div className="email-field">
            <label htmlFor="client-email" className="email-label">Email :</label>
            <input
              id="client-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="vous@exemple.com"
              className="email-input"
            />
          </div>
        </div>

        <div
          ref={messagesRef}
          className="messages"
          style={{ backgroundImage: `linear-gradient(180deg, rgba(5,7,15,.55) 0%, rgba(5,7,15,.72) 100%), url(${chatWallpaper})` }}
        >
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.type}`}>
              {msg.type === 'agent' && (
                <img src={agentAvatar} alt="Agent" className="msg-avatar" />
              )}
              <div className="bubble-wrap">
                <div className="bubble">{msg.text}</div>
                <span className="msg-time">{msg.time}</span>
              </div>
            </div>
          ))}
          {loading && (
            <div className="message agent">
              <img src={agentAvatar} alt="Agent" className="msg-avatar" />
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}
        </div>

        <div className="input-area">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Posez votre question…"
            className="message-input"
            rows="1"
            disabled={loading}
          />
          <button onClick={sendMessage} disabled={loading || !input.trim()} className="send-btn">
            Envoyer
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
