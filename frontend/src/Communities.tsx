import { CommunityLifecycle } from './CommunityLifecycle';
export function Communities({ token }: { token: string }) {
  return <CommunityLifecycle token={token} />;
}
