'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import LandingPage from '@/components/LandingPage';

const Workspace = dynamic(() => import('@/components/Workspace'), { ssr: false });

export default function App() {
  const [view, setView] = useState<'landing' | 'workspace'>('landing');

  return (
    <main className={`w-full bg-black text-white font-sans ${view === 'workspace' ? 'h-screen overflow-hidden' : 'min-h-screen'}`}>
      {view === 'landing' ? (
        <LandingPage onNavigate={() => setView('workspace')} />
      ) : (
        <Workspace onBack={() => setView('landing')} />
      )}
    </main>
  );
}

