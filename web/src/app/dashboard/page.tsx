"use client";

import { useState, useEffect } from "react";
import { 
  ShieldAlert, Activity, Cpu, Layers, Compass, 
  Database, TrendingUp, Gauge, Zap, UploadCloud, 
  RefreshCw, CheckCircle2, ChevronRight, HelpCircle,
  FolderOpen, Settings, Landmark
} from "lucide-react";
import ThreeDViewer from "@/components/ThreeDViewer";
import { getLocalSession, UserSession } from "@/utils/supabase";
import { API_BASE_URL } from "@/utils/api";

export default function DashboardPage() {
  const [session, setSession] = useState<UserSession | null>(null);
  const [hudTab, setHudTab] = useState<"summary" | "geology" | "inspect" | "construction" | "fire" | "pipeline">("summary");
  const [selectedFloor, setSelectedFloor] = useState<string>("2F");
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");

  const handleFileUpload = async (file: File) => {
    if (!file || !file.name.endsWith('.pdf')) {
      alert("Only PDF files are supported. (.pdf)");
      return;
    }

    setIsUploading(true);
    setUploadProgress("Uploading PDF to FastAPI Backend...");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/convert`, {
        method: "POST",
        headers: {
          "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock-key"
        },
        body: formData
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "PDF upload failed");
      }

      const data = await response.json();
      const taskId = data.task_id;
      setUploadProgress("Analyzing CAD elements (FastAPI + Celery)...");

      // Poll task status
      const interval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_BASE_URL}/api/v1/tasks/${taskId}`);
          if (!statusRes.ok) throw new Error("Failed to get task status");
          const statusData = await statusRes.json();
          
          if (statusData.status === "SUCCESS") {
            clearInterval(interval);
            setIsUploading(false);
            setUploadProgress("Success!");
            
            // Extract project id from result
            const result = statusData.result || {};
            const projectId = result.project_id || "mock_project_123";
            
            alert("CAD 2D-to-3D IFC reconstruction successful! Entering Workspace...");
            window.location.href = `/dashboard/editor?project_id=${projectId}`;
          } else if (statusData.status === "FAILURE") {
            clearInterval(interval);
            setIsUploading(false);
            setUploadProgress("Failed");
            alert("CAD Reconstruction failed: " + statusData.error);
          } else {
            const progress = statusData.progress || 10;
            setUploadProgress(`Processing CAD geometry... (${progress}%)`);
          }
        } catch (err: any) {
          clearInterval(interval);
          setIsUploading(false);
          setUploadProgress("Status check error.");
          console.error(err);
        }
      }, 1500);

    } catch (err: any) {
      setIsUploading(false);
      setUploadProgress("");
      alert(err.message || "Failed to communicate with FastAPI server.");
    }
  };

  useEffect(() => {
    setSession(getLocalSession());
  }, []);

  // 3D 뷰어에 주입할 HUD 모드별 실시간 3D 기하 데이터셋 (동적 갱신 모사)
  const get3DDataByHudTab = () => {
    // 기본 건물 외곽 벽 & 룸
    const baseWalls = [
      { id: 1, p1: { x: 40, y: 40 }, p2: { x: 360, y: 40 }, thickness_px: 12 },
      { id: 2, p1: { x: 360, y: 40 }, p2: { x: 360, y: 260 }, thickness_px: 12 },
      { id: 3, p1: { x: 360, y: 260 }, p2: { x: 40, y: 260 }, thickness_px: 12 },
      { id: 4, p1: { x: 40, y: 260 }, p2: { x: 40, y: 40 }, thickness_px: 12 },
      // 내부 칸막이벽
      { id: 5, p1: { x: 200, y: 40 }, p2: { x: 200, y: 260 }, thickness_px: 8 },
      { id: 6, p1: { x: 200, y: 150 }, p2: { x: 360, y: 150 }, thickness_px: 8 }
    ];

    const baseRooms = [
      {
        id: 1,
        polygon: [{ x: 40, y: 40 }, { x: 200, y: 40 }, { x: 200, y: 260 }, { x: 40, y: 260 }],
        kind: hudTab === "construction" ? "ldk" : "toilet",
        area_m2: 32.4
      },
      {
        id: 2,
        polygon: [{ x: 200, y: 40 }, { x: 360, y: 40 }, { x: 360, y: 150 }, { x: 200, y: 150 }],
        kind: hudTab === "pipeline" ? "shaft" : "bedroom",
        area_m2: 18.5
      },
      {
        id: 3,
        polygon: [{ x: 200, y: 150 }, { x: 360, y: 150 }, { x: 360, y: 260 }, { x: 200, y: 260 }],
        kind: hudTab === "fire" ? "kitchen" : "toilet",
        area_m2: 15.2
      }
    ];

    switch (hudTab) {
      case "geology":
        return {
          walls: baseWalls.map(w => ({ ...w, thickness_px: w.thickness_px + 4 })),
          rooms: baseRooms.map(r => ({ ...r, kind: "ldk" })),
          leakSources: [],
          damageZones: []
        };
      case "inspect":
        return {
          walls: baseWalls,
          rooms: baseRooms,
          leakSources: [
            { point: { x: 280, y: 95 }, room_id: 2, description: "天井配管継手部から微細漏水検出" }
          ],
          damageZones: [
            { id: 1, damage_type: "leak", severity: "high", polygon: [{ x: 240, y: 60 }, { x: 320, y: 60 }, { x: 320, y: 130 }, { x: 240, y: 130 }], room_id: 2 }
          ]
        };
      case "construction":
        return {
          walls: baseWalls.map(w => ({ ...w, thickness_px: 4 })),
          rooms: baseRooms,
          leakSources: [],
          damageZones: []
        };
      case "fire":
        return {
          walls: baseWalls,
          rooms: baseRooms,
          leakSources: [],
          damageZones: [
            { id: 2, damage_type: "fire_hazard", severity: "warning", polygon: [{ x: 200, y: 150 }, { x: 360, y: 150 }, { x: 360, y: 260 }, { x: 200, y: 260 }], room_id: 3 }
          ]
        };
      case "pipeline":
        return {
          walls: baseWalls,
          rooms: baseRooms.map(r => r.id === 2 ? { ...r, kind: "shaft" } : r),
          leakSources: [
            { point: { x: 300, y: 90 }, room_id: 2, description: "PS 排水立管継手部" }
          ],
          damageZones: []
        };
      default:
        return {
          walls: baseWalls,
          rooms: baseRooms,
          leakSources: [],
          damageZones: []
        };
    }
  };

  const current3DData = get3DDataByHudTab();

  return (
    <div className="min-h-screen bg-[#030306] text-white p-2 md:p-4 font-sans select-none overflow-x-hidden relative">
      
      {/* 1. 백그라운드 웅장한 네온 오라 조명 소스 (Spaceship HUD Backdrop Aurora) */}
      <div className="absolute top-1/4 left-1/12 w-[350px] h-[350px] rounded-full bg-blue-600/10 blur-[130px] pointer-events-none animate-pulse"></div>
      <div className="absolute bottom-1/3 right-1/10 w-[550px] h-[550px] rounded-full bg-purple-600/5 blur-[160px] pointer-events-none"></div>
      <div className="absolute top-1/2 left-1/3 w-[300px] h-[300px] rounded-full bg-orange-500/5 blur-[110px] pointer-events-none"></div>

      {/* 백그라운드 매트릭스 격자 라인 효과 */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#0f172a_1px,transparent_1px),linear-gradient(to_bottom,#0f172a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-35 pointer-events-none"></div>

      {/* 최상단 미래형 HUD 헤더 바 */}
      <div className="w-full flex flex-col md:flex-row justify-between items-center bg-neutral-950/50 backdrop-blur-3xl border border-neutral-800/40 rounded-3xl px-6 py-4 mb-6 shadow-2xl relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 via-transparent to-transparent pointer-events-none"></div>
        
        {/* 코너 데코레이터 */}
        <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-blue-500/60"></div>
        <div className="absolute top-0 right-0 w-2 h-2 border-t border-r border-blue-500/60"></div>
        <div className="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-blue-500/60"></div>
        <div className="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-blue-500/60"></div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-3.5 h-3.5 rounded-full bg-blue-500 animate-ping absolute inset-0"></div>
            <div className="w-3.5 h-3.5 rounded-full bg-blue-400 relative border border-white/20"></div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-black tracking-widest text-neutral-300 uppercase font-mono">Japanbuild-BIM3D compliance</h1>
              <span className="text-[8px] bg-blue-500/20 border border-blue-500/40 text-blue-400 px-1.5 py-0.5 rounded font-mono">RADAR ACTIVE</span>
            </div>
            <p className="text-xs text-blue-400 font-medium">BIM確認申請 & 適合性自動検証システム v1.5.0</p>
          </div>
        </div>
        
        {/* 현장 매핑 실시간 날씨 & 통신 상태 메타정보 */}
        <div className="flex items-center gap-6 mt-4 md:mt-0 text-xs font-mono text-neutral-400">
          <div className="flex flex-col items-end">
            <span className="text-[9px] text-neutral-600 block">SECURE BACKBONE</span>
            <span className="text-emerald-400 font-bold tracking-widest flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              SECURE ACCESS
            </span>
          </div>
          <div className="h-8 w-[1px] bg-neutral-800/60"></div>
          <div className="flex flex-col items-end">
            <span className="text-[9px] text-neutral-600 block">TENANT WORKSPACE</span>
            <span className="text-white font-black tracking-wider">{session?.company_name || "ギルポン建設株式会社"}</span>
          </div>
        </div>
      </div>

      {/* 메인 HUD 대시보드 그리드 */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4 relative z-10">
        
        {/* 1. LEFT PANEL (좌측 HUD 계측기) */}
        <div className="xl:col-span-1 space-y-4 flex flex-col justify-between">
          
          {/* A. 48% 메인 다이얼 속도계 */}
          <div className="bg-neutral-950/50 backdrop-blur-3xl border border-neutral-800/40 shadow-[0_0_30px_rgba(59,130,246,0.02)] hover:border-blue-500/30 hover:shadow-[0_0_40px_rgba(59,130,246,0.05)] transition-all duration-500 rounded-3xl p-5 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent pointer-events-none"></div>
            
            {/* 코너 데코 */}
            <div className="absolute top-2 left-2 text-neutral-700 font-mono text-[7px] select-none">[SEC-01]</div>
            <div className="absolute top-2 right-2 text-neutral-700 font-mono text-[7px] select-none">[+]</div>

            <div className="flex justify-between items-center mb-3 mt-1">
              <span className="text-[10px] font-black text-blue-500 tracking-widest uppercase font-mono">法規適合率 / GENERAL SPEC</span>
              <Gauge className="w-4 h-4 text-blue-400" />
            </div>
            
            <div className="flex flex-col items-center justify-center py-4 relative">
              {/* SVG 네온 원형 계측기 */}
              <svg className="w-36 h-36 transform -rotate-90 filter drop-shadow-[0_0_12px_rgba(59,130,246,0.35)]">
                <circle cx="72" cy="72" r="60" stroke="#0a0f26" strokeWidth="6" fill="transparent" />
                <circle 
                  cx="72" 
                  cy="72" 
                  r="60" 
                  stroke="url(#neonBlueGradient)" 
                  strokeWidth="8" 
                  fill="transparent" 
                  strokeDasharray={376.8}
                  strokeDashoffset={376.8 * (1 - 0.48)}
                  strokeLinecap="round"
                  className="transition-all duration-1000 ease-out"
                />
                <defs>
                  <linearGradient id="neonBlueGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#00d2ff" stopOpacity="1" />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.8" />
                  </linearGradient>
                </defs>
              </svg>
              
              <div className="absolute flex flex-col items-center justify-center">
                <span className="text-4xl font-black text-white tracking-tighter font-mono">48<span className="text-xl text-blue-400 font-bold">%</span></span>
                <span className="text-[9px] text-neutral-400 tracking-wider font-mono font-bold mt-0.5">採光・天井高適合</span>
              </div>
            </div>
            
            <div className="mt-2 text-center bg-orange-950/20 border border-orange-500/20 rounded-xl py-1.5 px-3">
              <p className="text-[10px] text-neutral-300 font-mono">
                2F 特定区画 採光率第28条 <span className="text-orange-400 font-bold animate-pulse">要調整警告</span>
              </p>
            </div>
          </div>

          {/* B. 층별 건축 기준법 적합도 바 게이지 */}
          <div className="bg-neutral-950/50 backdrop-blur-3xl border border-neutral-800/40 shadow-[0_0_30px_rgba(59,130,246,0.02)] hover:border-purple-500/30 hover:shadow-[0_0_40px_rgba(168,85,247,0.05)] transition-all duration-500 rounded-3xl p-5 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent pointer-events-none"></div>
            
            <div className="absolute top-2 left-2 text-neutral-700 font-mono text-[7px] select-none">[SEC-02]</div>
            <div className="absolute top-2 right-2 text-neutral-700 font-mono text-[7px] select-none">[-]</div>

            <div className="flex justify-between items-center mb-4 mt-1">
              <span className="text-[10px] font-black text-neutral-300 tracking-widest uppercase font-mono">階層別適合度 / FLOOR STATUS</span>
              <Layers className="w-4 h-4 text-purple-400" />
            </div>

            <div className="space-y-3.5 font-mono text-xs">
              <div className="space-y-1">
                <div className="flex justify-between text-[10px]">
                  <span className="text-neutral-300 font-bold">RF (屋上区画)</span>
                  <span className="text-blue-400 font-extrabold">95%</span>
                </div>
                <div className="w-full h-2 bg-neutral-900/60 rounded-full overflow-hidden border border-neutral-800/30">
                  <div className="h-full bg-blue-500 rounded-full shadow-[0_0_8px_rgba(59,130,246,0.6)]" style={{ width: "95%" }}></div>
                </div>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-[10px]">
                  <span className="text-neutral-300 font-bold">3F (一般事務室)</span>
                  <span className="text-blue-400 font-extrabold">85%</span>
                </div>
                <div className="w-full h-2 bg-neutral-900/60 rounded-full overflow-hidden border border-neutral-800/30">
                  <div className="h-full bg-blue-500 rounded-full shadow-[0_0_8px_rgba(59,130,246,0.6)]" style={{ width: "85%" }}></div>
                </div>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-[10px]">
                  <span className="text-orange-400 font-extrabold">2F (住居・検格区域)</span>
                  <span className="text-orange-400 font-extrabold">48%</span>
                </div>
                <div className="w-full h-2 bg-neutral-900/60 rounded-full overflow-hidden border border-neutral-800/30">
                  <div className="h-full bg-gradient-to-r from-orange-500 to-orange-400 rounded-full shadow-[0_0_8px_rgba(249,115,22,0.6)]" style={{ width: "48%" }}></div>
                </div>
              </div>
            </div>
          </div>

          {/* C. 3중 소형 도넛 서클 */}
          <div className="bg-neutral-950/50 backdrop-blur-3xl border border-neutral-800/40 shadow-[0_0_30px_rgba(59,130,246,0.02)] hover:border-emerald-500/30 hover:shadow-[0_0_40px_rgba(16,185,129,0.05)] transition-all duration-500 rounded-3xl p-5 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent pointer-events-none"></div>
            
            <div className="absolute top-2 left-2 text-neutral-700 font-mono text-[7px] select-none">[DIAG]</div>
            <div className="absolute top-2 right-2 text-neutral-700 font-mono text-[7px] select-none">[+]</div>

            <div className="flex justify-between items-center mb-4 mt-1">
              <span className="text-[10px] font-black text-neutral-300 tracking-widest uppercase font-mono">3重適合パラメータ / DIAGNOSTICS</span>
              <Cpu className="w-4 h-4 text-emerald-400" />
            </div>

            <div className="grid grid-cols-3 gap-2 py-1 text-center">
              <div className="flex flex-col items-center">
                <div className="relative w-12 h-12 flex items-center justify-center filter drop-shadow-[0_0_6px_rgba(59,130,246,0.4)]">
                  <svg className="w-12 h-12 transform -rotate-90">
                    <circle cx="24" cy="24" r="20" stroke="#060c24" strokeWidth="3" fill="transparent" />
                    <circle cx="24" cy="24" r="20" stroke="#00d2ff" strokeWidth="3.5" fill="transparent" strokeDasharray={125.6} strokeDashoffset={125.6 * (1 - 0.78)} />
                  </svg>
                  <span className="absolute text-[9px] font-bold font-mono">78%</span>
                </div>
                <span className="text-[8px] text-neutral-400 mt-2 block font-mono font-bold">採光割合</span>
              </div>

              <div className="flex flex-col items-center">
                <div className="relative w-12 h-12 flex items-center justify-center filter drop-shadow-[0_0_6px_rgba(168,85,247,0.4)]">
                  <svg className="w-12 h-12 transform -rotate-90">
                    <circle cx="24" cy="24" r="20" stroke="#120624" strokeWidth="3" fill="transparent" />
                    <circle cx="24" cy="24" r="20" stroke="#a855f7" strokeWidth="3.5" fill="transparent" strokeDasharray={125.6} strokeDashoffset={125.6 * (1 - 0.88)} />
                  </svg>
                  <span className="absolute text-[9px] font-bold font-mono">88%</span>
                </div>
                <span className="text-[8px] text-neutral-400 mt-2 block font-mono font-bold">天井高</span>
              </div>

              <div className="flex flex-col items-center">
                <div className="relative w-12 h-12 flex items-center justify-center filter drop-shadow-[0_0_6px_rgba(239,68,68,0.4)]">
                  <svg className="w-12 h-12 transform -rotate-90">
                    <circle cx="24" cy="24" r="20" stroke="#240606" strokeWidth="3" fill="transparent" />
                    <circle cx="24" cy="24" r="20" stroke="#ef4444" strokeWidth="3.5" fill="transparent" strokeDasharray={125.6} strokeDashoffset={125.6 * (1 - 0.35)} />
                  </svg>
                  <span className="absolute text-[9px] font-bold text-red-400 font-mono">35%</span>
                </div>
                <span className="text-[8px] text-neutral-400 mt-2 block font-mono font-bold">漏水耐性</span>
              </div>
            </div>
          </div>

          {/* D. 균열 분산 기하학 분산 노드 맵 (Scatter Node Map) */}
          <div className="bg-neutral-950/50 backdrop-blur-3xl border border-neutral-800/40 shadow-[0_0_30px_rgba(59,130,246,0.02)] hover:border-orange-500/30 hover:shadow-[0_0_40px_rgba(249,115,22,0.05)] transition-all duration-500 rounded-3xl p-5 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-transparent pointer-events-none"></div>
            
            <div className="absolute top-2 left-2 text-neutral-700 font-mono text-[7px] select-none">[SCATTER]</div>
            <div className="absolute top-2 right-2 text-neutral-700 font-mono text-[7px] select-none">[^]</div>

            <div className="flex justify-between items-center mb-3 mt-1">
              <span className="text-[10px] font-black text-neutral-300 tracking-widest uppercase font-mono">構造クラック分散 / GEOMETRY SCATTER</span>
              <Compass className="w-4 h-4 text-orange-400" />
            </div>

            <div className="relative w-full h-24 bg-neutral-950/80 border border-neutral-800/30 rounded-2xl overflow-hidden shadow-inner">
              <svg className="w-full h-full">
                <line x1="10" y1="20" x2="60" y2="40" stroke="#1b253b" strokeWidth="1" />
                <line x1="60" y1="40" x2="110" y2="30" stroke="#1b253b" strokeWidth="1" />
                <line x1="110" y1="30" x2="160" y2="70" stroke="#1b253b" strokeWidth="1" />
                <line x1="60" y1="40" x2="80" y2="80" stroke="#1b253b" strokeWidth="1" />
                <line x1="80" y1="80" x2="160" y2="70" stroke="#1b253b" strokeWidth="1" />
                
                <circle cx="10" cy="20" r="3" fill="#00d2ff" />
                <circle cx="60" cy="40" r="4" fill="#a855f7" className="animate-pulse" />
                <circle cx="110" cy="30" r="3" fill="#00d2ff" />
                <circle cx="160" cy="70" r="5" fill="#ef4444" className="animate-ping" />
                <circle cx="160" cy="70" r="3.5" fill="#ef4444" />
                <circle cx="80" cy="80" r="3" fill="#ffaa00" />
                <circle cx="130" cy="50" r="2.5" fill="#00d2ff" />
              </svg>
              <div className="absolute bottom-2 right-2 px-1.5 py-0.5 bg-neutral-900/90 text-[8px] font-mono text-neutral-400 rounded border border-neutral-800/40">
                SWEEP SWIFT
              </div>
            </div>
          </div>

        </div>

        {/* 2. CENTER PANEL (중앙 대시보드 3D 씬 HUD 메인) */}
        <div className="xl:col-span-2 space-y-4 flex flex-col justify-between">
          
          <div className="bg-neutral-950/60 backdrop-blur-3xl border border-neutral-800/40 rounded-3xl p-4 relative overflow-hidden flex flex-col justify-between flex-grow shadow-2xl">
            <div className="absolute inset-0 bg-gradient-to-t from-blue-500/5 to-transparent pointer-events-none"></div>
            
            {/* 3D 모니터 정보 오버레이 헤더 */}
            <div className="flex justify-between items-center mb-3 bg-neutral-950/80 px-4 py-2.5 rounded-xl border border-neutral-900/70 shadow-lg">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse"></span>
                <span className="text-xs font-mono text-neutral-300">ACTIVE SCENE: <span className="text-blue-400 font-black tracking-wider">TOKYO-AOYAMA-MOCK-201</span></span>
              </div>
              
              {/* 층수 오버레이 탭선택 */}
              <div className="flex gap-1.5">
                {["RF", "3F", "2F", "1F"].map(fl => (
                  <button 
                    key={fl}
                    onClick={() => setSelectedFloor(fl)}
                    className={`px-3 py-1 font-mono text-[10px] font-black rounded-lg transition-all cursor-pointer ${selectedFloor === fl ? "bg-blue-600 text-white shadow-lg shadow-blue-500/30 border border-blue-400/40" : "bg-neutral-900 text-neutral-400 hover:text-neutral-200 border border-neutral-800/30"}`}
                  >
                    {fl}
                  </button>
                ))}
              </div>
            </div>

            {/* 3D WebGL 빌딩 뷰어 마운트 (Three.js 이식 완료) */}
            <div className="relative w-full h-[450px] md:h-[500px] flex-grow rounded-2xl overflow-hidden border border-neutral-900/80 shadow-2xl">
              <ThreeDViewer 
                walls={current3DData.walls}
                rooms={current3DData.rooms}
                leakSources={current3DData.leakSources}
                damageZones={current3DData.damageZones}
                isLoading={false}
                hudTab={hudTab}
                selectedFloor={selectedFloor}
              />
            </div>

            {/* 하단 미래형 HUD 렌더링 필터 탭 (스크린샷 버튼 매핑) */}
            <div className="grid grid-cols-3 md:grid-cols-6 gap-2 mt-4">
              {[
                { id: "summary", label: "模型概要", desc: "基本モデル" },
                { id: "geology", label: "地質特性", desc: "地盤構造" },
                { id: "inspect", label: "中間検査", desc: "漏水診断" },
                { id: "construction", label: "墨出し/施工", desc: "精密図面" },
                { id: "fire", label: "消防系統", desc: "防犯防災" },
                { id: "pipeline", label: "設備管路", desc: "設備PS" }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setHudTab(tab.id as any)}
                  className={`px-2 py-3 rounded-2xl border font-bold text-[10px] tracking-wider transition-all flex flex-col items-center justify-center gap-1 cursor-pointer shadow-md ${hudTab === tab.id ? "bg-blue-600/10 border-blue-500 text-blue-400 shadow-[0_0_20px_rgba(59,130,246,0.15)]" : "bg-neutral-950/60 border-neutral-900 text-neutral-500 hover:text-neutral-300 hover:border-neutral-800"}`}
                >
                  <span className="font-extrabold">{tab.label}</span>
                  <span className="text-[8px] opacity-40 font-mono font-bold block">{tab.desc}</span>
                </button>
              ))}
            </div>

          </div>

        </div>

        {/* 3. RIGHT PANEL (우측 HUD 지표 & 가이드) */}
        <div className="xl:col-span-1 space-y-4 flex flex-col justify-between">
          
          {/* A. 98 / 58 더블 서클 계측기 */}
          <div className="bg-neutral-950/50 backdrop-blur-3xl border border-neutral-800/40 shadow-[0_0_30px_rgba(59,130,246,0.02)] hover:border-blue-500/30 hover:shadow-[0_0_40px_rgba(59,130,246,0.05)] transition-all duration-500 rounded-3xl p-5 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent pointer-events-none"></div>
            
            <div className="absolute top-2 left-2 text-neutral-700 font-mono text-[7px] select-none">[STATISTICS]</div>
            <div className="absolute top-2 right-2 text-neutral-700 font-mono text-[7px] select-none">[+]</div>

            <div className="flex justify-between items-center mb-4 mt-1">
              <span className="text-[10px] font-black text-neutral-300 tracking-widest uppercase font-mono">今日解析統計 / DAILY INSPECTS</span>
              <TrendingUp className="w-4 h-4 text-blue-400" />
            </div>

            <div className="grid grid-cols-2 gap-4 py-2">
              <div className="flex flex-col items-center border-r border-neutral-850">
                <div className="relative w-16 h-16 flex items-center justify-center filter drop-shadow-[0_0_8px_rgba(59,130,246,0.4)]">
                  <svg className="w-16 h-16 transform -rotate-90">
                    <circle cx="32" cy="32" r="26" stroke="#060c24" strokeWidth="4" fill="transparent" />
                    <circle cx="32" cy="32" r="26" stroke="#00d2ff" strokeWidth="4.5" fill="transparent" strokeDasharray={163.2} strokeDashoffset={163.2 * (1 - 0.98)} />
                  </svg>
                  <span className="absolute text-base font-black text-white font-mono">98</span>
                </div>
                <span className="text-[9px] text-neutral-500 mt-2 font-mono font-bold">総解析図面数</span>
              </div>

              <div className="flex flex-col items-center">
                <div className="relative w-16 h-16 flex items-center justify-center filter drop-shadow-[0_0_8px_rgba(245,158,11,0.4)]">
                  <svg className="w-16 h-16 transform -rotate-90">
                    <circle cx="32" cy="32" r="26" stroke="#241706" strokeWidth="4" fill="transparent" />
                    <circle cx="32" cy="32" r="26" stroke="#ffaa00" strokeWidth="4.5" fill="transparent" strokeDasharray={163.2} strokeDashoffset={163.2 * (1 - 0.58)} />
                  </svg>
                  <span className="absolute text-base font-black text-orange-400 font-mono">58<span className="text-[10px] font-bold">%</span></span>
                </div>
                <span className="text-[9px] text-neutral-500 mt-2 font-mono font-bold">平均適合率</span>
              </div>
            </div>
          </div>

          {/* B. 실시간 로드 / 트래픽 추세 선 차트 */}
          <div className="bg-neutral-950/50 backdrop-blur-3xl border border-neutral-800/40 shadow-[0_0_30px_rgba(59,130,246,0.02)] hover:border-blue-500/30 hover:shadow-[0_0_40px_rgba(59,130,246,0.05)] transition-all duration-500 rounded-3xl p-5 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent pointer-events-none"></div>
            
            <div className="absolute top-2 left-2 text-neutral-700 font-mono text-[7px] select-none">[NET-SYS]</div>
            <div className="absolute top-2 right-2 text-neutral-700 font-mono text-[7px] select-none">[-]</div>

            <div className="flex justify-between items-center mb-3 mt-1">
              <span className="text-[10px] font-black text-neutral-300 tracking-widest uppercase font-mono font-bold">サーバー同期トラフィック / DYNAMIC TRAFFIC</span>
              <Activity className="w-4 h-4 text-blue-400" />
            </div>

            <div className="relative w-full h-24 bg-neutral-950/80 border border-neutral-800/30 rounded-2xl overflow-hidden shadow-inner">
              <svg className="w-full h-full">
                <defs>
                  <linearGradient id="neonLineGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00d2ff" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#00d2ff" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path d="M 0,90 Q 30,50 60,70 T 120,40 T 180,20 T 240,60 L 240,100 L 0,100 Z" fill="url(#neonLineGradient)" />
                <path d="M 0,90 Q 30,50 60,70 T 120,40 T 180,20 T 240,60" fill="transparent" stroke="#00d2ff" strokeWidth="2.5" className="filter drop-shadow-[0_0_4px_#00d2ff]" />
                
                <line x1="0" y1="25" x2="240" y2="25" stroke="#12182c" strokeDasharray="3,3" />
                <line x1="0" y1="50" x2="240" y2="50" stroke="#12182c" strokeDasharray="3,3" />
                <line x1="0" y1="75" x2="240" y2="75" stroke="#12182c" strokeDasharray="3,3" />
              </svg>
              <div className="absolute top-2 left-2 px-1.5 py-0.5 bg-neutral-900/95 text-[8px] font-mono text-emerald-400 rounded-lg border border-emerald-500/20 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
                <span>SYNC OK (23ms)</span>
              </div>
            </div>
          </div>

          {/* C. 1급 건축사 날인 서명 인장 상태 */}
          <div className="bg-neutral-950/50 backdrop-blur-3xl border border-neutral-800/40 shadow-[0_0_30px_rgba(59,130,246,0.02)] hover:border-emerald-500/30 hover:shadow-[0_0_40px_rgba(16,185,129,0.05)] transition-all duration-500 rounded-3xl p-5 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent pointer-events-none"></div>
            
            <div className="absolute top-2 left-2 text-neutral-700 font-mono text-[7px] select-none">[CERTIFICATE]</div>
            <div className="absolute top-2 right-2 text-neutral-700 font-mono text-[7px] select-none">[+]</div>

            <div className="flex justify-between items-center mb-4 mt-1">
              <span className="text-[10px] font-black text-neutral-300 tracking-widest uppercase font-mono">設計者自己検格署名 / ARCHITECT INKAN</span>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>

            <div className="flex items-center gap-4 bg-neutral-950/80 p-3 rounded-2xl border border-neutral-800/40 shadow-md">
              <div className="w-12 h-12 rounded-full border border-red-500/40 flex items-center justify-center bg-red-950/10 shrink-0 shadow-lg">
                <div className="w-9 h-9 rounded-full border-2 border-red-500 flex flex-col items-center justify-center p-0.5 select-none font-bold text-[7px] text-red-500 filter drop-shadow-[0_0_2px_rgba(239,68,68,0.5)]">
                  <span className="text-[5px]">一級建築士</span>
                  <span>吉本</span>
                </div>
              </div>
              <div className="space-y-1">
                <h4 className="text-xs font-bold text-white">一級建築士 免許対照完了</h4>
                <p className="text-[10px] text-neutral-500 leading-normal font-sans">
                  免許番号: 国土交通省第376592号<br/>
                  認可官庁提出効力 有効化済
                </p>
              </div>
            </div>
          </div>

          {/* D. 남은 크레딧 (2,313 Credit) HUD 잔액 패널 */}
          <div className="bg-neutral-950/50 backdrop-blur-3xl border border-neutral-800/40 shadow-[0_0_30px_rgba(59,130,246,0.02)] hover:border-amber-500/30 hover:shadow-[0_0_40px_rgba(245,158,11,0.05)] transition-all duration-500 rounded-3xl p-5 relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 to-transparent pointer-events-none"></div>
            
            <div className="absolute top-2 left-2 text-neutral-700 font-mono text-[7px] select-none">[WALLET]</div>
            <div className="absolute top-2 right-2 text-neutral-700 font-mono text-[7px] select-none">[$]</div>

            <div className="flex justify-between items-center mb-3 mt-1">
              <span className="text-[10px] font-black text-neutral-300 tracking-widest uppercase font-mono">保有ライセンスクレジット / WALLET CREDIT</span>
              <Zap className="w-4 h-4 text-amber-400" />
            </div>

            <div className="flex justify-between items-end bg-neutral-950/80 border border-neutral-800/40 p-4 rounded-2xl shadow-inner">
              <div>
                <span className="text-[9px] font-bold text-neutral-600 block">TOTAL CREDITS AVAILABLE</span>
                <span className="text-3xl font-black text-white font-mono filter drop-shadow-[0_0_4px_rgba(255,255,255,0.2)]">2,313</span>
              </div>
              <span className="text-xs font-bold px-2.5 py-1 bg-amber-500/10 text-amber-400 rounded-lg border border-amber-500/20 shadow-md">
                PRO PLAN
              </span>
            </div>
          </div>

        </div>

      </div>

      {/* 4. BOTTOM AREA (새 모델 업로드 2D PDF Drag & Drop 섹션 - HUD 스타일) */}
      <div className="mt-8 relative z-10 max-w-6xl mx-auto">
        <div className="bg-neutral-950/50 backdrop-blur-3xl border border-neutral-800/40 rounded-3xl p-8 relative overflow-hidden shadow-2xl">
          <div className="absolute inset-0 bg-gradient-to-r from-blue-500/5 to-transparent pointer-events-none"></div>
          
          <div 
            className={`border border-dashed rounded-3xl p-10 flex flex-col items-center justify-center text-center transition-all duration-300 relative overflow-hidden ${
              isDragging 
                ? "border-blue-500 bg-blue-500/5 scale-[1.01]" 
                : "border-neutral-800/50 bg-neutral-950/50 hover:border-neutral-700 hover:bg-neutral-950/80"
            }`}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleFileUpload(e.dataTransfer.files[0]);
              }
            }}
          >
            <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-500/5 via-transparent to-transparent opacity-0 transition-opacity duration-500" style={{ opacity: isDragging ? 1 : 0 }}></div>
            
            {isUploading ? (
              <div className="flex flex-col items-center py-6">
                <RefreshCw className="w-10 h-10 text-blue-400 animate-spin mb-4" />
                <h3 className="text-lg font-bold text-white mb-2">BIM 3D 자동 변환 진행 중...</h3>
                <p className="text-xs text-blue-400 font-mono tracking-widest uppercase">{uploadProgress}</p>
              </div>
            ) : (
              <>
                <div className={`p-5 bg-neutral-950 rounded-full mb-4 shadow-2xl border border-neutral-800/60 transition-transform duration-300 ${isDragging ? "scale-110 text-blue-400 border-blue-500" : "text-neutral-500"}`}>
                  <UploadCloud className="w-10 h-10" />
                </div>
                
                <h3 className="text-xl font-bold text-white mb-2">2D竣工図面 PDFアップロード & 3D IFC復元</h3>
                <p className="text-xs text-neutral-400 max-w-md mx-auto mb-6 font-sans">
                  国土交通省(MLIT) 竣工図書提出規格를 완전 준수. 2D PDF를 드래그&드롭하거나 업로드하여 AI 기하 복원 및 법규 준수 검증을 가동하십시오.
                </p>
                
                <label className="relative overflow-hidden group cursor-pointer">
                  <input 
                    type="file" 
                    className="hidden" 
                    accept=".pdf" 
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleFileUpload(e.target.files[0]);
                      }
                    }}
                  />
                  <div className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded-xl shadow-lg hover:shadow-blue-500/20 transition-all flex items-center gap-2 border border-blue-400/30">
                    <span>新規ファイル参照 (Browse PDF)</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </div>
                </label>
                <p className="mt-4 text-[10px] text-neutral-600 font-mono">
                  Supports .pdf (max 50MB) | 🟢 3D IFC 変換: 3 Credits | 🔥 適合性報告書(PDF)発行: 10 Credits
                </p>
              </>
            )}
          </div>

        </div>
      </div>

    </div>
  );
}
