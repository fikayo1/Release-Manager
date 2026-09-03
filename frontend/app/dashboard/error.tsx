'use client';
import { RetryableError } from '@/components/RetryableError';
export default function DashboardError({ reset }: { error: Error; reset: () => void }) {
  return <RetryableError reset={reset} title="Dashboard unavailable" />;
}
