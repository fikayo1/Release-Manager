// Fixed-dimension, accessible loading placeholder. Reserves layout so the
// real content does not shift in when it arrives, and honours
// prefers-reduced-motion via the `.skeleton` rules in globals.css.
export function Skeleton({ label = 'Loading…', rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div className="skeleton" role="status" aria-busy="true" aria-live="polite">
      <span className="visually-hidden">{label}</span>
      <div className="skeleton-block skeleton-title" aria-hidden="true" />
      {Array.from({ length: rows }).map((_, i) => (
        <div className="skeleton-block skeleton-line" aria-hidden="true" key={i} />
      ))}
    </div>
  );
}
