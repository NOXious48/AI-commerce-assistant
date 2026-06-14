import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';

export default function Verify() {
  const { verify, resendCode } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Extract email from query params if passed
    const params = new URLSearchParams(location.search);
    const emailParam = params.get('email');
    if (emailParam) setEmail(emailParam);
  }, [location.search]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      await verify(email, code);
      setSuccess('Email verified successfully! Redirecting to login...');
      setTimeout(() => navigate('/login'), 2000);
    } catch (err: any) {
      setError(err.message || 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (!email) {
      setError('Please enter your email first.');
      return;
    }
    setError('');
    setSuccess('');
    try {
      await resendCode(email);
      setSuccess('Verification code resent! Please check your email.');
    } catch (err: any) {
      setError(err.message || 'Failed to resend code');
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
        <h2 className="text-2xl font-bold text-center text-text-primary mb-2">Verify Email</h2>
        <p className="text-sm text-center text-text-muted mb-6">Enter the code sent to your email</p>
        
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

        <form onSubmit={handleSubmit} className="flex flex-col gap-4" autoComplete="off">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Email</label>
            <input 
              type="email" 
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full px-4 py-2 bg-bg-secondary border border-border-light rounded-lg focus:outline-none focus:border-accent text-text-primary"
              required 
              autoComplete="one-time-code"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Verification Code</label>
            <input 
              type="text" 
              value={code}
              onChange={e => setCode(e.target.value)}
              className="w-full px-4 py-2 bg-bg-secondary border border-border-light rounded-lg focus:outline-none focus:border-accent text-text-primary"
              required 
              autoComplete="one-time-code"
            />
          </div>
          <button 
            type="submit" 
            disabled={loading}
            className="w-full mt-2 py-2.5 bg-gradient-to-r from-accent to-orange-500 hover:from-accent hover:to-orange-400 text-white font-semibold rounded-lg transition-transform hover:scale-[1.02] disabled:opacity-50 disabled:hover:scale-100"
          >
            {loading ? 'Verifying...' : 'Verify Email'}
          </button>

          <div className="text-center mt-4 text-sm text-text-muted">
            Didn't receive the code?{' '}
            <button type="button" onClick={handleResend} className="text-accent hover:text-accent-light font-medium transition-colors">
              Resend Code
            </button>
          </div>
          <div className="text-center mt-2 text-sm text-text-muted">
            <a href="/login" className="text-accent hover:text-accent-light font-medium transition-colors">
              Back to Login
            </a>
          </div>
        </form>
      </div>
    </div>
  );
}
