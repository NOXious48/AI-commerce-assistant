import React from 'react';
import { Plus, MessageSquare, LogOut, Heart, Settings, Trash2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

interface SidebarProps {
  currentSessionId: string | null;
  onSelectSession: (id: string) => void;
}

export default function Sidebar({ currentSessionId, onSelectSession }: SidebarProps) {
  const { user, logout, authFetch } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: sessions = [] } = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: async () => {
      const res = await authFetch('/api/chat/history');
      if (!res.ok) throw new Error('Failed to fetch history');
      return res.json();
    }
  });

  const createSessionMutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch('/api/chat/new-session', { method: 'POST' });
      if (!res.ok) throw new Error('Failed to create session');
      return res.json();
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] });
      onSelectSession(data.session_id);
    }
  });

  const deleteSessionMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await authFetch(`/api/chat/session/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete session');
    },
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['chat-sessions'] });
      if (currentSessionId === deletedId) {
        onSelectSession('');
      }
    }
  });

  return (
    <div className="w-[20%] min-w-[260px] bg-sidebar-bg border-r border-border-light flex flex-col h-full">
      <div className="p-4 border-b border-border-light flex justify-between items-center">
        <h3 className="font-semibold text-sm tracking-wide">Chat History</h3>
        <button 
          onClick={() => createSessionMutation.mutate()}
          className="p-1.5 bg-gradient-to-br from-accent to-orange-500 rounded-lg text-white hover:scale-105 transition-transform"
          title="New Chat"
        >
          <Plus size={18} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 scrollbar-custom space-y-1">
        {sessions.map((s: any) => (
          <div 
            key={s.session_id}
            onClick={() => onSelectSession(s.session_id)}
            className={`group flex items-center justify-between p-2.5 rounded-lg cursor-pointer transition-colors text-sm
              ${currentSessionId === s.session_id ? 'bg-accent-glow text-text-primary' : 'text-text-secondary hover:bg-sidebar-hover'}`}
          >
            <div className="flex items-center gap-3 overflow-hidden">
              <MessageSquare size={16} className="shrink-0 opacity-70" />
              <span className="truncate">{s.title || 'New Chat'}</span>
            </div>
            <button 
              onClick={(e) => { e.stopPropagation(); deleteSessionMutation.mutate(s.session_id); }}
              className="opacity-0 group-hover:opacity-100 p-1 text-text-muted hover:text-red-500 transition-all"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>

      <div className="p-4 border-t border-border-light space-y-4">
        <div className="flex gap-2 text-sm text-text-secondary">
          <button onClick={() => navigate('/saved-products')} className="flex items-center gap-2 hover:text-accent transition-colors">
            <Heart size={16} /> Saved
          </button>
          <button onClick={() => navigate('/preferences')} className="flex items-center gap-2 hover:text-accent transition-colors ml-auto">
            <Settings size={16} /> Prefs
          </button>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-orange-500 flex items-center justify-center font-bold text-white shrink-0">
            {user?.name?.[0]?.toUpperCase() || '?'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{user?.name || 'Loading...'}</div>
            <div className="text-xs text-text-muted truncate">{user?.email}</div>
          </div>
          <button onClick={logout} className="p-1.5 text-text-muted hover:text-red-500 transition-colors">
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
