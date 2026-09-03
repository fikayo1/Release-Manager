import Link from 'next/link';

export function MarketingHeader() {
  return (
    <header className="marketing-header">
      <div className="marketing-nav-wrap">
        <Link className="marketing-brand" href="/" aria-label="Release Manager home">
          <span aria-hidden="true">RM</span>
          <strong>Release Manager</strong>
        </Link>
        <nav className="marketing-nav" aria-label="Primary navigation">
          <Link href="/">Product</Link>
          <Link href="/about">About</Link>
          <Link href="/contact">Contact</Link>
          <Link className="marketing-nav-login" href="/login">Sign in</Link>
        </nav>
      </div>
    </header>
  );
}
