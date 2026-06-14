import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useMutation } from '@tanstack/react-query';

interface ChatPanelProps {
  sessionId: string | null;
  onSessionCreated: (id: string) => void;
  onProductsReceived: (products: any[]) => void;
  onStateReceived: (state: any) => void;
  onMetricsReceived: (metrics: any) => void;
  onCartReceived: (cartItems: any[]) => void;
  isTyping: boolean;
  setIsTyping: (t: boolean) => void;
}

// Simple Markdown Parser
function parseMarkdown(text: string) {
  if (!text) return '';
  try {
    return text
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code class="bg-black/20 px-1 rounded">$1</code>')
        .replace(/^\s*[-*]\s+(.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
        .replace(/^\s*\d+\.\s+(.+)$/gm, '<li class="ml-4 list-decimal">$1</li>')
        .replace(/((?:<li[^>]*>.*<\/li>\s*)+)/gs, '<ul class="my-2">$1</ul>')
        .replace(/\n\n/g, '</p><p class="mt-2">')
        .replace(/\n/g, '<br>')
        .replace(/^/, '<p>').replace(/$/, '</p>');
  } catch {
    return `<p>${text}</p>`;
  }
}

export default function ChatPanel({ sessionId, onSessionCreated, onProductsReceived, onStateReceived, onMetricsReceived, onCartReceived, isTyping, setIsTyping }: ChatPanelProps) {
  const { authFetch } = useAuth();
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load session messages when sessionId changes
  useEffect(() => {
    if (sessionId) {
      authFetch(`/api/chat/session/${sessionId}`)
        .then(res => res.json())
        .then(data => {
          if (data.messages && data.messages.length > 0) {
            setMessages(data.messages);
          } else {
            setMessages([{
              role: 'assistant',
              content: "Hey! 👋 I'm your AI shopping consultant. What are you looking for?"
            }]);
          }
          onProductsReceived(data.products || []);
          onStateReceived(data.state || {});
          onMetricsReceived(data.filtering_metadata || {});
          onCartReceived(data.cart_items || []);
        })
        .catch(err => console.error(err));
    } else {
      setMessages([{
        role: 'assistant',
        content: "Hey! 👋 I'm your AI shopping consultant. What are you looking for?"
      }]);
      onProductsReceived([]);
      onStateReceived({});
      onMetricsReceived({});
      onCartReceived([]);
    }
  }, [sessionId]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const sendMessageMutation = useMutation({
    mutationFn: async (message: string) => {
      const targetSession = sessionId || await authFetch('/api/chat/new-session', { method: 'POST' }).then(r => r.json()).then(d => {
        onSessionCreated(d.session_id);
        return d.session_id;
      });

      const res = await authFetch('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ session_id: targetSession, message })
      });
      if (!res.ok) throw new Error('Failed to send');
      return res.json();
    },
    onMutate: (newMsg) => {
      setMessages(prev => [...prev, { role: 'user', content: newMsg }]);
      setInput('');
      setIsTyping(true);
    },
    onSuccess: (data) => {
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
      
      if (data.recommendation_action !== "none") {
        onProductsReceived(data.products || []);
      }
      
      if (data.state) {
        onStateReceived(data.state);
      }
      if (data.filtering_metadata) {
        onMetricsReceived(data.filtering_metadata);
      }
      setIsTyping(false);
    },
    onError: () => {
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I encountered an error. Please try again." }]);
      setIsTyping(false);
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isTyping) {
      sendMessageMutation.mutate(input.trim());
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  return (
    <div className="flex-1 bg-bg-chat flex flex-col h-full min-w-[340px]">
      <div className="p-4 border-b border-border-light bg-gradient-to-br from-bg-secondary to-bg-card flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-orange-500 flex items-center justify-center text-white">
          <Bot size={18} />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-text-primary">Shopping Assistant</h2>
          <div className="text-[10px] text-success flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-success"></div> Online
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-custom">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 animate-fadeIn ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 text-white
              ${m.role === 'assistant' ? 'bg-gradient-to-br from-accent to-orange-500' : 'bg-gray-700'}`}>
              {m.role === 'assistant' ? <Bot size={16} /> : <User size={16} />}
            </div>
            <div className={`max-w-[85%] p-3 text-sm leading-relaxed ${
              m.role === 'assistant' 
                ? 'bg-chat-ai rounded-2xl rounded-tl-sm text-text-primary' 
                : 'bg-chat-user rounded-2xl rounded-tr-sm text-white'
            }`}>
              {m.role === 'assistant' 
                ? <div dangerouslySetInnerHTML={{ __html: parseMarkdown(m.content || '') }} />
                : <p>{m.content || ''}</p>
              }
            </div>
          </div>
        ))}

        {isTyping && (
          <div className="flex gap-3 animate-fadeIn">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-orange-500 flex items-center justify-center shrink-0 text-white">
              <Bot size={16} />
            </div>
            <div className="bg-chat-ai rounded-2xl rounded-tl-sm p-4 flex items-center gap-1">
              <div className="w-1.5 h-1.5 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
              <div className="w-1.5 h-1.5 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
              <div className="w-1.5 h-1.5 bg-text-muted rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-bg-secondary border-t border-border-light">
        {messages.length <= 1 ? (
          <div className="flex flex-wrap gap-2 mb-3">
            {['Coffee pods for Keurig', 'Healthy snacks', 'Cat food'].map(s => (
              <button 
                key={s}
                onClick={() => sendMessageMutation.mutate(s)}
                className="px-3 py-1.5 rounded-full bg-accent-glow/30 border border-accent/30 text-accent-light text-xs hover:bg-accent/20 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about products... (Shift+Enter for new line)"
            className="flex-1 bg-bg-card border border-border-light rounded-xl px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-glow resize-none h-12 scrollbar-custom"
            rows={1}
            disabled={isTyping}
          />
          <button 
            type="submit" 
            disabled={!input.trim() || isTyping}
            className="w-12 h-12 shrink-0 bg-gradient-to-br from-accent to-orange-500 rounded-xl flex items-center justify-center text-white hover:scale-105 transition-transform disabled:opacity-50 disabled:hover:scale-100"
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
