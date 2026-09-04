export const dynamic = 'force-dynamic';
import { api } from '@/lib/api';
import { guard } from '@/lib/session';
import { GitHubRepositoryForm, Repository } from '@/components/GitHubRepositoryForm';

type Connection = {
  status: string;
  account: string | null;
  selected_repository: string | null;
  repositories: Repository[];
  authorize_url: string;
};

export default async function GitHubSettings({
  searchParams,
}: {
  searchParams: Promise<{ github?: string }>;
}) {
  const [data, query] = await Promise.all([
    guard(() => api<Connection>('/api/github')),
    searchParams,
  ]);
  const alerts: Record<string, string> = {
    connected: 'GitHub connected. Select a repository below.',
    denied: 'GitHub authorization was denied.',
    invalid_state: 'The authorization request expired or was invalid. Try again.',
    exchange_failed: 'GitHub could not be connected. Try again.',
  };
  return (
    <section>
      <h1>Repos</h1>
      <p>Connect GitHub and choose the repository Release Manager should scan.</p>
      {query.github && alerts[query.github] && (
        <p className="alert" role="alert">
          {alerts[query.github]}
        </p>
      )}
      {data.status !== 'connected' ? (
        <>
          <p>
            {data.status === 'revoked'
              ? 'Your GitHub connection was revoked. Reconnect to continue.'
              : 'Connect GitHub to choose a repository and run scans.'}
          </p>
          <a className="button" href={data.authorize_url}>
            Continue with GitHub
          </a>
        </>
      ) : (
        <>
          <p>
            Connected as <strong>{data.account}</strong>.
          </p>
          <GitHubRepositoryForm
            repositories={data.repositories}
            selected={data.selected_repository}
          />
        </>
      )}
    </section>
  );
}
