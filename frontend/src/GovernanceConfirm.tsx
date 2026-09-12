import { useEffect, useRef, useState, type ReactNode } from 'react';

export function GovernanceConfirm({ title, consequence, onConfirm, onClose, children, requireReason = true }: {
  title: string; consequence: string; onConfirm: (reason: string) => Promise<void>; onClose: () => void;
  children?: ReactNode; requireReason?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const element = dialog.current;
    element?.showModal();
    return () => { element?.close(); previous?.focus(); };
  }, []);
  return <dialog ref={dialog} className="panel management-screen governance-dialog" aria-labelledby="governance-confirm-title" onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <form onSubmit={async event => { event.preventDefault(); setBusy(true); setError(''); try { await onConfirm(reason.trim()); onClose(); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Action failed.'); } finally { setBusy(false); } }}>
      <h2 id="governance-confirm-title">{title}</h2><p>{consequence}</p>{children}
      {requireReason && <label>Reason<textarea autoFocus required minLength={3} maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} /></label>}
      {error && <p role="alert" className="error">{error}</p>}
      <div className="form-actions"><button disabled={busy || requireReason && reason.trim().length < 3}>{busy ? 'Saving…' : 'Confirm'}</button><button type="button" className="secondary" disabled={busy} onClick={onClose}>Cancel</button></div>
    </form>
  </dialog>;
}
