'use client';

import { motion } from 'motion/react';
import { ArrowLeft, Box } from 'lucide-react';
import Link from 'next/link';
import { useLanguage } from '@/lib/i18n';
import LanguageSelector from '@/components/LanguageSelector';

export default function FeaturesPage() {
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
            {t('features')}
          </h1>
          <p className="text-lg text-neutral-400 mb-12 leading-relaxed">
            {t('bentoDesc')}
          </p>

          <div className="space-y-12">
            {/* Feature 1 */}
            <div className="p-8 rounded-3xl bg-[#0A0A0A] border border-white/10">
              <h2 className="text-2xl font-medium mb-4">{t('card1Title')}</h2>
              <p className="text-neutral-400 leading-relaxed">{t('card1Desc')}</p>
            </div>
            
            {/* Feature 2 */}
            <div className="p-8 rounded-3xl bg-[#0A0A0A] border border-white/10">
              <h2 className="text-2xl font-medium mb-4">{t('card2Title')}</h2>
              <p className="text-neutral-400 leading-relaxed">{t('card2Desc')}</p>
            </div>

            {/* Feature 3 */}
            <div className="p-8 rounded-3xl bg-[#0A0A0A] border border-white/10">
              <h2 className="text-2xl font-medium mb-4">{t('card3Title')}</h2>
              <p className="text-neutral-400 leading-relaxed">{t('card3Desc')}</p>
            </div>

            {/* Feature 4 */}
            <div className="p-8 rounded-3xl bg-[#0A0A0A] border border-white/10">
              <h2 className="text-2xl font-medium mb-4">{t('card4Title')}</h2>
              <p className="text-neutral-400 leading-relaxed">{t('card4Desc')}</p>
            </div>

            {/* Feature 5 */}
            <div className="p-8 rounded-3xl bg-[#0A0A0A] border border-white/10">
              <h2 className="text-2xl font-medium mb-4">{t('card5Title')}</h2>
              <p className="text-neutral-400 leading-relaxed">{t('card5Desc')}</p>
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  );
}
