import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export default function Login() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Redirect if already logged in
  React.useEffect(() => {
    if (isAuthenticated) {
      navigate('/');
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/'); // Redirect to dashboard after login
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-bg-primary">
      <div className="w-full max-w-md p-8 bg-bg-card rounded-2xl shadow-lg border border-border-light">
        <div className="flex justify-center mb-6">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent to-orange-500 flex items-center justify-center text-xl font-bold text-white">
            A
          </div>
        </div>
        <h2 className="text-2xl font-bold text-center text-text-primary mb-2">Welcome Back</h2>
        <p className="text-sm text-center text-text-muted mb-6">Sign in to your AI Commerce Assistant</p>
        
        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Email</label>
            <input 
              type="email" 
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full px-4 py-2 bg-bg-secondary border border-border-light rounded-lg focus:outline-none focus:border-accent text-text-primary"
              required 
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Password</label>
            <input 
              type="password" 
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-4 py-2 bg-bg-secondary border border-border-light rounded-lg focus:outline-none focus:border-accent text-text-primary"
              required 
            />
          </div>
          <button 
            type="submit" 
            disabled={loading}
            className="w-full mt-2 py-2.5 bg-gradient-to-r from-accent to-orange-500 hover:from-accent hover:to-orange-400 text-white font-semibold rounded-lg transition-transform hover:scale-[1.02] disabled:opacity-50 disabled:hover:scale-100"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>

          <div className="flex items-center justify-between mt-4 text-sm">
            <a href="/forgot-password" className="text-accent hover:text-accent-light transition-colors">
              Forgot password?
            </a>
            <span className="text-text-muted">
              Don't have an account?{' '}
              <a href="/signup" className="text-accent hover:text-accent-light font-medium transition-colors">
                Sign up
              </a>
            </span>
          </div>
        </form>
      </div>
    </div>
  );
}
