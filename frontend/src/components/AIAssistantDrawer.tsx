import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, Sparkles, X, History, Plus, MessageSquare, Trash2, Tag, Activity } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';
import { usePageContext } from '../context/PageContext';
import { buildChatContext } from '../services/contextBuilder';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

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

export default function AIAssistantDrawer() {
  const { authFetch } = useAuth();
  const { syncCart } = useCart();
  const { pageContext } = usePageContext();
  const queryClient = useQueryClient();
  
  const [isOpen, setIsOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeDomain, setActiveDomain] = useState<string>('general');
  const [selectedPlan, setSelectedPlan] = useState<any>(null);
  
  const [messages, setMessages] = useState<any[]>([{ role: 'assistant', content: "Hi! I'm Rufus. How can I help you today?" }]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  
  const [loadingEvent, setLoadingEvent] = useState<string>('Understanding request...');
  const [loadingStartTime, setLoadingStartTime] = useState<number | null>(null);
  const [isSending, setIsSending] = useState(false);
  
  const [rawState, setRawState] = useState<any>(null); // For developer inspector
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Custom Event Listener for open-ai-drawer
  useEffect(() => {
    const handleOpenDrawer = (e: any) => {
      setIsOpen(true);
      if (e.detail?.prompt) {
        setInput(e.detail.prompt);
      }
    };
    window.addEventListener('open-ai-drawer', handleOpenDrawer);
    return () => window.removeEventListener('open-ai-drawer', handleOpenDrawer);
  }, []);

  // Fetch Chat History
  const { data: sessions = [], isSuccess: sessionsLoaded } = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: async () => {
      const res = await authFetch('/api/chat/history');
      if (!res.ok) throw new Error('Failed to fetch history');
      return res.json();
    }
  });

  // Session Recovery Guard
  useEffect(() => {
    if (sessionsLoaded) {
      const savedSession = localStorage.getItem('active_chat_session_id');
      const savedDomain = localStorage.getItem('last_active_domain') || 'general';
      const savedPlan = localStorage.getItem('selected_plan');
      
      if (savedSession) {
        const exists = sessions.find((s: any) => s.session_id === savedSession);
        if (exists) {
          setSessionId(savedSession);
          setActiveDomain(savedDomain);
          if (savedPlan) {
            try { setSelectedPlan(JSON.parse(savedPlan)); } catch(e) {}
          }
        } else if (sessions.length > 0) {
          setSessionId(sessions[0].session_id);
        }
      }
    }
  }, [sessionsLoaded, sessions]);

  // Sync to LocalStorage
  useEffect(() => {
    if (sessionId) localStorage.setItem('active_chat_session_id', sessionId);
    if (activeDomain) localStorage.setItem('last_active_domain', activeDomain);
    if (selectedPlan) localStorage.setItem('selected_plan', JSON.stringify(selectedPlan));
  }, [sessionId, activeDomain, selectedPlan]);

  // Load Session Data
  useEffect(() => {
    if (sessionId && !isSending) {
      authFetch(`/api/chat/session/${sessionId}`)
        .then(res => res.json())
        .then(data => {
          if (data.messages && data.messages.length > 0) {
            setMessages(data.messages);
          } else {
            setMessages([{ role: 'assistant', content: "Hi! I'm Rufus. How can I help you today?" }]);
          }
          if (data.state || data.active_domains) {
            const mergedState = { ...(data.state || {}), active_domains: data.active_domains || [] };
            setRawState(mergedState);
            localStorage.setItem('ai_session_id', sessionId);
            localStorage.setItem('ai_active_domains', JSON.stringify(mergedState.active_domains));
            window.dispatchEvent(new CustomEvent('ai-state-updated', { detail: { state: mergedState, sessionId: sessionId } }));
          }
        })
        .catch(err => console.error(err));
    }
  }, [sessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping, isOpen, isHistoryOpen]);

  // Loading Event Polling
  useEffect(() => {
    let interval: any;
    if (isTyping && sessionId) {
      setLoadingStartTime(Date.now());
      interval = setInterval(() => {
        authFetch(`/api/chat/session/${sessionId}`)
          .then(res => res.json())
          .then(data => {
            if (data.session?.execution_audit_trail?.length > 0) {
              const latest = data.session.execution_audit_trail[data.session.execution_audit_trail.length - 1];
              if (latest.event) setLoadingEvent(latest.event + "...");
            }
          }).catch(() => {});
          
        if (loadingStartTime && (Date.now() - loadingStartTime > 20000)) {
           setLoadingEvent("Still working on your request...");
        }
      }, 2000);
    } else {
      setLoadingEvent('Understanding request...');
      setLoadingStartTime(null);
    }
    return () => clearInterval(interval);
  }, [isTyping, sessionId, loadingStartTime]);

  const createSessionMutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch('/api/chat/new-session', { method: 'POST' });
      if (!res.ok) throw new Error('Failed to create session');
      return res.json();
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] });
      setSessionId(data.session_id);
      setIsHistoryOpen(false);
      setMessages([{ role: 'assistant', content: "Hi! I'm Rufus. How can I help you today?" }]);
    }
  });

  const deleteSessionMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await authFetch(`/api/chat/session/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete session');
    },
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] });
      if (sessionId === deletedId) {
        setSessionId(null);
      }
    }
  });

  const sendMessageMutation = useMutation({
    mutationFn: async (message: string) => {
      let targetSession = sessionId;
      if (!targetSession) {
         const d = await authFetch('/api/chat/new-session', { method: 'POST' }).then(r => r.json());
         setSessionId(d.session_id);
         queryClient.invalidateQueries({ queryKey: ['chat-sessions'] });
         targetSession = d.session_id;
      }

      const payloadContext = buildChatContext(pageContext);
      
      const res = await authFetch('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ session_id: targetSession, message, page_context: payloadContext })
      });
      if (!res.ok) throw new Error('Failed to send');
      return { data: await res.json(), targetSession };
    },
    onMutate: (newMsg) => {
      setIsSending(true);
      setMessages(prev => [...prev, { role: 'user', content: newMsg }]);
      setInput('');
      setIsTyping(true);
      setLoadingEvent('Understanding request...');
    },
    onSuccess: ({ data, targetSession }) => {
      setLoadingEvent('Recommendations Ready');
      setTimeout(() => {
        setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
        setIsTyping(false);
        setIsSending(false);
        if (data.state || data.active_domains) {
          const mergedState = { ...(data.state || {}), active_domains: data.active_domains || [] };
          setRawState(mergedState);
          localStorage.setItem('ai_session_id', targetSession || '');
          localStorage.setItem('ai_active_domains', JSON.stringify(mergedState.active_domains));
          window.dispatchEvent(new CustomEvent('ai-state-updated', { detail: { state: mergedState, sessionId: targetSession } }));
        }
        
        // Force shelf to refresh with newly recommended products
        queryClient.invalidateQueries({ queryKey: ['shelf'] });
        
        if (data.cart_items) {
          syncCart(data.cart_items);
        }
      }, 500); // slight delay to show completion event
    },
    onError: () => {
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I encountered an error. Please try again." }]);
      setIsTyping(false);
      setIsSending(false);
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

  const currentPlans = rawState?.domains ? Object.entries(rawState.domains).map(([domain, data]: any) => ({
    domain,
    status: data.plan?.status || 'Active'
  })) : [];

  const isDevMode = import.meta.env.VITE_DEMO_MODE === 'true' || import.meta.env.MODE === 'development';

  return (
    <>
      <div className="fixed bottom-6 right-6 z-40">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={`flex items-center gap-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-full px-4 py-3 shadow-2xl hover:scale-105 transition-transform ${isOpen ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}
        >
          <Sparkles size={20} />
          <span className="font-bold">Ask AI Assistant</span>
        </button>
      </div>

      <div className={`fixed top-0 right-0 h-full w-[400px] bg-white shadow-2xl z-50 transform transition-transform duration-300 ease-in-out flex flex-col ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 p-4 text-white flex items-center justify-between shrink-0 relative z-20">
          <div className="flex items-center gap-2">
            <button onClick={() => setIsHistoryOpen(!isHistoryOpen)} className="p-1 hover:bg-white/20 rounded transition-colors mr-2">
              <History size={20} />
            </button>
            <Sparkles size={24} />
            <div>
              <h2 className="font-bold text-lg leading-tight">AI Assistant</h2>
              <p className="text-xs text-blue-100">Powered by advanced shopping AI</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isDevMode && (
              <button onClick={() => setIsInspectorOpen(!isInspectorOpen)} className="p-1 hover:bg-white/20 rounded transition-colors text-xs font-mono">
                DEV
              </button>
            )}
            <button onClick={() => setIsOpen(false)} className="p-2 hover:bg-white/20 rounded-full transition-colors">
              <X size={20} />
            </button>
          </div>
        </div>

        <div className="relative flex-1 overflow-hidden flex flex-col">
          {/* Developer Inspector */}
          {isDevMode && isInspectorOpen && (
            <div className="absolute inset-x-0 top-0 h-1/2 bg-slate-900 text-green-400 font-mono text-[10px] p-4 overflow-y-auto z-30 shadow-inner">
              <h3 className="text-white font-bold mb-2">WORKSPACE INSPECTOR</h3>
              <p>Active Domain: {activeDomain}</p>
              <pre>{JSON.stringify(rawState, null, 2)}</pre>
            </div>
          )}

          {/* History & Plans Overlay */}
          <div className={`absolute inset-0 bg-white z-20 transform transition-transform duration-300 flex flex-col ${isHistoryOpen ? 'translate-x-0' : '-translate-x-full'}`}>
            <div className="p-4 border-b border-gray-200 flex justify-between items-center bg-gray-50">
              <h3 className="font-semibold text-gray-800">Shopping Sessions</h3>
              <button onClick={() => createSessionMutation.mutate()} className="flex items-center gap-1 text-sm bg-blue-100 text-blue-700 px-3 py-1.5 rounded-full hover:bg-blue-200 transition-colors font-medium">
                <Plus size={16} /> New Chat
              </button>
            </div>
            
            {/* Active Plans Section */}
            {currentPlans.length > 0 && (
              <div className="p-4 border-b border-gray-100">
                <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Active Plans</h4>
                <div className="space-y-1">
                  {currentPlans.map(p => (
                    <div 
                      key={p.domain}
                      onClick={() => setActiveDomain(p.domain)}
                      className={`flex justify-between items-center text-sm p-2 rounded cursor-pointer ${activeDomain === p.domain ? 'bg-purple-50 text-purple-700 font-medium' : 'hover:bg-gray-50 text-gray-600'}`}
                    >
                      <span className="capitalize">{p.domain.replace('_', ' ')}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${p.status === 'Completed' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>{p.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex-1 overflow-y-auto p-2">
               <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2 px-2 mt-2">Recent Chats</h4>
              {sessions.map((s: any) => (
                <div 
                  key={s.session_id}
                  onClick={() => { setSessionId(s.session_id); setIsHistoryOpen(false); }}
                  className={`group flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors mb-1 ${sessionId === s.session_id ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-100 border border-transparent'}`}
                >
                  <div className="flex flex-col overflow-hidden w-full">
                    <div className="flex items-center gap-2">
                      <MessageSquare size={16} className={sessionId === s.session_id ? 'text-blue-600' : 'text-gray-500'} />
                      <span className={`truncate text-sm font-medium ${sessionId === s.session_id ? 'text-blue-800' : 'text-gray-700'}`}>{s.title || 'New Shopping Plan'}</span>
                    </div>
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); deleteSessionMutation.mutate(s.session_id); }} className="opacity-0 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-all ml-2">
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-white shadow-sm ${m.role === 'assistant' ? 'bg-gradient-to-br from-blue-500 to-purple-500' : 'bg-gray-400'}`}>
                  {m.role === 'assistant' ? <Bot size={16} /> : <User size={16} />}
                </div>
                <div className={`max-w-[80%] p-3 text-sm shadow-sm ${m.role === 'assistant' ? 'bg-white rounded-2xl rounded-tl-sm text-gray-800 border border-gray-100' : 'bg-blue-600 rounded-2xl rounded-tr-sm text-white'}`}>
                  {m.role === 'assistant' ? <div dangerouslySetInnerHTML={{ __html: parseMarkdown(m.content || '') }} /> : <p>{m.content || ''}</p>}
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center shrink-0 text-white shadow-sm">
                  <Bot size={16} />
                </div>
                <div className="bg-white border border-gray-100 shadow-sm rounded-2xl rounded-tl-sm p-4 flex flex-col gap-2 min-w-[150px]">
                  <div className="flex items-center gap-1">
                     <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                     <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                     <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                  <span className="text-[10px] text-gray-500 font-medium uppercase tracking-wider flex items-center gap-1">
                    <Activity size={10} /> {loadingEvent}
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="p-4 bg-white border-t border-gray-200 shrink-0">
            <form onSubmit={handleSubmit} className="relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask me anything..."
                className="w-full bg-gray-100 border-none rounded-xl pl-4 pr-12 py-3 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none h-12 scrollbar-custom block"
                rows={1}
                disabled={isTyping}
              />
              <button type="submit" disabled={!input.trim() || isTyping} className="absolute right-1 top-1 bottom-1 w-10 flex items-center justify-center text-blue-600 disabled:opacity-50 hover:bg-blue-50 rounded-lg transition-colors">
                <Send size={18} />
              </button>
            </form>
          </div>
        </div>
      </div>
    </>
  );
}
