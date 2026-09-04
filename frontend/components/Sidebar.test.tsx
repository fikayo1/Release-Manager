import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';

let mockPath = '/dashboard';
vi.mock('next/navigation', () => ({ usePathname: () => mockPath }));
vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: any) => (
    <a href={typeof href === 'string' ? href : String(href)} {...rest}>
      {children}
    </a>
  ),
}));

import { Sidebar } from './Sidebar';

afterEach(() => {
  cleanup();
  mockPath = '/dashboard';
});

describe('Sidebar', () => {
  it('renders the five section links, a sign-out control, and the logo link to /', () => {
    render(<Sidebar />);
    const nav = screen.getByRole('navigation', { name: 'Dashboard sections' });
    for (const label of ['Home', 'Releases', 'Operations', 'Repos', 'Schedule']) {
      expect(within(nav).getByRole('link', { name: label })).toBeTruthy();
    }
    expect(within(nav).getByRole('link', { name: 'Home' }).getAttribute('href')).toBe('/dashboard');
    expect(within(nav).getByRole('link', { name: 'Releases' }).getAttribute('href')).toBe(
      '/dashboard/releases',
    );
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeTruthy();
    expect(screen.getByRole('link', { name: /Release Manager/ }).getAttribute('href')).toBe('/');
  });

  it('marks only the active route with aria-current="page"', () => {
    mockPath = '/dashboard/releases';
    render(<Sidebar />);
    expect(screen.getByRole('link', { name: 'Releases' }).getAttribute('aria-current')).toBe('page');
    expect(screen.getByRole('link', { name: 'Home' }).getAttribute('aria-current')).toBeNull();
  });

  it('keeps Home inactive on nested dashboard routes (exact match only)', () => {
    mockPath = '/dashboard/operations';
    render(<Sidebar />);
    expect(screen.getByRole('link', { name: 'Home' }).getAttribute('aria-current')).toBeNull();
    expect(screen.getByRole('link', { name: 'Operations' }).getAttribute('aria-current')).toBe('page');
  });

  it('exposes an aria-expanded toggle that controls the sidebar region', () => {
    render(<Sidebar />);
    const toggle = screen.getByRole('button', { name: 'Menu' });
    expect(toggle.getAttribute('aria-controls')).toBe('dashboard-sidebar');
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(toggle);
    expect(screen.getByRole('button', { name: 'Close menu' }).getAttribute('aria-expanded')).toBe('true');
    expect(document.getElementById('dashboard-sidebar')?.getAttribute('data-open')).toBe('true');
  });

  it('has no navigation landmark labelled as top/primary navigation', () => {
    render(<Sidebar />);
    expect(screen.queryByRole('navigation', { name: /primary/i })).toBeNull();
  });
});
