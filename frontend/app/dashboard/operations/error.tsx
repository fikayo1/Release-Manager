'use client';
import { RetryableError } from '@/components/RetryableError';
export default function OperationsError({ reset }: { error: Error; reset: () => void }) {
  return <RetryableError reset={reset} title="Operations unavailable" />;
}
