import type { Metadata } from 'next';
import './globals.css';
import './polish.css';
import './cib-light.css';
export const metadata: Metadata = {
  title: 'ChangeImpactBench',
  description: 'Reproducible model evaluations for production incident reasoning',
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
