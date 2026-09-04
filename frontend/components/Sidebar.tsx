'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

const LINKS: [string, string][] = [
  ['/dashboard', 'Home'],
  ['/dashboard/releases', 'Releases'],
  ['/dashboard/operations', 'Operations'],
  ['/dashboard/settings/github', 'Repos'],
  ['/dashboard/settings/schedule', 'Schedule'],
];

function isActive(href: string, pathname: string): boolean {
  return href === '/dashboard' ? pathname === '/dashboard' : pathname.startsWith(href);
}

export function Sidebar() {
  const pathname = usePathname() ?? '/dashboard';
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => {
    setOpen(false);
    toggleRef.current?.focus();
  }, []);

  // Close on route change so a tap-through on mobile does not leave the rail up.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, close]);

  return (
    <>
      <button
        ref={toggleRef}
        type="button"
        className="sidebar-toggle button"
        data-open={open ? 'true' : 'false'}
        aria-expanded={open}
        aria-controls="dashboard-sidebar"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? 'Close menu' : 'Menu'}
      </button>
      <div
        className="sidebar-backdrop"
        data-open={open ? 'true' : 'false'}
        onClick={close}
        aria-hidden="true"
      />
      <aside id="dashboard-sidebar" className="sidebar" data-open={open ? 'true' : 'false'}>
        <Link className="sidebar-brand" href="/">
          Release Manager
          <span>Console</span>
        </Link>
        <nav aria-label="Dashboard sections">
          {LINKS.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              aria-current={isActive(href, pathname) ? 'page' : undefined}
            >
              {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot">
          <form action="/auth/logout" method="post">
            <button type="submit">Sign out</button>
          </form>
        </div>
      </aside>
    </>
  );
}
