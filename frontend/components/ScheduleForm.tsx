'use client';
import { useMemo, useState } from 'react';
import { CRON_FIELDS, CronClause, CronSchedule, describeCron, parseCron, serializeCron } from '@/lib/cron';

function ClauseEditor({ clause, min, max, onChange, onRemove, removable }: { clause: CronClause; min: number; max: number; onChange: (clause: CronClause) => void; onRemove: () => void; removable: boolean }) {
  return <div className="cron-clause">
    <label>Selection
      <select value={clause.kind} onChange={(event) => onChange({ ...clause, kind: event.target.value as CronClause['kind'] })}>
        <option value="wildcard">Every value</option><option value="value">One value</option><option value="range">Range</option>
      </select>
    </label>
    {clause.kind !== 'wildcard' && <label>{clause.kind === 'range' ? 'From' : 'Value'}
      <input type="number" min={min} max={max} value={clause.start ?? min} onChange={(event) => onChange({ ...clause, start: Number(event.target.value) })} />
    </label>}
    {clause.kind === 'range' && <label>Through
      <input type="number" min={min} max={max} value={clause.end ?? max} onChange={(event) => onChange({ ...clause, end: Number(event.target.value) })} />
    </label>}
    <label>Step
      <input type="number" min="1" value={clause.step} onChange={(event) => onChange({ ...clause, step: Number(event.target.value) })} />
    </label>
    {removable && <button type="button" className="button-secondary" onClick={onRemove}>Remove</button>}
  </div>;
}

export function ScheduleForm({ schedule }: { schedule: { expression: string; enabled: boolean } }) {
  const initial = useMemo(() => { try { return { value: parseCron(schedule.expression), error: '' }; } catch (error) { return { value: null, error: error instanceof Error ? error.message : 'Invalid saved schedule.' }; } }, [schedule.expression]);
  const [model, setModel] = useState<CronSchedule | null>(initial.value);
  const [expression, setExpression] = useState(schedule.expression);
  const [expressionError, setExpressionError] = useState('');
  const [enabled, setEnabled] = useState(schedule.enabled);
  const [message, setMessage] = useState('');
  const validation = useMemo(() => { if (expressionError) return expressionError; if (!model) return initial.error; try { serializeCron(model); return ''; } catch (error) { return error instanceof Error ? error.message : 'Invalid schedule.'; } }, [model, initial.error, expressionError]);
  const update = (key: keyof CronSchedule, value: CronClause[]) => setModel((current) => {
    if (!current) return current;
    const next = { ...current, [key]: value };
    try { setExpression(serializeCron(next)); setExpressionError(''); } catch { /* Keep the editor available while a numeric field is incomplete. */ }
    return next;
  });
  const updateExpression = (value: string) => {
    setExpression(value);
    try { setModel(parseCron(value)); setExpressionError(''); }
    catch { setExpressionError('Enter a valid five-field cron expression.'); }
  };
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!model || validation) { setMessage(validation || 'Enter a valid five-field cron expression.'); return; }
    setMessage('Saving…');
    const response = await fetch('/api/schedule', { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ expression: serializeCron(model), enabled }) });
    const data = await response.json(); setMessage(response.ok ? 'Schedule saved' : data.detail || 'Could not save');
  }
  if (!model) return <p className="alert" role="alert">The saved schedule cannot be edited: {initial.error}</p>;
  return <form onSubmit={submit} className="schedule-form">
    <div className="schedule-heading"><div><h2>Scan timing</h2><p>Choose when automated repository scans run.</p></div><label className="switch"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> Enabled</label></div>
    <label>Cron expression (UTC)
      <input value={expression} onChange={(event) => updateExpression(event.target.value)} aria-invalid={Boolean(expressionError)} />
    </label>
    <details className="schedule-guide"><summary>How scheduling works</summary><p>All times use UTC. A run occurs only when minute, hour, day of month, month, and weekday all match. Use Step to select every nth value within every value or a range. Add choices creates a comma-separated list.</p></details>
    {CRON_FIELDS.map((field) => <fieldset key={field.key}>
      <legend>{field.label} <small>{field.min}–{field.max}</small></legend>
      {model[field.key].map((clause, index) => <ClauseEditor key={index} clause={clause} min={field.min} max={field.max} removable={model[field.key].length > 1} onChange={(next) => update(field.key, model[field.key].map((item, i) => i === index ? next : item))} onRemove={() => update(field.key, model[field.key].filter((_, i) => i !== index))} />)}
      <button type="button" className="button-secondary" onClick={() => update(field.key, [...model[field.key], { kind: 'value', start: field.min, step: 1 }])}>Add choice</button>
    </fieldset>)}
    <div className="schedule-summary"><strong>Schedule summary</strong><p>{validation || describeCron(model)}</p></div>
    <button>Save schedule</button><p role="status">{message}</p>
  </form>;
}
