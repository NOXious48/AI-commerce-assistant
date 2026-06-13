import { useState } from 'react';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Usually calls an API to send reset link
    setSuccess('If an account with that email exists, we have sent a password reset link.');
  };

  return (
    <div className="flex h-screen items-center justify-center bg-bg-primary">
      <div className="w-full max-w-md p-8 bg-bg-card rounded-2xl shadow-lg border border-border-light">
        <div className="flex justify-center mb-6">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent to-orange-500 flex items-center justify-center text-xl font-bold text-white">
            A
          </div>
        </div>
        <h2 className="text-2xl font-bold text-center text-text-primary mb-2">Reset Password</h2>
        <p className="text-sm text-center text-text-muted mb-6">Enter your email to receive a reset link</p>
        
        {success && (
          <div className="mb-4 p-3 bg-success/10 border border-success/50 rounded-lg text-success text-sm text-center">
            {success}
          </div>
        )}

        {!success ? (
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
            <button 
              type="submit" 
              className="w-full mt-2 py-2.5 bg-gradient-to-r from-accent to-orange-500 hover:from-accent hover:to-orange-400 text-white font-semibold rounded-lg transition-transform hover:scale-[1.02]"
            >
              Send Reset Link
            </button>
          </form>
        ) : null}

        <div className="text-center mt-6 text-sm">
          <a href="/login" className="text-accent hover:text-accent-light font-medium transition-colors">
            Back to Sign in
          </a>
        </div>
      </div>
    </div>
  );
}
