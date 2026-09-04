export type CronClause = {
  kind: 'wildcard' | 'value' | 'range';
  start?: number;
  end?: number;
  step: number;
};
export type CronField = CronClause[];
export type CronSchedule = {
  minute: CronField;
  hour: CronField;
  dayOfMonth: CronField;
  month: CronField;
  dayOfWeek: CronField;
};

export const CRON_FIELDS = [
  { key: 'minute', label: 'Minute', min: 0, max: 59 },
  { key: 'hour', label: 'Hour', min: 0, max: 23 },
  { key: 'dayOfMonth', label: 'Day of month', min: 1, max: 31 },
  { key: 'month', label: 'Month', min: 1, max: 12 },
  { key: 'dayOfWeek', label: 'Weekday', min: 0, max: 6 },
] as const;

function parseField(text: string, min: number, max: number): CronField {
  if (!text) throw new Error('A cron field cannot be empty.');
  return text.split(',').map((part) => {
    const pieces = part.split('/');
    if (pieces.length > 2 || !pieces[0]) throw new Error(`Invalid schedule field: ${text}`);
    const step = pieces.length === 2 ? Number(pieces[1]) : 1;
    if (!Number.isInteger(step) || step < 1) throw new Error('Steps must be positive whole numbers.');
    const base = pieces[0];
    if (base === '*') return { kind: 'wildcard', step };
    if (base.includes('-')) {
      const values = base.split('-').map(Number);
      if (values.length !== 2 || values.some((v) => !Number.isInteger(v))) throw new Error(`Invalid range: ${base}`);
      if (values[0] < min || values[1] > max || values[0] > values[1]) throw new Error(`Values must be between ${min} and ${max}.`);
      return { kind: 'range', start: values[0], end: values[1], step };
    }
    const value = Number(base);
    if (!Number.isInteger(value) || value < min || value > max) throw new Error(`Values must be between ${min} and ${max}.`);
    return { kind: 'value', start: value, step };
  });
}

export function parseCron(expression: string): CronSchedule {
  const parts = expression.trim().split(/\s+/);
  if (parts.length !== 5) throw new Error('A schedule must contain five fields.');
  const parsed = CRON_FIELDS.map((field, index) => parseField(parts[index], field.min, field.max));
  return Object.fromEntries(CRON_FIELDS.map((field, index) => [field.key, parsed[index]])) as CronSchedule;
}

function serializeField(clauses: CronField, min: number, max: number): string {
  if (!clauses.length) throw new Error('Each field needs at least one choice.');
  return clauses.map((clause) => {
    const step = Number(clause.step);
    if (!Number.isInteger(step) || step < 1) throw new Error('Steps must be positive whole numbers.');
    const start = Number(clause.start);
    const end = Number(clause.end);
    let base: string;
    if (clause.kind === 'wildcard') base = '*';
    else if (!Number.isInteger(start) || start < min || start > max) throw new Error(`Values must be between ${min} and ${max}.`);
    else if (clause.kind === 'value') base = String(start);
    else {
      if (!Number.isInteger(end) || end < start || end > max) throw new Error(`Ranges must be between ${min} and ${max}.`);
      base = `${start}-${end}`;
    }
    return `${base}${step === 1 ? '' : `/${step}`}`;
  }).join(',');
}

export function serializeCron(schedule: CronSchedule): string {
  return CRON_FIELDS.map((field) => serializeField(schedule[field.key], field.min, field.max)).join(' ');
}

function fieldDescription(field: CronField, label: string): string {
  return field.map((clause) => {
    const base = clause.kind === 'wildcard' ? `every ${label.toLowerCase()}` : clause.kind === 'value' ? `${label.toLowerCase()} ${clause.start}` : `${label.toLowerCase()}s ${clause.start} through ${clause.end}`;
    return clause.step > 1 ? `${base}, every ${clause.step}` : base;
  }).join(' or ');
}

export function describeCron(scheduleOrExpression: CronSchedule | string): string {
  const schedule = typeof scheduleOrExpression === 'string' ? parseCron(scheduleOrExpression) : scheduleOrExpression;
  return `UTC: ${CRON_FIELDS.map((field) => fieldDescription(schedule[field.key], field.label)).join('; ')}.`;
}
