'use client';

import { motion } from 'motion/react';
import { ArrowLeft, Box } from 'lucide-react';
import Link from 'next/link';
import { useLanguage } from '@/lib/i18n';
import LanguageSelector from '@/components/LanguageSelector';

export default function MethodologyPage() {
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
            {t('methodology')}
          </h1>
          
          <div className="prose prose-invert max-w-none prose-lg">
            <div className="p-8 rounded-3xl bg-[#0A0A0A] border border-white/10 mb-8">
              <h2 className="text-2xl font-medium mb-4 text-white">Our Approach to AI CAD</h2>
              <p className="text-neutral-400 leading-relaxed mb-6">
                At GlowPoint, we believe that the transition from 2D sketches to 3D models should be seamless, intuitive, and highly accurate. Our methodology is built upon three core pillars: Vision Recognition, Parametric Inference, and Real-time Validation.
              </p>
              
              <h3 className="text-xl font-medium mb-3 text-white mt-8">1. Vision Recognition</h3>
              <p className="text-neutral-400 leading-relaxed mb-6">
                We utilize state-of-the-art computer vision models trained on millions of technical drawings and hand-drawn sketches. This allows our system to accurately identify lines, arcs, dimensions, and annotations, even when the input is imperfect or noisy.
              </p>

              <h3 className="text-xl font-medium mb-3 text-white mt-8">2. Parametric Inference</h3>
              <p className="text-neutral-400 leading-relaxed mb-6">
                Once the geometry is recognized, our proprietary inference engine deduces the underlying parametric relationships. It automatically identifies parallel lines, perpendicular intersections, tangencies, and concentric circles, applying these as constraints to build a robust 3D model.
              </p>

              <h3 className="text-xl font-medium mb-3 text-white mt-8">3. Real-time Validation</h3>
              <p className="text-neutral-400 leading-relaxed">
                As the 3D model is generated, it undergoes continuous validation against industry standards (such as ISO tolerances). Our system highlights potential errors or inconsistencies in real-time, allowing engineers to correct them before exporting to their manufacturing pipelines.
              </p>
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  );
}
