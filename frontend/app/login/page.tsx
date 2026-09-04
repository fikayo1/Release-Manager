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
    <main className="editorial login-page">
      <section className="login-card" aria-labelledby="login-title">
        <p className="eyebrow">Release Manager</p>
        <h1 id="login-title">Sign in to the console</h1>
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
            <svg className="github-icon" aria-hidden="true" viewBox="0 0 24 24"><path fill="currentColor" d="M12 .7a11.5 11.5 0 0 0-3.64 22.4c.58.1.79-.25.79-.56v-2.23c-3.22.7-3.9-1.37-3.9-1.37-.52-1.34-1.28-1.7-1.28-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.57-.29-5.27-1.28-5.27-5.69 0-1.26.45-2.28 1.18-3.09-.12-.29-.51-1.47.11-3.05 0 0 .96-.31 3.16 1.18a10.9 10.9 0 0 1 5.75 0c2.2-1.49 3.16-1.18 3.16-1.18.62 1.58.23 2.76.11 3.05.74.81 1.18 1.83 1.18 3.09 0 4.42-2.71 5.39-5.29 5.68.42.36.79 1.07.79 2.16v3.2c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .7Z"/></svg>
            Login with GitHub
          </a>
          <Link href="/">Back to overview</Link>
        </div>
      </section>
    </main>
  );
}
