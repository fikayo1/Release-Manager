import Link from 'next/link';
import {MarketingShell} from '@/components/MarketingShell';

const stages = [
  {name: 'Scan', detail: 'Read repository changes and collect the source evidence for a release.'},
  {name: 'Draft', detail: 'Turn that evidence into a release pack with rationale, notes, and history.'},
  {name: 'Review', detail: 'Hold the draft for a named human to inspect, approve, or reject with a reason.'},
  {name: 'Publish', detail: 'Publish to GitHub only after the governance decision is recorded.'},
  {name: 'Rollback', detail: 'Keep a governed path back when a published change must be reversed.'},
];

export default function Home() {
  return (
    <MarketingShell>
      <section className="marketing-hero" aria-labelledby="hero-title">
        <div className="marketing-hero-copy">
          <p className="marketing-kicker">GitHub release governance</p>
          <h1 id="hero-title">Release with proof,<br /><em>not crossed fingers.</em></h1>
          <p className="marketing-lede">
            Release Manager turns repository change into an evidence-backed release
            pack, then keeps a named human in control of what ships.
          </p>
          <div className="marketing-actions">
            <Link className="button" href="/login">Open the console</Link>
            <Link className="marketing-text-link" href="/about">Why we built it <span aria-hidden="true">→</span></Link>
          </div>
        </div>
        <aside className="marketing-proof" aria-label="Release governance summary">
          <p className="marketing-proof-label">Release posture</p>
          <strong>Evidence assembled</strong>
          <div className="marketing-proof-rule" />
          <dl>
            <div><dt>Source</dt><dd>Repository history</dd></div>
            <div><dt>Gate</dt><dd>Named human review</dd></div>
            <div><dt>Record</dt><dd>Decision + rationale</dd></div>
          </dl>
          <p className="marketing-proof-stamp">Ready for review</p>
        </aside>
      </section>

      <section className="marketing-explanation" aria-labelledby="explanation-title">
        <p className="marketing-index">01 / The proposition</p>
        <div>
          <h2 id="explanation-title">Automation prepares.<br />People decide.</h2>
          <p>
            Release Manager scans a GitHub repository and drafts a release pack from
            the evidence it finds. Publication waits until a named reviewer has made
            and explained the decision. Every scan, decision, and publication attempt
            is recorded for audit—so speed never erases accountability.
          </p>
        </div>
      </section>

      <section className="marketing-workflow" aria-labelledby="workflow-title">
        <div className="marketing-section-head">
          <div><p className="marketing-index">02 / The workflow</p><h2 id="workflow-title">A clear route to release.</h2></div>
          <p>Five deliberate stages. No invisible handoffs.</p>
        </div>
        <ol className="marketing-stages">
          {stages.map((stage, index) => (
            <li key={stage.name}>
              <span className="marketing-stage-number">{String(index + 1).padStart(2, '0')}</span>
              <h3>{stage.name}</h3>
              <p>{stage.detail}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="marketing-benefits" aria-labelledby="benefits-title">
        <div className="marketing-section-head">
          <div><p className="marketing-index">03 / What changes</p><h2 id="benefits-title">Confidence you can inspect.</h2></div>
        </div>
        <div className="marketing-benefit-grid">
          <article><span aria-hidden="true">↳</span><h3>Evidence before opinion</h3><p>Release notes and rationale begin with the repository record, not a blank page or fading memory.</p></article>
          <article><span aria-hidden="true">↳</span><h3>Governance without fog</h3><p>Named reviewers and recorded reasons make the authority behind publication explicit.</p></article>
          <article><span aria-hidden="true">↳</span><h3>An accountable history</h3><p>Scans, decisions, publication attempts, and rollback activity remain available for audit.</p></article>
        </div>
      </section>

      <section className="marketing-shipyard" aria-labelledby="shipyard-title">
        <p className="marketing-index">04 / Built by Shipyard</p>
        <div>
          <h2 id="shipyard-title">Product-building discipline,<br />carried into release day.</h2>
          <p>Release Manager is built by Shipyard, Herald&apos;s product-building platform, with the same emphasis on governed, reviewable delivery.</p>
          <Link className="marketing-text-link" href="/about">About Release Manager <span aria-hidden="true">→</span></Link>
        </div>
      </section>

      <section className="marketing-final" aria-labelledby="final-title">
        <p className="marketing-kicker">Make the next release legible</p>
        <h2 id="final-title">Move quickly.<br /><em>Leave a trail.</em></h2>
        <p>Bring repository evidence, human judgment, and release history into one governed flow.</p>
        <div className="marketing-actions">
          <Link className="button" href="/login">Open the console</Link>
          <Link className="marketing-text-link" href="/about">Learn more <span aria-hidden="true">→</span></Link>
        </div>
      </section>
    </MarketingShell>
  );
}
