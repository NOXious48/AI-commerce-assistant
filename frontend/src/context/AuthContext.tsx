import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';

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
  verify: (email: string, code: string) => Promise<void>;
  resendCode: (email: string) => Promise<void>;
  authFetch: (url: string, options?: RequestInit) => Promise<Response>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true';

  const [user, setUser] = useState<User | null>(
    isDemoMode ? { sub: 'local_demo_user', email: 'demo@example.com', name: 'Demo User' } : null
  );
  const [accessToken, setAccessToken] = useState<string | null>(isDemoMode ? 'demo_token' : null);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(!isDemoMode);

  const setTokens = (accToken: string, idToken: string, expiresIn: number) => {
    if (isDemoMode) return;
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
    if (isDemoMode) return;
    setAccessToken(null);
    setUser(null);
    setExpiresAt(null);
  };

  const refreshTokens = async (): Promise<boolean> => {
    if (isDemoMode) return true;
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

  const fetchWithToken = async (url: string, options: RequestInit = {}) => {
    if (isDemoMode) {
      const headers = {
        ...options.headers,
        'Authorization': `Bearer demo_token`,
      };
      if (options.body && typeof options.body === 'string') {
        (headers as any)['Content-Type'] = 'application/json';
      }
      return fetch(url, { ...options, headers, credentials: 'include' });
    }

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
      }
    }
    return res;
  };

  const login = async (email: string, password: string) => {
    if (isDemoMode) return;
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
    if (isDemoMode) return;
    try {
      await fetchWithToken('/api/auth/logout', { method: 'POST' });
    } catch (e) {}
    clearTokens();
  };

  const signup = async (email: string, password: string, fullName: string) => {
    if (isDemoMode) return;
    const res = await fetch('/api/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Signup failed');
  };

  const verify = async (email: string, code: string) => {
    if (isDemoMode) return;
    const res = await fetch('/api/auth/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, code }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Verification failed');
  };

  const resendCode = async (email: string) => {
    if (isDemoMode) return;
    const res = await fetch('/api/auth/resend-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to resend code');
  };

  useEffect(() => {
    if (!isDemoMode) {
      refreshTokens().finally(() => setIsLoading(false));
    }
  }, [isDemoMode]);

  useEffect(() => {
    if (isDemoMode) return;
    if (!expiresAt) return;
    const timeUntilRefresh = Math.max((expiresAt - Date.now() - 300000), 5000);
    const timer = setTimeout(() => {
      refreshTokens();
    }, timeUntilRefresh);
    return () => clearTimeout(timer);
  }, [expiresAt, isDemoMode]);

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated: !!user && !!accessToken,
      isLoading,
      login,
      logout,
      signup,
      verify,
      resendCode,
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
