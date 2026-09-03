import Link from 'next/link';
import { hasSession } from '@/lib/session';

// Public marketing landing page. Server component; reads cookie presence only
// (never calls the API), so it renders identically with or without a backend
// and exposes no release, operation, or repository data in either state.
export default async function Home() {
  const authed = await hasSession();
  return (
    <main className="editorial">
      <p className="eyebrow">Release Manager</p>
      <h1>Evidence in. Governed releases out.</h1>
      <p className="lede">
        Release Manager turns a codebase scan into a reviewable release pack —
        rationale, notes, and the change history behind them — then holds
        publication until a named human approves it with a reason. Every scan,
        decision, and publication attempt is recorded for audit.
      </p>
      <div className="cta-row">
        {authed ? (
          <Link className="button" href="/dashboard">
            Go to dashboard
          </Link>
        ) : (
          <>
            <Link className="button" href="/login">
              Open the console
            </Link>
            <a className="button" href="/auth/github">
              Login with GitHub
            </a>
          </>
        )}
      </div>
    </main>
  );
}
