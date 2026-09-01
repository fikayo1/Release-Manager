"""Strict five-field cron parsing and UTC occurrence calculation."""
from datetime import datetime, timedelta, timezone

RANGES = ((0,59),(0,23),(1,31),(1,12),(0,6))

class CronError(ValueError): pass

def _field(text, low, high):
    values=set()
    for part in text.split(','):
        base, sep, step_text=part.partition('/')
        try: step=int(step_text) if sep else 1
        except ValueError: raise CronError("cron step must be an integer")
        if step < 1: raise CronError("cron step must be positive")
        if base=='*': start,end=low,high
        elif '-' in base:
            try: start,end=map(int,base.split('-',1))
            except ValueError: raise CronError("invalid cron range")
        else:
            try: start=end=int(base)
            except ValueError: raise CronError("invalid cron value")
        if start<low or end>high or start>end: raise CronError(f"cron value must be between {low} and {high}")
        values.update(range(start,end+1,step))
    return values

def parse(expression):
    parts=expression.strip().split()
    if len(parts)!=5: raise CronError("cron expression must contain exactly five fields")
    return tuple(_field(part,*bounds) for part,bounds in zip(parts,RANGES))

def matches(expression, moment):
    fields=parse(expression); moment=moment.astimezone(timezone.utc)
    return all(value in values for value,values in zip((moment.minute,moment.hour,moment.day,moment.month,(moment.weekday()+1)%7),fields))

def next_run(expression, after):
    candidate=after.astimezone(timezone.utc).replace(second=0,microsecond=0)+timedelta(minutes=1)
    for _ in range(366*24*60*5):
        if matches(expression,candidate): return candidate
        candidate += timedelta(minutes=1)
    raise CronError("no occurrence found within five years")
