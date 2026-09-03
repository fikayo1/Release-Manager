import type {ReactNode} from 'react';
import {MarketingFooter} from './MarketingFooter';
import {MarketingHeader} from './MarketingHeader';

export function MarketingShell({children, pageClass = ''}: {children: ReactNode; pageClass?: string}) {
  return (
    <div className="marketing-shell">
      <MarketingHeader />
      <main className={`marketing-main ${pageClass}`.trim()}>{children}</main>
      <MarketingFooter />
    </div>
  );
}
