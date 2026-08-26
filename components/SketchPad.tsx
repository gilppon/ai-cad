import React, { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import { Stage, Layer, Line, Circle, Arc, Image as KonvaImage } from 'react-konva';
import type Konva from 'konva';
import { Pencil, Circle as CircleIcon, MousePointer2, Upload, Trash2 } from 'lucide-react';

type Tool = 'select' | 'line' | 'circle' | 'arc';

interface ShapeData {
  id: string;
  type: Tool;
  points?: number[];
  x?: number;
  y?: number;
  radius?: number;
  angle?: number;
  rotation?: number;
}

export interface SketchPadRef {
  getBase64Image: () => string | undefined;
  clear: () => void;
}

const SketchPad = forwardRef<SketchPadRef, { hasError?: boolean }>(({ hasError }, ref) => {
  const [tool, setTool] = useState<Tool>('line');
  const [shapes, setShapes] = useState<ShapeData[]>([
    // Initial L-Shape mock
    { id: 'initial-1', type: 'line', points: [100, 250, 300, 250, 300, 200, 150, 200, 150, 50, 100, 50, 100, 250] }
  ]);
  const [currentShape, setCurrentShape] = useState<ShapeData | null>(null);
  const isDrawing = useRef(false);
  const stageRef = useRef<Konva.Stage | null>(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 300 });
  const containerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [bgImage, setBgImage] = useState<HTMLImageElement | null>(null);
  const [bgImageProps, setBgImageProps] = useState({ x: 0, y: 0, width: 0, height: 0 });

  useImperativeHandle(ref, () => ({
    getBase64Image: () => {
      if (!stageRef.current) return undefined;
      return stageRef.current.toDataURL();
    },
    clear: () => {
      setShapes([]);
      setBgImage(null);
    },
  }));

  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.offsetWidth,
          height: containerRef.current.offsetHeight
        });
      }
    };
    
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = () => {
        const img = new window.Image();
        img.src = reader.result as string;
        img.onload = () => {
          // Calculate scale to fit within dimensions
          const scale = Math.min(
            dimensions.width / img.width,
            dimensions.height / img.height
          );
          const width = img.width * scale;
          const height = img.height * scale;
          const x = (dimensions.width - width) / 2;
          const y = (dimensions.height - height) / 2;
          
          setBgImage(img);
          setBgImageProps({ x, y, width, height });
        };
      };
      reader.readAsDataURL(file);
    }
    // Reset input so the same file can be uploaded again if needed
    if (e.target) e.target.value = '';
  };

  const handleMouseDown = (e: Konva.KonvaEventObject<MouseEvent>) => {
    if (tool === 'select') return;
    
    const stage = e.target.getStage();
    const pos = stage?.getPointerPosition();
    if (!pos) return;

    isDrawing.current = true;
    const id = Date.now().toString();

    if (tool === 'line') {
      setCurrentShape({ id, type: 'line', points: [pos.x, pos.y] });
    } else if (tool === 'circle') {
      setCurrentShape({ id, type: 'circle', x: pos.x, y: pos.y, radius: 0 });
    } else if (tool === 'arc') {
      setCurrentShape({ id, type: 'arc', x: pos.x, y: pos.y, radius: 0, angle: 0, rotation: 0 });
    }
  };

  const handleMouseMove = (e: Konva.KonvaEventObject<MouseEvent>) => {
    if (!isDrawing.current || !currentShape) return;

    const stage = e.target.getStage();
    const point = stage?.getPointerPosition();
    if (!point) return;

    if (tool === 'line') {
      let newPoints = currentShape.points ? [...currentShape.points] : [];
      newPoints = newPoints.concat([point.x, point.y]);
      setCurrentShape({ ...currentShape, points: newPoints });
    } else if (tool === 'circle') {
      const dx = point.x - (currentShape.x || 0);
      const dy = point.y - (currentShape.y || 0);
      const radius = Math.sqrt(dx * dx + dy * dy);
      setCurrentShape({ ...currentShape, radius });
    } else if (tool === 'arc') {
      const dx = point.x - (currentShape.x || 0);
      const dy = point.y - (currentShape.y || 0);
      const radius = Math.sqrt(dx * dx + dy * dy);
      let angle = Math.atan2(dy, dx) * (180 / Math.PI);
      if (angle < 0) angle += 360;
      setCurrentShape({ ...currentShape, radius, angle, rotation: 0 });
    }
  };

  const handleMouseUp = () => {
    if (!isDrawing.current || !currentShape) return;
    isDrawing.current = false;
    setShapes([...shapes, currentShape]);
    setCurrentShape(null);
  };

  const strokeColor = hasError ? "#ef4444" : "#94a3b8";
  const strokeDash = hasError ? [5, 5] : [];

  useImperativeHandle(ref, () => ({
    getBase64Image: () => {
      if (stageRef.current) {
        return stageRef.current.toDataURL();
      }
      return undefined;
    },
    clear: () => {
      setShapes([]);
      setBgImage(null);
    }
  }));

  return (
    <div className="w-full h-full flex flex-col relative" ref={containerRef}>
      {/* Toolbar */}
      <div className="absolute top-4 right-4 z-20 flex flex-col gap-2 bg-black/80 backdrop-blur-md p-2 rounded-lg border border-white/10">
        <button 
          onClick={() => setTool('select')}
          className={`p-2 rounded transition-colors ${tool === 'select' ? 'bg-blue-500/30 text-blue-400' : 'hover:bg-white/10 text-slate-400'}`}
          title="Select"
        >
          <MousePointer2 className="w-4 h-4" />
        </button>
        <button 
          onClick={() => setTool('line')}
          className={`p-2 rounded transition-colors ${tool === 'line' ? 'bg-blue-500/30 text-blue-400' : 'hover:bg-white/10 text-slate-400'}`}
          title="Draw Line"
        >
          <Pencil className="w-4 h-4" />
        </button>
        <button 
          onClick={() => setTool('circle')}
          className={`p-2 rounded transition-colors ${tool === 'circle' ? 'bg-blue-500/30 text-blue-400' : 'hover:bg-white/10 text-slate-400'}`}
          title="Draw Circle"
        >
          <CircleIcon className="w-4 h-4" />
        </button>
        <button 
          onClick={() => setTool('arc')}
          className={`p-2 rounded transition-colors ${tool === 'arc' ? 'bg-blue-500/30 text-blue-400' : 'hover:bg-white/10 text-slate-400'}`}
          title="Draw Arc"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
            <path d="M3 3v5h5" />
          </svg>
        </button>
        <button 
          onClick={() => fileInputRef.current?.click()}
          className="p-2 rounded transition-colors hover:bg-white/10 text-slate-400 mt-2 border-t border-white/10"
          title="Upload Sketch"
        >
          <Upload className="w-4 h-4" />
        </button>
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleImageUpload} 
          accept="image/*" 
          className="hidden" 
        />
        <button 
          onClick={() => { setShapes([]); setBgImage(null); }}
          className="p-2 rounded transition-colors hover:bg-red-500/20 text-red-400 mt-2 border-t border-white/10"
          title="Clear All"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 w-full h-full cursor-crosshair">
        <Stage
          width={dimensions.width}
          height={dimensions.height}
          onMouseDown={handleMouseDown}
          onMousemove={handleMouseMove}
          onMouseup={handleMouseUp}
          ref={stageRef}
        >
          <Layer>
            {bgImage && (
              <KonvaImage
                image={bgImage}
                x={bgImageProps.x}
                y={bgImageProps.y}
                width={bgImageProps.width}
                height={bgImageProps.height}
                opacity={0.5}
              />
            )}
            {shapes.map((shape) => {
              if (shape.type === 'line') {
                return <Line key={shape.id} points={shape.points || []} stroke={strokeColor} strokeWidth={3} dash={strokeDash} tension={0.5} lineCap="round" lineJoin="round" />;
              }
              if (shape.type === 'circle') {
                return <Circle key={shape.id} x={shape.x || 0} y={shape.y || 0} radius={shape.radius || 0} stroke={strokeColor} strokeWidth={3} dash={strokeDash} />;
              }
              if (shape.type === 'arc') {
                return <Arc key={shape.id} x={shape.x || 0} y={shape.y || 0} innerRadius={shape.radius || 0} outerRadius={shape.radius || 0} angle={shape.angle || 0} rotation={shape.rotation || 0} stroke={strokeColor} strokeWidth={3} dash={strokeDash} />;
              }
              return null;
            })}
            
            {/* Current Shape being drawn */}
            {currentShape && currentShape.type === 'line' && (
              <Line points={currentShape.points || []} stroke="#60a5fa" strokeWidth={3} tension={0.5} lineCap="round" lineJoin="round" />
            )}
            {currentShape && currentShape.type === 'circle' && (
              <Circle x={currentShape.x || 0} y={currentShape.y || 0} radius={currentShape.radius || 0} stroke="#60a5fa" strokeWidth={3} />
            )}
            {currentShape && currentShape.type === 'arc' && (
              <Arc x={currentShape.x || 0} y={currentShape.y || 0} innerRadius={currentShape.radius || 0} outerRadius={currentShape.radius || 0} angle={currentShape.angle || 0} rotation={currentShape.rotation || 0} stroke="#60a5fa" strokeWidth={3} />
            )}
          </Layer>
        </Stage>
      </div>
    </div>
  );
});

SketchPad.displayName = 'SketchPad';
export default SketchPad;
