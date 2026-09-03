import Link from 'next/link';

export function MarketingFooter() {
  return (
    <footer className="marketing-footer">
      <div className="marketing-footer-wrap">
        <div>
          <strong>Release Manager</strong>
          <p>Evidence-led releases, governed by people.</p>
        </div>
        <nav aria-label="Footer navigation">
          <Link href="/">Product</Link>
          <Link href="/about">About</Link>
          <Link href="/contact">Contact</Link>
          <Link href="/login">Sign in</Link>
        </nav>
        <p className="marketing-maker">Built by Shipyard, Herald&apos;s product-building platform.</p>
      </div>
    </footer>
  );
}
