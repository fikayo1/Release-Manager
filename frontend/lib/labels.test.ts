import { describe, expect, it } from 'vitest';
import { operationTitle, sourceLabel, statusLabel } from './labels';

describe('operation labels', () => {
  it('maps every known raw token to human wording', () => {
    for (const token of [
      'non_release',
      'draft_created',
      'reconnect_required',
      'suppressed',
      'failed',
      'legacy',
      'manual',
      'scheduled',
    ]) {
      const rendered = `${statusLabel(token)} ${sourceLabel(token)}`;
      expect(rendered).not.toMatch(/_/);
      expect(rendered.toLowerCase()).not.toContain('non release manual');
    }
  });

  it('never produces the raw "Non Release manual" string', () => {
    const title = operationTitle({ source: 'manual', result: 'non_release' });
    expect(title).toBe('Manual scan — No release needed');
    expect(title).not.toContain('Non Release');
  });

  it('falls back to a humanized label for unknown tokens', () => {
    expect(statusLabel('brand_new_state')).toBe('Brand New State');
    expect(sourceLabel('webhook')).toBe('Webhook scan');
  });
});
