'use client';
import { RetryableError } from '@/components/RetryableError';
export default function ReleasesError({ reset }: { error: Error; reset: () => void }) {
  return <RetryableError reset={reset} title="Releases unavailable" />;
}
