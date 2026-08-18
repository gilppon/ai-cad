'use client';

import { motion } from 'motion/react';
import { ArrowLeft, Box } from 'lucide-react';
import Link from 'next/link';
import { useLanguage } from '@/lib/i18n';
import LanguageSelector from '@/components/LanguageSelector';

export default function CustomersPage() {
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
            {t('customers')}
          </h1>
          
          <div className="prose prose-invert max-w-none prose-lg">
            <div className="p-8 rounded-3xl bg-[#0A0A0A] border border-white/10 mb-8">
              <h2 className="text-2xl font-medium mb-4 text-white">Trusted by Industry Leaders</h2>
              <p className="text-neutral-400 leading-relaxed mb-12">
                GlowPoint is used by thousands of engineering teams worldwide to accelerate their product development cycles and bring innovative designs to life faster than ever before.
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Customer 1 */}
                <div className="p-6 rounded-2xl bg-[#111] border border-white/5">
                  <div className="w-12 h-12 bg-indigo-500/20 rounded-full flex items-center justify-center mb-4">
                    <span className="text-indigo-400 font-bold text-xl">A</span>
                  </div>
                  <h3 className="text-xl font-medium mb-2 text-white">Aerospace Dynamics</h3>
                  <p className="text-neutral-400 text-sm leading-relaxed">
                    "GlowPoint has revolutionized our rapid prototyping phase. We can now move from conceptual sketches to 3D models in minutes instead of days."
                  </p>
                </div>

                {/* Customer 2 */}
                <div className="p-6 rounded-2xl bg-[#111] border border-white/5">
                  <div className="w-12 h-12 bg-emerald-500/20 rounded-full flex items-center justify-center mb-4">
                    <span className="text-emerald-400 font-bold text-xl">M</span>
                  </div>
                  <h3 className="text-xl font-medium mb-2 text-white">MechWorks Global</h3>
                  <p className="text-neutral-400 text-sm leading-relaxed">
                    "The AI-powered constraint detection is incredibly accurate. It saves our drafting team countless hours of manual dimensioning."
                  </p>
                </div>

                {/* Customer 3 */}
                <div className="p-6 rounded-2xl bg-[#111] border border-white/5">
                  <div className="w-12 h-12 bg-rose-500/20 rounded-full flex items-center justify-center mb-4">
                    <span className="text-rose-400 font-bold text-xl">N</span>
                  </div>
                  <h3 className="text-xl font-medium mb-2 text-white">Nova Robotics</h3>
                  <p className="text-neutral-400 text-sm leading-relaxed">
                    "Being able to instantly export to STEP files and integrate with our existing CNC pipelines has been a game-changer for our manufacturing speed."
                  </p>
                </div>

                {/* Customer 4 */}
                <div className="p-6 rounded-2xl bg-[#111] border border-white/5">
                  <div className="w-12 h-12 bg-amber-500/20 rounded-full flex items-center justify-center mb-4">
                    <span className="text-amber-400 font-bold text-xl">S</span>
                  </div>
                  <h3 className="text-xl font-medium mb-2 text-white">Stellar Automotive</h3>
                  <p className="text-neutral-400 text-sm leading-relaxed">
                    "The real-time simulation and error detection features ensure that our models are production-ready before they ever leave the design phase."
                  </p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  );
}
