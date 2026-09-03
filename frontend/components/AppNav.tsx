'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const LINKS: [string, string][] = [
  ['/', 'Overview'],
  ['/releases', 'Releases'],
  ['/operations', 'Operations'],
  ['/settings/schedule', 'Schedule'],
  ['/settings/github', 'GitHub'],
];

export function AppNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary">
      {LINKS.map(([href, label]) => {
        const active = href === '/' ? pathname === '/' : pathname.startsWith(href);
        return (
          <Link key={href} href={href} aria-current={active ? 'page' : undefined}>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
