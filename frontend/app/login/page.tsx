import Link from 'next/link';

// Dedicated editorial sign-in page. Server component, no session data. The one
// prominent control is a link to `/auth/github` (the existing, unchanged OAuth
// initiation route). Shows an inline alert when the backend bounced an OAuth
// failure back as `?error=<status>`.
const ERRORS: Record<string, string> = {
  denied: 'GitHub authorization was denied. Try again to continue.',
  invalid_state: 'The sign-in request expired or was invalid. Start again.',
  exchange_failed: 'GitHub could not complete the sign-in. Try again.',
};

export default async function Login({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  const message = error ? ERRORS[error] ?? 'Sign-in could not be completed. Try again.' : null;
  return (
    <main className="editorial">
      <p className="eyebrow">Release Manager</p>
      <h1>Sign in to the console</h1>
      <p className="lede">
        Access is a single GitHub account. Authorize the <code>repo</code> scope
        once; tokens stay on the server and never reach your browser.
      </p>
      {message && (
        <p className="alert" role="alert">
          {message}
        </p>
      )}
      <div className="cta-row">
        <a className="button" href="/auth/github">
          Continue with GitHub
        </a>
        <Link href="/">Back to overview</Link>
      </div>
    </main>
  );
}
