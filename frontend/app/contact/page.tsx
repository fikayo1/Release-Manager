import type {Metadata} from 'next';
import Link from 'next/link';
import {MarketingShell} from '@/components/MarketingShell';

export const metadata: Metadata = {
  title: 'Contact | Release Manager',
  description: 'Release Manager contact capability is coming soon.',
};

export default function ContactPage() {
  return (
    <MarketingShell pageClass="marketing-simple marketing-contact">
      <section className="marketing-page-hero">
        <p className="marketing-status">Coming soon</p>
        <p className="marketing-kicker">Contact</p>
        <h1>A direct line is<br />still being built.</h1>
        <p className="marketing-lede">
          Contact capability is not available yet. There is no form or active
          contact channel on this page today.
        </p>
        <Link className="button" href="/">Back to the product</Link>
      </section>
    </MarketingShell>
  );
}
