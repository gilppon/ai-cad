import { motion } from 'motion/react';
import { Upload, Image as ImageIcon, Box, Ruler, Download, History } from 'lucide-react';
import Image from 'next/image';

const menuItems = [
  { icon: Upload, label: 'UPLOAD SKETCH' },
  { icon: ImageIcon, label: '2D SOURCE VIEW' },
  { icon: Box, label: '3D INTERACTIVE' },
  { icon: Ruler, label: 'CONSTRAINTS' },
  { icon: Download, label: 'EXPORT TO STEP' },
  { icon: History, label: 'VERSION HISTORY' },
];

export default function CircularMenu({ onNavigate }: { onNavigate: () => void }) {
  const R = 450; // Radius of the menu items arc
  const cx = 0; // Center X (left edge)
  
  // Distribute items evenly between -60 and 60 degrees
  const startAngle = -60;
  const endAngle = 60;
  const angleStep = (endAngle - startAngle) / (menuItems.length - 1);

  return (
    <div className="relative w-full h-full overflow-hidden">
      {/* Background Image */}
      <Image
        src="/assets/engineering_bg.png"
        alt="Background"
        fill
        className="object-cover opacity-30 mix-blend-overlay"
        priority
      />
      <div className="absolute inset-0 bg-gradient-to-r from-slate-900 via-slate-900/80 to-transparent" />

      {/* Curved Line */}
      <div
        className="absolute rounded-full border border-white/20 pointer-events-none"
        style={{
          width: `${R * 2}px`,
          height: `${R * 2}px`,
          left: `calc(${cx}px - ${R}px)`,
          top: `calc(50% - ${R}px)`,
        }}
      />

      {/* Main Circle (Left side) */}
      <div 
        className="absolute rounded-full border border-white/30 bg-slate-900/60 backdrop-blur-md flex flex-col items-center justify-center shadow-2xl z-10"
        style={{
          width: '500px',
          height: '500px',
          left: '-250px',
          top: 'calc(50% - 250px)',
        }}
      >
        <div className="ml-32 flex flex-col items-center text-center">
          <h1 className="text-sm font-light tracking-[0.3em] text-white/60 mb-2">AI CAD</h1>
          <h2 className="text-4xl font-bold tracking-widest text-white mb-6">CONVERTER</h2>
          <div className="w-32 h-px bg-white/20 mb-6" />
          <p className="text-lg font-light text-white/80 mb-1">Parametric</p>
          <p className="text-lg font-light text-white/80">Modeling</p>
          <div className="mt-8 flex items-center gap-2 text-white/50 text-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            SYSTEM ONLINE
          </div>
        </div>
      </div>

      {/* Menu Items */}
      {menuItems.map((item, i) => {
        const angleDeg = startAngle + i * angleStep;
        const angleRad = (angleDeg * Math.PI) / 180;
        const x = cx + R * Math.cos(angleRad);
        const y = R * Math.sin(angleRad);

        return (
          <motion.div
            key={i}
            className="absolute flex items-center gap-4 group cursor-pointer z-20"
            style={{
              left: `${x}px`,
              top: `calc(50% + ${y}px)`,
              transform: 'translate(-50%, -50%)',
            }}
            initial={{ opacity: 0, x: x - 50 }}
            animate={{ opacity: 1, x: x }}
            transition={{ delay: i * 0.1, duration: 0.5, ease: 'easeOut' }}
            onClick={onNavigate}
          >
            <div className="w-14 h-14 rounded-full border border-white/40 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm group-hover:bg-white/20 group-hover:border-white group-hover:scale-110 transition-all duration-300 shadow-lg">
              <item.icon className="w-5 h-5 text-white/80 group-hover:text-white transition-colors" />
            </div>
            <span className="text-white/70 tracking-[0.2em] text-xs font-medium group-hover:text-white transition-colors uppercase whitespace-nowrap">
              {item.label}
            </span>
          </motion.div>
        );
      })}
    </div>
  );
}
