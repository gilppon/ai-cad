import { useEffect, useState, useRef, MouseEvent, WheelEvent } from 'react';
import { useParams, Link } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { ArrowLeft, Save, Undo, ZoomIn, ZoomOut, Maximize } from 'lucide-react';

// --- Types ---
interface Point { x: number; y: number; }
interface Room { id: number; kind: string; polygon: Point[]; }
interface Wall { id?: number; p1: Point; p2: Point; kind?: string; }
interface GeometryPayload { rooms: Room[]; walls: Wall[]; }

// --- Dummy Data ---
const DUMMY_PAYLOAD: GeometryPayload = {
  rooms: [
    { id: 1, kind: 'LDK', polygon: [{x: 100, y: 100}, {x: 400, y: 100}, {x: 400, y: 300}, {x: 100, y: 300}] },
    { id: 2, kind: 'BEDROOM', polygon: [{x: 400, y: 100}, {x: 600, y: 100}, {x: 600, y: 300}, {x: 400, y: 300}] },
    { id: 3, kind: 'BATHROOM', polygon: [{x: 100, y: 300}, {x: 300, y: 300}, {x: 300, y: 450}, {x: 100, y: 450}] },
  ],
  walls: [
    { p1: {x: 100, y: 100}, p2: {x: 600, y: 100} },
    { p1: {x: 600, y: 100}, p2: {x: 600, y: 300} },
    { p1: {x: 600, y: 300}, p2: {x: 100, y: 300} },
    { p1: {x: 100, y: 300}, p2: {x: 100, y: 100} },
    { p1: {x: 400, y: 100}, p2: {x: 400, y: 300} },
    { p1: {x: 300, y: 300}, p2: {x: 300, y: 450} },
    { p1: {x: 100, y: 450}, p2: {x: 300, y: 450} },
    { p1: {x: 100, y: 450}, p2: {x: 100, y: 300} },
  ]
};

const ROOM_COLORS: Record<string, string> = {
  LDK: '#fef08a',      // yellow-200
  BEDROOM: '#bfdbfe',  // blue-200
  BATHROOM: '#a7f3d0', // emerald-200
  CORRIDOR: '#e5e7eb', // gray-200
  UNKNOWN: '#fecaca',  // red-200
};

export default function Editor() {
  const { projectId } = useParams<{ projectId: string }>();
  const [loading, setLoading] = useState(true);
  const [project, setProject] = useState<any>({ original_filename: 'Loading...' });
  const [payload, setPayload] = useState<GeometryPayload>({ rooms: [], walls: [] });

  useEffect(() => {
    if (projectId) fetchProjectData(projectId);
  }, [projectId]);

  const fetchProjectData = async (id: string) => {
    try {
      setLoading(true);
      const { data: projectData, error } = await supabase
        .from('projects')
        .select('*')
        .eq('id', id)
        .single();
      if (error) throw error;
      setProject(projectData);

      const { data: { session } } = await supabase.auth.getSession();
      const res = await fetch(`http://localhost:8000/api/v1/projects/${id}/geometry`, {
        headers: { 'Authorization': `Bearer ${session?.access_token}` }
      });
      if (res.ok) {
        const geomData = await res.json();
        setPayload(geomData);
      } else {
        setPayload(DUMMY_PAYLOAD);
      }
    } catch (error) {
      console.error('Error fetching project:', error);
      setPayload(DUMMY_PAYLOAD);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveAndRebuild = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const res = await fetch(`http://localhost:8000/api/v1/projects/${projectId}/correction`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session?.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Failed to save correction');
      alert('Correction saved and IFC rebuilt successfully!');
    } catch (error) {
      console.error(error);
      alert('Error saving correction.');
    }
  };
  
  // View transform
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const startPanRef = useRef({ x: 0, y: 0 });

  // Interaction
  const [selectedRoomId, setSelectedRoomId] = useState<number | null>(null);

  // Tools
  const [activeTool, setActiveTool] = useState<string>('select');

  // Prevent default scrolling on canvas
  useEffect(() => {
    const handleGlobalWheel = (e: globalThis.WheelEvent) => {
      if (e.ctrlKey) e.preventDefault();
    };
    document.addEventListener('wheel', handleGlobalWheel, { passive: false });
    return () => document.removeEventListener('wheel', handleGlobalWheel);
  }, []);

  const handleWheel = (e: WheelEvent) => {
    e.preventDefault();
    const zoomFactor = 1.1;
    if (e.deltaY < 0) {
      setScale(s => s * zoomFactor);
    } else {
      setScale(s => Math.max(0.1, s / zoomFactor));
    }
  };

  const handleMouseDown = (e: MouseEvent) => {
    if (e.button === 1 || e.button === 2 || activeTool === 'pan') {
      setIsPanning(true);
      startPanRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    } else if (activeTool === 'select') {
      // If clicking on empty canvas, deselect
      if (e.target instanceof SVGElement && e.target.tagName === 'svg') {
        setSelectedRoomId(null);
      }
    }
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (isPanning) {
      setPan({
        x: e.clientX - startPanRef.current.x,
        y: e.clientY - startPanRef.current.y
      });
    }
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  const handleRoomClick = (e: MouseEvent, roomId: number) => {
    if (isPanning || activeTool === 'pan') return;
    e.stopPropagation();
    setSelectedRoomId(roomId);
  };

  const handleChangeRoomType = (newType: string) => {
    if (selectedRoomId === null) return;
    setPayload(prev => ({
      ...prev,
      rooms: prev.rooms.map(r => r.id === selectedRoomId ? { ...r, kind: newType } : r)
    }));
  };

  if (loading) return <div className="p-8">Loading...</div>;

  return (
    <div className="flex flex-col h-screen bg-gray-50 overflow-hidden select-none font-sans">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4 flex justify-between items-center shrink-0 z-10 shadow-sm">
        <div className="flex items-center gap-4">
          <Link to="/dashboard" className="text-gray-500 hover:text-gray-900 transition-colors">
            <ArrowLeft size={20} />
          </Link>
          <h1 className="text-xl font-bold text-gray-800">
            Correction Editor 
            <span className="text-sm font-normal text-gray-500 ml-3 bg-gray-100 px-2 py-1 rounded">
              {project?.original_filename}
            </span>
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-3 py-1.5 text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors font-medium text-sm">
            <Undo size={16} /> Revert
          </button>
          <button onClick={handleSaveAndRebuild} className="flex items-center gap-2 px-4 py-1.5 text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors font-medium text-sm shadow-sm">
            <Save size={16} /> Save & Rebuild
          </button>
        </div>
      </header>

      {/* Workspace */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Tools panel */}
        <div className="w-64 bg-white border-r flex flex-col z-10 shadow-sm relative">
          <div className="p-5 flex-1 overflow-y-auto">
            <h3 className="font-bold text-gray-400 uppercase text-xs tracking-wider mb-3">Tools</h3>
            <div className="flex flex-col gap-1.5 mb-8">
              <button 
                className={`text-left px-3 py-2.5 rounded-md text-sm transition-colors ${activeTool === 'select' ? 'bg-blue-50 text-blue-700 font-semibold ring-1 ring-blue-200' : 'text-gray-600 hover:bg-gray-50'}`}
                onClick={() => setActiveTool('select')}
              >Select & Edit</button>
              <button 
                className={`text-left px-3 py-2.5 rounded-md text-sm transition-colors ${activeTool === 'pan' ? 'bg-blue-50 text-blue-700 font-semibold ring-1 ring-blue-200' : 'text-gray-600 hover:bg-gray-50'}`}
                onClick={() => setActiveTool('pan')}
              >Pan View</button>
            </div>

            {selectedRoomId !== null && (
              <div className="mb-8 p-4 bg-blue-50/50 rounded-xl border border-blue-100 shadow-sm">
                <h3 className="font-semibold text-blue-900 text-sm mb-3">Edit Room #{selectedRoomId}</h3>
                <div className="grid grid-cols-2 gap-2">
                  {['LDK', 'BEDROOM', 'BATHROOM', 'CORRIDOR', 'UNKNOWN'].map(t => (
                    <button 
                      key={t}
                      onClick={() => handleChangeRoomType(t)}
                      className="text-xs py-1.5 px-2 bg-white border border-blue-200 rounded text-gray-700 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-all font-medium"
                    >{t}</button>
                  ))}
                </div>
              </div>
            )}

            <h3 className="font-bold text-gray-400 uppercase text-xs tracking-wider mb-3">Incident Semantics</h3>
            <button className="w-full text-left px-3 py-2.5 rounded-md hover:bg-blue-50 text-blue-600 border border-transparent hover:border-blue-200 text-sm transition-colors font-medium">Add Leak Source</button>
            <button className="w-full text-left px-3 py-2.5 rounded-md hover:bg-red-50 text-red-600 border border-transparent hover:border-red-200 text-sm mt-1.5 transition-colors font-medium">Paint Damage Zone</button>
          </div>
        </div>

        {/* SVG Canvas Area */}
        <div 
          className="flex-1 bg-gray-100 relative overflow-hidden"
          style={{ cursor: activeTool === 'pan' ? (isPanning ? 'grabbing' : 'grab') : 'crosshair' }}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onContextMenu={(e) => e.preventDefault()}
        >
          {/* Controls overlay */}
          <div className="absolute bottom-6 right-6 flex gap-2 z-20 bg-white p-2 rounded-xl shadow-lg border border-gray-200/60">
            <button onClick={() => setScale(s => s * 1.2)} className="p-2 hover:bg-gray-100 rounded-lg text-gray-600 transition-colors" title="Zoom In"><ZoomIn size={20} /></button>
            <button onClick={() => setScale(s => s / 1.2)} className="p-2 hover:bg-gray-100 rounded-lg text-gray-600 transition-colors" title="Zoom Out"><ZoomOut size={20} /></button>
            <div className="w-px bg-gray-200 my-1 mx-1"></div>
            <button onClick={() => { setScale(1); setPan({x:0, y:0}); }} className="p-2 hover:bg-gray-100 rounded-lg text-gray-600 transition-colors" title="Reset View"><Maximize size={20} /></button>
          </div>

          <svg 
            width="100%" 
            height="100%" 
            className="absolute top-0 left-0"
          >
            {/* Grid background for aesthetics */}
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e5e7eb" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />

            <g transform={`translate(${pan.x + window.innerWidth/4}, ${pan.y + window.innerHeight/4}) scale(${scale})`}>
              {/* Render Rooms */}
              {payload.rooms.map(room => {
                const pointsStr = room.polygon.map(p => `${p.x},${p.y}`).join(' ');
                const isSelected = selectedRoomId === room.id;
                return (
                  <polygon
                    key={`room-${room.id}`}
                    points={pointsStr}
                    fill={ROOM_COLORS[room.kind] || ROOM_COLORS.UNKNOWN}
                    fillOpacity={isSelected ? 0.8 : 0.5}
                    stroke={isSelected ? '#3b82f6' : '#9ca3af'}
                    strokeWidth={isSelected ? 4 / scale : 1.5 / scale}
                    onClick={(e) => handleRoomClick(e, room.id)}
                    className="cursor-pointer hover:fill-opacity-70 transition-opacity drop-shadow-sm"
                  />
                );
              })}

              {/* Render Walls */}
              {payload.walls.map((wall, idx) => (
                <line
                  key={`wall-${idx}`}
                  x1={wall.p1.x}
                  y1={wall.p1.y}
                  x2={wall.p2.x}
                  y2={wall.p2.y}
                  stroke="#374151"
                  strokeWidth={6 / scale}
                  strokeLinecap="round"
                  className="drop-shadow-sm"
                />
              ))}
            </g>
          </svg>
        </div>
      </div>
    </div>
  );
}
