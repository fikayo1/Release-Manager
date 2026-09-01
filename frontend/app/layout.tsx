import './globals.css';import {AppNav} from '@/components/AppNav';
export const metadata={title:'Release Manager',description:'Governed release operations'};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body><header><div><strong>Release Manager</strong><span>Operator dashboard</span></div><AppNav/></header><main>{children}</main></body></html>}
