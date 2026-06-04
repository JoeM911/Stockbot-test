import { useState } from 'react';

export default function Login({ onAuth }) {
  const [pw, setPw]         = useState('');
  const [error, setError]   = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pw }),
      });
      const data = await res.json();
      if (data.ok) {
        onAuth();
      } else {
        setError('Wrong password');
      }
    } catch {
      setError('Cannot reach server');
    }
    setLoading(false);
  };

  return (
    <div className="login-screen">
      <div className="login-box">
        <div className="login-brand">STOCKBOT</div>
        <div className="login-sub">TERMINAL</div>
        <form onSubmit={submit} className="login-form">
          <input
            className="t-input login-input"
            type="password"
            placeholder="Password"
            value={pw}
            onChange={e => setPw(e.target.value)}
            autoFocus
          />
          <button className="btn-neutral login-btn" type="submit" disabled={loading}>
            {loading ? 'CONNECTING…' : 'ENTER'}
          </button>
        </form>
        {error && <div className="cmd-err" style={{ marginTop: 8, textAlign: 'center' }}>{error}</div>}
      </div>
    </div>
  );
}
