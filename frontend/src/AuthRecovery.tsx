import { useEffect, useState } from 'react';
import { API_BASE, clearSession, type SessionData } from './api';
import { PasswordInput } from './PasswordInput';
import { useRevealFocus } from './RevealFocus';

const returnData = new URLSearchParams(window.location.hash.slice(1) || window.location.search);
const proofKey = 'tickvendor.google-proof';

export const googleErrors: Record<string, string> = {
  cancelled: 'Google sign-in was cancelled.',
  provider_denied: 'Google did not approve sign-in. Please try again.',
  invalid_state: 'Google sign-in expired or did not start in this browser. Please start again.',
  provider_failure: 'Google sign-in could not be verified. Please try again.',
  unavailable: 'Google sign-in is not configured. Use email and password.',
};

async function authPost(path: string, body: object) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(`${API_BASE}/auth/${path}`, { method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Unable to complete this request. Check your input and try again.');
    return data;
  } finally { window.clearTimeout(timeout); }
}

export async function googleStart() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  const encode = (data: Uint8Array) => btoa(String.fromCharCode(...data)).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
  const verifier = encode(bytes);
  const challenge = encode(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
  sessionStorage.setItem(proofKey, JSON.stringify({ verifier, at: Date.now() }));
  window.location.assign(`${API_BASE}/auth/google/start?handoff_challenge=${challenge}`);
}

export function GoogleButton() {
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/auth/google/config`).then(response => response.json()).then(data => { if (active) setEnabled(data.enabled === true); }).catch(() => { if (active) setError('Google sign-in availability could not be checked.'); });
    return () => { active = false; };
  }, []);
  return <div className="google-auth"><div className="auth-divider">OR</div>
    <button className="secondary" type="button" disabled={!enabled} onClick={() => { void googleStart().catch(() => setError('Unable to start Google sign-in. Allow browser storage and try again.')); }}>Continue with Google</button>
    {!enabled && <small>Google sign-in is unavailable until configured.</small>}{error && <p role="alert">{error}</p>}
  </div>;
}

export function PasswordRecovery({ reset = false }: { reset?: boolean }) {
  const [email, setEmail] = useState('');
  const [token] = useState(() => returnData.get('token') || '');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState(reset && !token ? 'This password reset link is invalid or has expired.' : '');
  useRevealFocus(error || success, '#recovery-result');
  useEffect(() => { if (reset) window.history.replaceState(null, '', '/reset-password'); }, [reset]);
  return <main className="auth"><section className="panel" aria-labelledby="recovery-title">
    <h1 id="recovery-title">{reset ? 'Reset password' : 'Forgot password?'}</h1>
    <p>{reset ? 'Choose a new password with at least 12 characters (maximum 72 UTF-8 bytes).' : 'Enter your email to request password reset instructions.'}</p>
    {(error || success) && <p id="recovery-result" role={error ? 'alert' : 'status'}>{error || success}</p>}
    {!success && <form onSubmit={async event => {
      event.preventDefault(); setError('');
      if (reset && password !== confirm) { setError('Passwords do not match.'); return; }
      if (reset && new TextEncoder().encode(password).length > 72) { setError('Password must not exceed 72 UTF-8 bytes.'); return; }
      setBusy(true);
      try {
        await authPost(reset ? 'password-reset/confirm' : 'password-reset/request', reset ? { token, new_password: password } : { email });
        if (reset) { clearSession(); setPassword(''); setConfirm(''); }
        setSuccess(reset ? 'Password reset successfully. Sign in with your new password.' : "If an account exists for that email, we'll send password reset instructions.");
      } catch (cause) { setError(cause instanceof Error && cause.name !== 'AbortError' ? cause.message : 'The request took too long. Please try again.'); }
      finally { setBusy(false); }
    }}>
      {reset ? <>
        <PasswordInput label="New password" required minLength={12} maxLength={72} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} aria-describedby={error ? 'recovery-result' : undefined} />
        <PasswordInput label="Confirm new password" required minLength={12} maxLength={72} autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)} aria-describedby={error ? 'recovery-result' : undefined} />
      </> : <label>Email address<input required type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} /></label>}
      <button disabled={busy || reset && !token}>{busy ? 'Working…' : reset ? 'Reset password' : 'Send reset instructions'}</button>
    </form>}
    {busy && <p role="status">Submitting securely…</p>}
    <div className="auth-footer"><a href="/">Back to sign in</a>{reset && error && <a href="/forgot-password">Request a new reset link</a>}</div>
  </section></main>;
}

export function GoogleReturn({ onLogin }: { onLogin: (session: SessionData) => void }) {
  const [grant] = useState(() => returnData.get('grant') || '');
  const [error, setError] = useState(() => googleErrors[returnData.get('error') || ''] || (!grant ? 'Google sign-in could not be completed. Please start again.' : ''));
  const [password, setPassword] = useState('');
  const [linking, setLinking] = useState(false);
  const [busy, setBusy] = useState(false);
  useRevealFocus(error, '#google-result');
  useEffect(() => { window.history.replaceState(null, '', '/auth/google/return'); }, []);
  return <main className="auth"><section className="panel" aria-labelledby="google-title"><h1 id="google-title">Complete Google sign-in</h1>
    <p>Finish securely in TickVendor. Existing accounts may require confirmation before linking.</p>
    {error && <p id="google-result" role="alert">{error}</p>}
    {grant && <form onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError('');
      try {
        const proof = JSON.parse(sessionStorage.getItem(proofKey) || '{}');
        if (!proof.verifier || Date.now() - proof.at > 12 * 60000) throw new Error(googleErrors.invalid_state);
        const session = await authPost('google/complete', { grant, verifier: proof.verifier, ...(linking ? { password } : {}) });
        sessionStorage.removeItem(proofKey); setPassword(''); window.history.replaceState(null, '', '/'); onLogin(session);
      } catch (cause) {
        const message = cause instanceof Error && cause.name !== 'AbortError' ? cause.message : 'Google sign-in could not finish in time. Please try again.';
        setLinking(message.startsWith('Confirm your existing TickVendor password') || linking); setError(message);
      } finally { setBusy(false); }
    }}>
      {linking && <PasswordInput label="Existing TickVendor password" required autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} />}
      <button disabled={busy}>{busy ? 'Signing in…' : linking ? 'Confirm and link Google' : 'Complete sign-in'}</button>
    </form>}
    {busy && <p role="status">Verifying your sign-in…</p>}
    <div className="auth-footer"><a href="/">Back to sign in</a><a href="/forgot-password">Forgot password?</a></div>
  </section></main>;
}
