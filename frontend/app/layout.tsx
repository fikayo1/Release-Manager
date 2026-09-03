import './globals.css';
import './marketing.css';

export const metadata = {
  title: 'Release Manager',
  description: 'Governed release operations',
};

// The root layout owns only <html>/<body>. Each surface renders its own
// landmark: the dashboard shell owns <main> + the sidebar <nav>, while the
// marketing and login pages own a single <main>.
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
