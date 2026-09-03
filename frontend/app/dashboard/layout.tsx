import { Sidebar } from '@/components/Sidebar';

// Authenticated shell: a responsive left sidebar (no top <header> nav) plus the
// page <main>. `middleware.ts` guarantees a session cookie is present before
// anything here renders.
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="dashboard-shell">
      <Sidebar />
      <main>{children}</main>
    </div>
  );
}
