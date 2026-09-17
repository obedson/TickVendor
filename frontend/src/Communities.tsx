import { CommunityLifecycle } from './CommunityLifecycle';
export function Communities({ token, isSuperAdmin }: { token: string; isSuperAdmin?: boolean }) {
  return <CommunityLifecycle isSuperAdmin={isSuperAdmin} token={token} />;
}
