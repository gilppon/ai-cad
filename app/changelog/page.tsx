'use client';

import { motion } from 'motion/react';
import { ArrowLeft, Box } from 'lucide-react';
import Link from 'next/link';
import { useLanguage } from '@/lib/i18n';
import LanguageSelector from '@/components/LanguageSelector';

export default function ChangelogPage() {
  const { t } = useLanguage();

  return (
    <div className="min-h-screen bg-black text-white font-sans selection:bg-white/30">
      {/* Navbar */}
      <nav className="fixed top-0 inset-x-0 z-50 border-b border-white/5 bg-black/50 backdrop-blur-xl">
        <div className="flex items-center justify-between px-6 h-16 max-w-7xl mx-auto">
          <Link href="/" className="flex items-center gap-3">
            <div className="w-7 h-7 bg-white rounded flex items-center justify-center">
              <Box className="w-4 h-4 text-black" />
            </div>
            <span className="font-semibold text-lg tracking-tight">
              GlowPoint
            </span>
          </Link>
          <div className="flex items-center gap-4">
            <LanguageSelector />
            <Link href="/" className="p-2 hover:bg-white/5 rounded-md transition-colors text-slate-400 hover:text-white">
              <ArrowLeft className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto px-6 pt-40 pb-24">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
        >
          <h1 className="text-4xl md:text-6xl font-medium tracking-tighter mb-6 text-transparent bg-clip-text bg-gradient-to-b from-white to-white/60">
            {t('changelog')}
          </h1>
          
          <div className="prose prose-invert max-w-none prose-lg">
            <div className="p-8 rounded-3xl bg-[#0A0A0A] border border-white/10 mb-8">
              <h2 className="text-2xl font-medium mb-4 text-white">Latest Updates</h2>
              
              <div className="space-y-12">
                {/* Version 2.0 */}
                <div className="relative pl-8 border-l border-white/10">
                  <div className="absolute w-3 h-3 bg-indigo-500 rounded-full -left-[6.5px] top-2"></div>
                  <h3 className="text-xl font-medium text-white mb-1">v2.0.0 - The AI Revolution</h3>
                  <p className="text-sm text-neutral-500 mb-4">March 15, 2026</p>
                  <ul className="list-disc list-inside text-neutral-400 space-y-2">
                    <li>Introduced our next-generation AI vision models for 5x faster sketch recognition.</li>
                    <li>Added support for real-time parametric constraint inference.</li>
                    <li>Completely redesigned the 3D workspace with a new dark theme and improved performance.</li>
                    <li>New ISO tolerance suggestion engine based on context.</li>
                    <li>Added multi-language support (English, Korean, Japanese, Chinese, French, German, Spanish).</li>
                  </ul>
                </div>

                {/* Version 1.5 */}
                <div className="relative pl-8 border-l border-white/10">
                  <div className="absolute w-3 h-3 bg-neutral-600 rounded-full -left-[6.5px] top-2"></div>
                  <h3 className="text-xl font-medium text-white mb-1">v1.5.2 - Export Enhancements</h3>
                  <p className="text-sm text-neutral-500 mb-4">January 28, 2026</p>
                  <ul className="list-disc list-inside text-neutral-400 space-y-2">
                    <li>Improved STEP file export compatibility with major CAD software (SolidWorks, AutoCAD).</li>
                    <li>Added IGES export format.</li>
                    <li>Fixed a bug where complex splines were sometimes misinterpreted during conversion.</li>
                    <li>Performance improvements for rendering large assemblies in the browser.</li>
                  </ul>
                </div>

                {/* Version 1.4 */}
                <div className="relative pl-8 border-l border-white/10">
                  <div className="absolute w-3 h-3 bg-neutral-600 rounded-full -left-[6.5px] top-2"></div>
                  <h3 className="text-xl font-medium text-white mb-1">v1.4.0 - Collaboration Tools</h3>
                  <p className="text-sm text-neutral-500 mb-4">November 10, 2025</p>
                  <ul className="list-disc list-inside text-neutral-400 space-y-2">
                    <li>Introduced shared workspaces for team collaboration.</li>
                    <li>Added real-time cursor tracking for multiple users in the same project.</li>
                    <li>Version history and rollback capabilities added to all projects.</li>
                    <li>New commenting system directly on 3D models.</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  );
}
