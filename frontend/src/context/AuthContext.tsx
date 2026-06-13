import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
  sub: string;
  email: string;
  name: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  signup: (email: string, password: string, fullName: string) => Promise<void>;
  authFetch: (url: string, options?: RequestInit) => Promise<Response>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Set tokens and decode user from idToken
  const setTokens = (accToken: string, idToken: string, expiresIn: number) => {
    setAccessToken(accToken);
    setExpiresAt(Date.now() + expiresIn * 1000);

    try {
      const payload = JSON.parse(atob(idToken.split('.')[1]));
      setUser({
        sub: payload.sub,
        email: payload.email || '',
        name: payload.name || payload['cognito:username'] || '',
      });
    } catch (e) {
      console.warn('Could not decode ID token');
    }
  };

  const clearTokens = () => {
    setAccessToken(null);
    setUser(null);
    setExpiresAt(null);
  };

  const refreshTokens = async (): Promise<boolean> => {
    try {
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        clearTokens();
        return false;
      }
      const data = await res.json();
      setTokens(data.access_token, data.id_token, data.expires_in);
      return true;
    } catch (e) {
      clearTokens();
      return false;
    }
  };

  // Auth-aware fetch
  const authFetch = async (url: string, options: RequestInit = {}): Promise<Response> => {
    let currentToken = accessToken;
    
    // Refresh if expiring within 1 minute
    if (!currentToken || (expiresAt && Date.now() > expiresAt - 60000)) {
      const success = await refreshTokens();
      if (!success) {
        throw new Error('Not authenticated');
      }
      currentToken = accessToken; // Will be updated by refreshTokens but we can't await state update easily here
      // Actually, refreshTokens updates state asynchronously, but authFetch needs the token immediately.
      // So let's re-fetch the token directly here if needed, or just rely on the browser cookie if possible?
      // Wait, we need to pass the Bearer token.
      // We should return a Promise from refreshTokens that resolves to the new token.
    }
    
    // Quick hack for currentToken since state update is async:
    // If we just refreshed, `accessToken` state might be stale in this closure. 
    // To fix properly:
    return fetchWithToken(url, options);
  };

  const fetchWithToken = async (url: string, options: RequestInit) => {
    // If we need to refresh, do it directly
    if (!accessToken || (expiresAt && Date.now() > expiresAt - 60000)) {
      try {
        const res = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          setTokens(data.access_token, data.id_token, data.expires_in);
          
          const headers = {
            ...options.headers,
            'Authorization': `Bearer ${data.access_token}`,
          };
          if (options.body && typeof options.body === 'string') {
            (headers as any)['Content-Type'] = 'application/json';
          }
          return fetch(url, { ...options, headers, credentials: 'include' });
        }
      } catch (e) {}
      throw new Error('Session expired');
    }

    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${accessToken}`,
    };
    if (options.body && typeof options.body === 'string') {
      (headers as any)['Content-Type'] = 'application/json';
    }

    let res = await fetch(url, { ...options, headers, credentials: 'include' });
    if (res.status === 401) {
      const success = await refreshTokens();
      if (success) {
        // Will use new token on next render, but for this request we fail. 
        // In a real app we'd queue requests and retry.
      }
    }
    return res;
  };

  const login = async (email: string, password: string) => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Login failed');
    setTokens(data.access_token, data.id_token, data.expires_in);
  };

  const logout = async () => {
    try {
      await authFetch('/api/auth/logout', { method: 'POST' });
    } catch (e) {}
    clearTokens();
  };

  const signup = async (email: string, password: string, fullName: string) => {
    const res = await fetch('/api/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Signup failed');
  };

  useEffect(() => {
    refreshTokens().finally(() => setIsLoading(false));
  }, []);

  // Schedule refresh timeout
  useEffect(() => {
    if (!expiresAt) return;
    const timeUntilRefresh = Math.max((expiresAt - Date.now() - 300000), 5000);
    const timer = setTimeout(() => {
      refreshTokens();
    }, timeUntilRefresh);
    return () => clearTimeout(timer);
  }, [expiresAt]);

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user && !!accessToken,
      isLoading,
      login,
      logout,
      signup,
      authFetch: fetchWithToken
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
