"use client";

import { useState, useEffect } from "react";
import { Box, Loader2 } from "lucide-react";

interface IfcViewerProps {
  url?: string;
  fallbackMessage?: string;
}

export default function IfcViewer({ url, fallbackMessage = "No 3D Model loaded." }: IfcViewerProps) {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (url) {
      // Simulate loading time for 3D viewer
      const timer = setTimeout(() => {
        setIsLoading(false);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [url]);

  if (!url) {
    return (
      <div className="w-full h-full min-h-[400px] flex flex-col items-center justify-center bg-neutral-900 border border-neutral-800 rounded-xl text-neutral-500">
        <Box className="w-12 h-12 mb-4 opacity-50" />
        <p>{fallbackMessage}</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full min-h-[400px] relative bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden group">
      {isLoading ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-neutral-900/80 backdrop-blur-sm z-10">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-4" />
          <p className="text-blue-400 font-medium">Loading 3D Model...</p>
        </div>
      ) : null}
      
      {/* 3D Canvas Placeholder */}
      <div className="absolute inset-0 flex items-center justify-center opacity-30 pointer-events-none">
        <div className="w-48 h-48 border-4 border-blue-500 rounded-lg transform rotate-45 scale-y-50"></div>
      </div>
      
      {/* Overlay UI */}
      <div className="absolute bottom-4 left-4 right-4 flex justify-between items-end z-20">
        <div className="bg-neutral-950/80 backdrop-blur-md px-4 py-2 rounded-lg border border-neutral-800">
          <p className="text-sm font-medium text-white">Generated IFC Model</p>
          <p className="text-xs text-neutral-400">WebGL Viewer Active</p>
        </div>
        <button className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors shadow-lg">
          Download .ifc
        </button>
      </div>
    </div>
  );
}
