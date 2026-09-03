'use client';
import { RetryableError } from '@/components/RetryableError';
export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return <RetryableError reset={reset} title="Dashboard unavailable" />;
}
