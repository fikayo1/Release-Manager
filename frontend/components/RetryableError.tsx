'use client';

// A bounded, retryable error state. The Retry button re-runs the failed
// server render via the route boundary's `reset()` — no full browser reload.
export function RetryableError({
  reset,
  title = 'Something went wrong',
  message = 'The release service could not be reached. This is usually temporary.',
}: {
  reset: () => void;
  title?: string;
  message?: string;
}) {
  return (
    <div className="card" role="alert">
      <h1>{title}</h1>
      <p>{message}</p>
      <button type="button" className="retry" onClick={() => reset()}>
        Retry
      </button>
    </div>
  );
}
