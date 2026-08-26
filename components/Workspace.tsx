import { useState, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  ArrowLeft,
  Maximize,
  Settings,
  Download,
  AlertCircle,
  Check,
  History,
  Loader2,
  Zap,
} from "lucide-react";
import { Canvas } from "@react-three/fiber";
import {
  OrbitControls,
  Environment,
  ContactShadows,
} from "@react-three/drei";
import LanguageSelector from "./LanguageSelector";
import { useLanguage } from "@/lib/i18n";
import dynamic from "next/dynamic";
import type { SketchPadRef } from "./SketchPad";
import DynamicModel, { ModelPart } from "./DynamicModel";

const SketchPad = dynamic(() => import("./SketchPad"), { ssr: false });


export default function Workspace({ onBack }: { onBack: () => void }) {
  const [dimension, setDimension] = useState(50);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(50);
  const [hasError, setHasError] = useState(false);
  const [highlightEdge, setHighlightEdge] = useState(false);
  const { t } = useLanguage();

  const [isProcessing, setIsProcessing] = useState(false);
  const [modelParts, setModelParts] = useState<ModelPart[]>([
    { type: 'box', position: [0, 0.5, 0], size: [4, 1, 2], color: '#4f46e5' },
    { type: 'box', position: [-1.5, 2.5, 0], size: [1, 3, 2], color: '#4f46e5' }
  ]);
  const sketchRef = useRef<SketchPadRef>(null);

  const handleAIProcess = async () => {
    if (!sketchRef.current) return;
    
    const imageData = sketchRef.current.getBase64Image();
    if (!imageData) return;

    setIsProcessing(true);
    try {
      const response = await fetch('/api/generate-3d', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageData }),
      });

      if (!response.ok) throw new Error('API request failed');

      const data = await response.json();
      if (Array.isArray(data)) {
        setModelParts(data);
      }
    } catch (error) {
      console.error('AI Error:', error);
      alert('AI analysis failed. Please check your API key.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleApply = () => {
    setDimension(editValue);
    setIsEditing(false);
    setHighlightEdge(false);
  };

  return (
    <div className="w-full h-full flex flex-col bg-black text-white">
      {/* Top Bar */}
      <header className="h-14 border-b border-white/5 bg-black/50 backdrop-blur-xl flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="p-2 hover:bg-white/5 rounded-md transition-colors text-slate-400 hover:text-white"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-sm font-medium tracking-wider uppercase">
            {t('project')}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSelector />
          <button
            onClick={() => setHasError(!hasError)}
            className={`px-3 py-1.5 text-xs font-medium rounded border transition-colors ${
              hasError
                ? "bg-red-500/20 border-red-500/50 text-red-400"
                : "border-white/10 hover:bg-white/5"
            }`}
          >
            {hasError ? t('fixError') : t('simulateError')}
          </button>
          <button className="flex items-center gap-2 px-3 py-1.5 border border-white/10 hover:bg-white/5 text-slate-300 text-xs font-medium rounded transition-colors">
            <History className="w-4 h-4" />
            {t('versionHistory')}
          </button>
          <button className="p-2 hover:bg-white/5 rounded-md transition-colors text-slate-400 hover:text-white">
            <Settings className="w-5 h-5" />
          </button>
          <button
            onClick={handleAIProcess}
            disabled={isProcessing}
            className={`flex items-center gap-2 px-4 py-1.5 bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white text-sm font-bold rounded-full transition-all ml-2 shadow-[0_0_15px_rgba(79,70,229,0.4)] ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isProcessing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Zap className="w-4 h-4" />
            )}
            {isProcessing ? 'Analyzing...' : 'AI Generate'}
          </button>
          <button className="flex items-center gap-2 px-4 py-1.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white text-sm font-bold rounded-full transition-all ml-2 shadow-[0_0_15px_rgba(59,130,246,0.3)]">
            <Download className="w-4 h-4" />
            {t('exportStep')}
          </button>
        </div>
      </header>

      {/* Split Screen */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel: 2D Source View */}
        <div className="w-1/2 border-r border-white/5 bg-black relative flex flex-col">
          <div className="absolute top-4 left-4 z-10 bg-black/50 backdrop-blur-xl px-3 py-1.5 rounded text-xs font-medium tracking-wider border border-white/10">
            {t('view2d')}
          </div>

          <div className="flex-1 relative flex items-center justify-center p-8 overflow-hidden bg-[url('/assets/sketch_grid.png')] bg-repeat opacity-90 mix-blend-screen">
            <div className="absolute inset-0 bg-black/90" />
            {/* Mock 2D Sketch */}
            <div className="relative z-10 w-[400px] h-[300px] border border-white/10 rounded-xl bg-[#0A0A0A]/80 backdrop-blur-md flex items-center justify-center shadow-2xl">
              <SketchPad ref={sketchRef} hasError={hasError} />

              {/* Dimension Bounding Box */}
              <div
                className={`absolute bottom-[-40px] left-1/2 -translate-x-1/2 px-3 py-1 border-2 border-dashed cursor-pointer transition-colors ${
                  highlightEdge
                    ? "border-blue-500 bg-blue-500/20 text-blue-300"
                    : "border-blue-400/50 hover:border-blue-400 text-slate-300"
                }`}
                onClick={() => {
                  setIsEditing(true);
                  setHighlightEdge(true);
                }}
                onMouseEnter={() => setHighlightEdge(true)}
                onMouseLeave={() => !isEditing && setHighlightEdge(false)}
              >
                {dimension} mm
              </div>

              {/* Error Tooltip */}
              <AnimatePresence>
                {hasError && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-red-950 border border-red-500/50 text-red-200 px-4 py-3 rounded-lg shadow-xl flex items-start gap-3 max-w-xs"
                  >
                    <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                    <div className="text-sm">
                      <p className="font-medium mb-1">{t('errorTitle')}</p>
                      <p className="text-red-300/80 text-xs">
                        {t('errorDesc')}
                      </p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Edit Popover */}
              <AnimatePresence>
                {isEditing && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="absolute bottom-[-90px] left-1/2 -translate-x-1/2 bg-[#0A0A0A] border border-white/10 p-3 rounded-xl shadow-[0_10px_40px_rgba(0,0,0,0.5)] flex items-center gap-2 z-20"
                  >
                    <input
                      type="number"
                      value={editValue}
                      onChange={(e) => setEditValue(Number(e.target.value))}
                      className="w-20 bg-black border border-white/10 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-indigo-500"
                      autoFocus
                    />
                    <span className="text-neutral-400 text-sm">mm</span>
                    <select className="ml-2 bg-black border border-white/10 rounded px-2 py-1 text-xs text-neutral-300 focus:outline-none focus:border-indigo-500">
                      <option value="H7">H7 ({t('hole')})</option>
                      <option value="h7">h7 ({t('shaft')})</option>
                      <option value="js6">js6 ({t('transition')})</option>
                      <option value="custom">{t('custom')}...</option>
                    </select>
                    <button
                      onClick={handleApply}
                      className="ml-2 p-1.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white rounded transition-colors"
                    >
                      <Check className="w-4 h-4" />
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        {/* Right Panel: 3D Interactive View */}
        <div className="w-1/2 bg-black relative flex flex-col">
          <div className="absolute top-4 left-4 z-10 bg-black/50 backdrop-blur-xl px-3 py-1.5 rounded text-xs font-medium tracking-wider border border-white/10">
            {t('view3d')}
          </div>
          <div className="absolute top-4 right-4 z-10 flex gap-2">
            <button className="p-1.5 bg-black/50 backdrop-blur-xl rounded border border-white/10 text-neutral-400 hover:text-white transition-colors">
              <Maximize className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 w-full h-full cursor-move">
            <Canvas camera={{ position: [5, 5, 5], fov: 45 }}>
              <ambientLight intensity={0.5} />
              <directionalLight
                position={[10, 10, 10]}
                intensity={1}
                castShadow
              />
              <Environment preset="city" />
              <gridHelper
                args={[20, 20, "#1e293b", "#0f172a"]}
                position={[0, -1, 0]}
              />

              {/* AI-Generated 3D Model */}
              <group position={[0, -1, 0]}>
                <DynamicModel parts={modelParts} />
              </group>

              <ContactShadows
                position={[0, -1, 0]}
                opacity={0.4}
                scale={20}
                blur={2}
                far={4}
              />
              <OrbitControls
                makeDefault
                minPolarAngle={0}
                maxPolarAngle={Math.PI / 2 + 0.1}
              />
            </Canvas>
          </div>
        </div>
      </div>
    </div>
  );
}
