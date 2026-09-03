import type {Metadata} from 'next';
import Link from 'next/link';
import {MarketingShell} from '@/components/MarketingShell';

export const metadata: Metadata = {
  title: 'About | Release Manager',
  description: 'Why Shipyard built Release Manager for governed, reviewable delivery.',
};

export default function AboutPage() {
  return (
    <MarketingShell pageClass="marketing-simple">
      <section className="marketing-page-hero">
        <p className="marketing-kicker">About</p>
        <h1>Delivery should be fast.<br />Decisions should stay visible.</h1>
        <p className="marketing-lede">
          Release Manager is built by Shipyard to make the evidence, judgment,
          and accountability behind every release part of the work—not an afterthought.
        </p>
      </section>
      <section className="marketing-about-grid" aria-labelledby="origin-title">
        <div>
          <p className="marketing-index">01 / Origin</p>
          <h2 id="origin-title">Built by Shipyard</h2>
        </div>
        <div className="marketing-prose">
          <p>
            Shipyard is Herald&apos;s product-building platform. Release Manager comes
            from that practice: turning a clear product intent into software whose
            operation can be understood and reviewed.
          </p>
          <p>
            That origin shapes a deliberately governed release process. Automation
            assembles evidence and prepares the work; a named human reviews the
            result, records a reason, and decides whether it is ready to publish.
          </p>
          <p>
            The goal is not automation without limits. It is reviewable delivery:
            a practical path from repository change to accountable release, with a
            record teams can return to later.
          </p>
        </div>
      </section>
      <section className="marketing-inline-cta" aria-labelledby="about-cta-title">
        <div><p className="marketing-kicker">See the process</p><h2 id="about-cta-title">Put evidence before action.</h2></div>
        <div className="marketing-actions">
          <Link className="button" href="/">Explore the product</Link>
          <Link className="marketing-text-link" href="/login">Open the console <span aria-hidden="true">→</span></Link>
        </div>
      </section>
    </MarketingShell>
  );
}
