import { motion } from "motion/react";
import { Box, Sparkles, Globe, ChevronRight } from "lucide-react";
import Link from "next/link";
import LanguageSelector from "./LanguageSelector";
import { useLanguage } from "@/lib/i18n";

export default function LandingPage({
  onNavigate,
}: {
  onNavigate: () => void;
}) {
  const { t } = useLanguage();

  return (
    <div className="min-h-screen bg-black text-white font-sans selection:bg-white/30 overflow-y-auto overflow-x-hidden">
      {/* Navbar */}
      <nav className="fixed top-0 inset-x-0 z-50 border-b border-white/5 bg-black/50 backdrop-blur-xl">
        <div className="flex items-center justify-between px-6 h-16 max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 bg-white rounded flex items-center justify-center">
              <Box className="w-4 h-4 text-black" />
            </div>
            <span className="font-semibold text-lg tracking-tight">
              GlowPoint
            </span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-neutral-400">
            <Link href="/features" className="hover:text-white transition-colors">
              {t('features')}
            </Link>
            <Link href="/methodology" className="hover:text-white transition-colors">
              {t('methodology')}
            </Link>
            <Link href="/customers" className="hover:text-white transition-colors">
              {t('customers')}
            </Link>
            <Link href="/changelog" className="hover:text-white transition-colors">
              {t('changelog')}
            </Link>
          </div>
          <div className="flex items-center gap-4">
            <LanguageSelector />
            <button className="hidden md:block text-sm font-medium text-neutral-400 hover:text-white transition-colors">
              {t('login')}
            </button>
            <button
              onClick={onNavigate}
              className="px-4 py-2 bg-white text-black text-sm font-medium rounded-full hover:bg-neutral-200 transition-colors flex items-center gap-2"
            >
              {t('getStarted')} <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-6 pt-40 pb-24 flex flex-col items-center text-center relative">
        {/* Subtle Background Glow */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-indigo-500/10 blur-[120px] rounded-full pointer-events-none" />

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 flex flex-col items-center w-full"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-neutral-300 mb-8">
            <Sparkles className="w-3 h-3 text-indigo-400" />
            <span>{t('intro')}</span>
          </div>
          <h1 className="text-5xl md:text-7xl font-medium tracking-tighter mb-6 leading-[1.1] max-w-4xl text-transparent bg-clip-text bg-gradient-to-b from-white to-white/60">
            {t('heroTitle1')} <br className="hidden md:block" />
            {t('heroTitle2')}
          </h1>
          <p className="text-lg md:text-xl text-neutral-400 max-w-2xl mx-auto mb-10 font-normal leading-relaxed">
            {t('heroDesc')}
          </p>
          <div className="flex items-center gap-4">
            <button
              onClick={onNavigate}
              className="px-6 py-3 bg-white text-black text-sm font-medium rounded-full hover:scale-105 transition-transform flex items-center gap-2"
            >
              {t('startFree')}
            </button>
            <button className="px-6 py-3 bg-white/5 border border-white/10 text-white text-sm font-medium rounded-full hover:bg-white/10 transition-colors flex items-center gap-2">
              {t('bookDemo')}
            </button>
          </div>
        </motion.div>

        {/* Hero Image/Graphic */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-5xl mt-24 relative rounded-2xl border border-white/10 bg-[#0A0A0A] overflow-hidden shadow-2xl"
        >
          <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-transparent z-10" />
          <div className="aspect-[16/9] relative flex items-center justify-center bg-[url('/assets/cad_hero.png')] bg-cover bg-center opacity-40 mix-blend-luminosity">
            {/* Overlay UI elements to simulate the app */}
            <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" />
            <div className="relative z-20 w-3/4 h-3/4 border border-white/10 rounded-xl bg-black/50 backdrop-blur-md shadow-2xl flex flex-col overflow-hidden">
              <div className="h-10 border-b border-white/10 flex items-center px-4 gap-2 bg-white/5">
                <div className="w-3 h-3 rounded-full bg-red-500/80" />
                <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                <div className="w-3 h-3 rounded-full bg-green-500/80" />
              </div>
              <div className="flex-1 flex">
                <div className="w-64 border-r border-white/10 p-4 flex flex-col gap-3 bg-white/[0.02]">
                  <div className="h-4 w-24 bg-white/10 rounded" />
                  <div className="h-4 w-full bg-white/5 rounded" />
                  <div className="h-4 w-3/4 bg-white/5 rounded" />
                  <div className="h-4 w-5/6 bg-white/5 rounded" />
                </div>
                <div className="flex-1 relative flex items-center justify-center">
                  <div className="w-48 h-48 border border-indigo-500/30 rounded-full flex items-center justify-center">
                    <div className="w-32 h-32 border border-cyan-500/30 rounded-full flex items-center justify-center">
                      <Box className="w-12 h-12 text-white/50" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </main>

      {/* Bento Grid Section */}
      <section className="max-w-7xl mx-auto px-6 pb-32">
        <div className="mb-16">
          <h2 className="text-3xl md:text-4xl font-medium tracking-tight mb-4 text-white">
            {t('bentoTitle')}
          </h2>
          <p className="text-neutral-400 text-lg max-w-2xl">
            {t('bentoDesc')}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 auto-rows-[320px]">
          {/* Card 1: Large Left (Spans 2 rows) */}
          <motion.div
            whileHover={{ scale: 0.99 }}
            className="md:col-span-2 md:row-span-2 rounded-3xl p-8 flex flex-col relative overflow-hidden bg-[#0A0A0A] border border-white/10 group"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

            <div className="relative z-10 max-w-md">
              <h3 className="text-2xl font-medium tracking-tight mb-3">
                {t('card1Title')}
              </h3>
              <p className="text-neutral-400 leading-relaxed">
                {t('card1Desc')}
              </p>
            </div>

            <div className="mt-auto relative flex-1 w-full rounded-xl overflow-hidden border border-white/10 bg-[#111] mt-8">
              <div className="absolute inset-0 bg-[url('/assets/blueprint_card.png')] bg-cover opacity-30 mix-blend-luminosity" />
              <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0A] to-transparent" />

              {/* Scanning effect */}
              <div className="absolute top-0 left-0 right-0 h-1 bg-indigo-500 shadow-[0_0_20px_rgba(99,102,241,1)] animate-scan" />
            </div>
          </motion.div>

          {/* Card 2: Top Right */}
          <motion.div
            whileHover={{ scale: 0.99 }}
            className="md:col-span-1 rounded-3xl p-8 flex flex-col relative overflow-hidden bg-[#0A0A0A] border border-white/10 group"
          >
            <div className="relative z-10">
              <h3 className="text-xl font-medium tracking-tight mb-2">
                {t('card2Title')}
              </h3>
              <p className="text-sm text-neutral-400">
                {t('card2Desc')}
              </p>
            </div>

            <div className="mt-auto relative h-32 w-full flex items-center justify-center">
              <div className="w-24 h-24 rounded-full bg-gradient-to-tr from-cyan-400 to-indigo-500 blur-xl opacity-40 group-hover:opacity-60 transition-opacity" />
              <div className="absolute w-16 h-16 rounded-xl bg-white/10 backdrop-blur-xl border border-white/20 flex items-center justify-center transform group-hover:rotate-12 transition-transform duration-500">
                <Box className="w-8 h-8 text-white" />
              </div>
            </div>
          </motion.div>

          {/* Card 3: Middle Right */}
          <motion.div
            whileHover={{ scale: 0.99 }}
            className="md:col-span-1 rounded-3xl p-8 flex flex-col relative overflow-hidden bg-[#0A0A0A] border border-white/10 group"
          >
            <div className="relative z-10">
              <h3 className="text-xl font-medium tracking-tight mb-2">
                {t('card3Title')}
              </h3>
              <p className="text-sm text-neutral-400">
                {t('card3Desc')}
              </p>
            </div>

            <div className="mt-auto flex flex-col gap-2">
              <div className="w-full h-8 bg-white/5 rounded border border-white/5 flex items-center px-3 gap-2">
                <div className="w-2 h-2 rounded-full bg-indigo-400" />
                <div className="h-1.5 w-16 bg-white/20 rounded-full" />
              </div>
              <div className="w-full h-8 bg-white/5 rounded border border-white/5 flex items-center px-3 gap-2">
                <div className="w-2 h-2 rounded-full bg-cyan-400" />
                <div className="h-1.5 w-24 bg-white/20 rounded-full" />
              </div>
            </div>
          </motion.div>

          {/* Card 4: Bottom Left */}
          <motion.div
            whileHover={{ scale: 0.99 }}
            className="md:col-span-1 rounded-3xl p-8 flex flex-col relative overflow-hidden bg-[#0A0A0A] border border-white/10 group"
          >
            <div className="relative z-10">
              <h3 className="text-xl font-medium tracking-tight mb-2">
                {t('card4Title')}
              </h3>
              <p className="text-sm text-neutral-400">
                {t('card4Desc')}
              </p>
            </div>

            <div className="mt-auto flex items-end gap-2 h-24">
              {[40, 60, 80, 100, 70].map((h, i) => (
                <div
                  key={i}
                  className="flex-1 bg-white/5 hover:bg-white/10 transition-colors rounded-t-sm border-t border-white/10 relative group/bar"
                  style={{ height: `${h}%` }}
                >
                  {i === 3 && (
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 text-[10px] font-medium bg-white text-black px-2 py-0.5 rounded opacity-0 group-hover/bar:opacity-100 transition-opacity">
                      H7
                    </div>
                  )}
                </div>
              ))}
            </div>
          </motion.div>

          {/* Card 5: Bottom Middle & Right */}
          <motion.div
            whileHover={{ scale: 0.99 }}
            className="md:col-span-2 rounded-3xl p-8 flex flex-col relative overflow-hidden bg-[#0A0A0A] border border-white/10 group"
          >
            <div className="absolute right-0 top-0 bottom-0 w-1/2 bg-gradient-to-l from-indigo-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

            <div className="relative z-10 max-w-sm">
              <h3 className="text-xl font-medium tracking-tight mb-2">
                {t('card5Title')}
              </h3>
              <p className="text-sm text-neutral-400 mb-6">
                {t('card5Desc')}
              </p>
              <div className="flex gap-3">
                <div className="px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-white">
                  STEP
                </div>
                <div className="px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-white">
                  IGES
                </div>
                <div className="px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-white">
                  STL
                </div>
              </div>
            </div>

            <Globe className="absolute right-8 bottom-8 w-32 h-32 text-white/5 transform group-hover:rotate-12 transition-transform duration-700" />
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/10 py-12">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Box className="w-5 h-5 text-white" />
            <span className="font-medium text-sm">GlowPoint</span>
          </div>
          <p className="text-neutral-500 text-sm">
            {t('footerRights')}
          </p>
        </div>
      </footer>

    </div>
  );
}
