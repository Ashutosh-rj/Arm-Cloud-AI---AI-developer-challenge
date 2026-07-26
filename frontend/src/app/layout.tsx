import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'InferaV22 — Every Version. Faster. Smarter. Optimized.',
  description: 'Autonomous AI Inference Optimization Platform for Arm Cloud (Arm AI Challenge 2026)',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-[#0A0A0F] text-white min-h-screen">
        {children}
      </body>
    </html>
  );
}
