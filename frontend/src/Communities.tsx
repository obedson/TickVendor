import { CommunityLifecycle } from './CommunityLifecycle';
export function Communities({ token, isSuperAdmin, isEmailVerified }: { token: string; isSuperAdmin?: boolean; isEmailVerified?: boolean }) {
  return <CommunityLifecycle isSuperAdmin={isSuperAdmin} isEmailVerified={isEmailVerified} token={token} />;
}
