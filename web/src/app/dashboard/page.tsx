"use client";

import { useState } from "react";
import { UploadCloud, FileType2, Building2, CheckCircle2 } from "lucide-react";
import { clsx } from "clsx";

export default function DashboardPage() {
  const [isDragging, setIsDragging] = useState(false);

  return (
    <div className="max-w-6xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="flex justify-between items-start mb-4">
            <div className="p-3 bg-blue-500/10 rounded-xl">
              <Building2 className="w-6 h-6 text-blue-400" />
            </div>
            <span className="text-xs font-medium px-2 py-1 bg-green-500/10 text-green-400 rounded-full">+12%</span>
          </div>
          <h3 className="text-3xl font-bold text-white mb-1">1,204</h3>
          <p className="text-sm text-neutral-400">Total Models Generated</p>
        </div>

        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="flex justify-between items-start mb-4">
            <div className="p-3 bg-purple-500/10 rounded-xl">
              <CheckCircle2 className="w-6 h-6 text-purple-400" />
            </div>
          </div>
          <h3 className="text-3xl font-bold text-white mb-1">99.8%</h3>
          <p className="text-sm text-neutral-400">RAG Compliance Accuracy</p>
        </div>

        <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="flex justify-between items-start mb-4">
            <div className="p-3 bg-orange-500/10 rounded-xl">
              <FileType2 className="w-6 h-6 text-orange-400" />
            </div>
          </div>
          <h3 className="text-3xl font-bold text-white mb-1">3</h3>
          <p className="text-sm text-neutral-400">Available Credits</p>
        </div>
      </div>

      {/* Upload Section */}
      <div className="mt-8">
        <h2 className="text-xl font-semibold text-white mb-4">Create New Model</h2>
        <div 
          className={clsx(
            "border-2 border-dashed rounded-3xl p-12 flex flex-col items-center justify-center text-center transition-all duration-300 relative overflow-hidden",
            isDragging 
              ? "border-blue-500 bg-blue-500/5 scale-[1.01]" 
              : "border-neutral-800 bg-neutral-900/50 hover:border-neutral-700 hover:bg-neutral-900"
          )}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => { e.preventDefault(); setIsDragging(false); }}
        >
          <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-500/10 via-transparent to-transparent opacity-0 transition-opacity duration-500" style={{ opacity: isDragging ? 1 : 0 }}></div>
          
          <div className={clsx("p-6 bg-neutral-950 rounded-full mb-6 shadow-2xl transition-transform duration-300", isDragging ? "scale-110 text-blue-400 shadow-blue-500/20" : "text-neutral-500")}>
            <UploadCloud className="w-12 h-12" />
          </div>
          <h3 className="text-2xl font-bold text-white mb-2">Drag & Drop architectural PDF</h3>
          <p className="text-neutral-400 max-w-md mx-auto mb-8">
            Upload a high-resolution PDF or CAD export. Our AI will automatically reconstruct the 3D IFC model and run Japanese compliance checks.
          </p>
          <label className="relative overflow-hidden group cursor-pointer">
            <input type="file" className="hidden" accept=".pdf" />
            <div className="absolute inset-0 bg-blue-600 group-hover:bg-blue-500 transition-colors"></div>
            <div className="relative px-8 py-3.5 text-white font-medium flex items-center justify-center">
              Browse Files
            </div>
          </label>
          <p className="mt-4 text-xs text-neutral-500">Supports .pdf (max 50MB). Requires 3 credits per floor.</p>
        </div>
      </div>
    </div>
  );
}
