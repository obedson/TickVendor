import { useEffect, useState } from 'react';
import { apiJson, getLiveToken } from './api';
import { GovernanceConfirm } from './GovernanceConfirm';

export function CommunityAccessEditor({ token, communityId }: { token: string; communityId: string }) {
  const [access, setAccess] = useState('invite_only');
  const [visible, setVisible] = useState(true);
  const [ready, setReady] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    apiJson<{ membership_access: string; is_public: boolean }>(`communities/${communityId}`, {}, getLiveToken() ?? token).then(item => { setAccess(item.membership_access); setVisible(item.is_public); setReady(true); }).catch(cause => setError(cause.message));
  }, [token, communityId]);
  return <details className="panel"><summary>Community membership policy</summary><p>Visibility controls discovery. Access policy controls how participants become members.</p>{error && <p className="error" role="alert">{error}</p>}
    <label>Membership access<select disabled={!ready} value={access} onChange={event => setAccess(event.target.value)}><option value="open">Open</option><option value="approval_required">Approval required</option><option value="invite_only">Invite only</option></select></label>
    <label><input type="checkbox" checked={visible} onChange={event => setVisible(event.target.checked)} /> Publicly discoverable</label><button disabled={!ready} onClick={() => setConfirming(true)}>Save membership policy</button>
    {confirming && <GovernanceConfirm title="Change membership policy" consequence="This changes discovery and new join requests. Existing memberships are retained." requireReason={false} onClose={() => setConfirming(false)} onConfirm={async () => { await apiJson(`communities/${communityId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ membership_access: access, is_public: visible }) }, getLiveToken() ?? token); }} />}
  </details>;
}
