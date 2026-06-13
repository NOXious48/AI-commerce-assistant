import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      await signup(email, password, fullName);
      setSuccess('Signup successful! Please check your email to verify your account.');
      // Keep them on this page to read the message, or redirect to a verify page
    } catch (err: any) {
      setError(err.message || 'Signup failed');
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
        <h2 className="text-2xl font-bold text-center text-text-primary mb-2">Create an Account</h2>
        <p className="text-sm text-center text-text-muted mb-6">Join the AI Commerce Assistant</p>
        
        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}
        {success && (
          <div className="mb-4 p-3 bg-success/10 border border-success/50 rounded-lg text-success text-sm">
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Full Name</label>
            <input 
              type="text" 
              value={fullName}
              onChange={e => setFullName(e.target.value)}
              className="w-full px-4 py-2 bg-bg-secondary border border-border-light rounded-lg focus:outline-none focus:border-accent text-text-primary"
              required 
            />
          </div>
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
              minLength={8}
            />
          </div>
          <button 
            type="submit" 
            disabled={loading}
            className="w-full mt-2 py-2.5 bg-gradient-to-r from-accent to-orange-500 hover:from-accent hover:to-orange-400 text-white font-semibold rounded-lg transition-transform hover:scale-[1.02] disabled:opacity-50 disabled:hover:scale-100"
          >
            {loading ? 'Creating Account...' : 'Sign Up'}
          </button>

          <div className="text-center mt-4 text-sm text-text-muted">
            Already have an account?{' '}
            <a href="/login" className="text-accent hover:text-accent-light font-medium transition-colors">
              Sign in
            </a>
          </div>
        </form>
      </div>
    </div>
  );
}
