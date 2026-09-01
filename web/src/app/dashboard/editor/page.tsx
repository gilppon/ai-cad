"use client";

import { useEffect, useState, useRef, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { 
  ArrowLeft, Save, MapPin, Layers, RefreshCw, 
  HelpCircle, AlertTriangle, ShieldCheck, CheckCircle2, ChevronRight,
  Loader2
} from "lucide-react";
import ThreeDViewer from "@/components/ThreeDViewer";
import { API_BASE_URL } from "@/utils/api";
import { getAuthHeaders } from "@/utils/apiAuth";

interface Point {
  x: number;
  y: number;
}

interface Wall {
  id: number;
  p1: Point;
  p2: Point;
  thickness_px: number;
  kind?: string;
}

interface Room {
  id: number;
  polygon: Point[];
  kind: string;
  area_m2: number;
}

interface LeakSource {
  point: Point;
  room_id?: number;
  description: string;
  compliance_opinion?: any;
}

interface DamageZone {
  id: number;
  damage_type: string;
  severity: string;
  polygon: Point[];
  room_id?: number;
}

function EditorContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  // SP6/P0-4: project_id는 필수. 없으면 Mock으로 대체하지 않고 즉시 오류를 노출한다.
  // (과거: 하드코딩된 가짜 프로젝트 ID 로 폴백 — 결제 고객에게 실존하지 않는 데모 도면이 표시되던 결함)
  const projectId = searchParams.get("project_id");

  // 상태 관리 (2D 도면 데이터 및 기하 상태)
  const [walls, setWalls] = useState<Wall[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [canvas, setCanvas] = useState<{ width: number; height: number }>({ width: 500, height: 400 });
  const [leakSources, setLeakSources] = useState<LeakSource[]>([]);
  const [damageZones, setDamageZones] = useState<DamageZone[]>([]);
  
  // 에디팅 도구 상태
  const [activeTool, setActiveTool] = useState<"select" | "leak_pin" | "damage_brush">("select");
  const [selectedRoom, setSelectedRoom] = useState<Room | null>(null);
  const [selectedWall, setSelectedWall] = useState<Wall | null>(null);
  const [draggedNode, setDraggedNode] = useState<{ wallId: number; endpoint: "p1" | "p2" } | null>(null);
  
  // 로딩 및 API 세션 상태
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [complianceOpinions, setComplianceOpinions] = useState<any[]>([]);

  // SP6/P0-5: 로드·저장 실패는 반드시 사용자에게 노출한다. 조용한 Mock 폴백은 금지.
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);

  // 1. 초기 프로젝트 데이터 로드 (실데이터 전용 — 폴백 없음)
  useEffect(() => {
    if (!projectId) {
      setIsLoading(false);
      setLoadError("project_id가 지정되지 않았습니다. 대시보드에서 프로젝트를 선택해 주십시오.");
      return;
    }

    let cancelled = false;

    async function loadProjectData() {
      setIsLoading(true);
      setLoadError(null);
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/projects/${projectId}/geometry`, {
          headers: await getAuthHeaders()
        });

        if (!res.ok) {
          const detail = res.status === 404
            ? "프로젝트를 찾을 수 없거나 접근 권한이 없습니다."
            : `서버가 도면 데이터를 반환하지 않았습니다 (HTTP ${res.status}).`;
          if (!cancelled) setLoadError(detail);
          return;
        }

        const data = await res.json();
        if (cancelled) return;

        // API 데이터 바인딩 — 빈 배열은 빈 도면으로 정직하게 렌더링한다.
        setWalls(data.walls || []);
        setRooms(data.rooms || []);
        setLeakSources(data.incident?.leak_sources || []);
        setDamageZones(data.incident?.damage_zones || []);
        setComplianceOpinions(data.incident?.compliance_opinions || []);
        if (data.canvas) {
          setCanvas(data.canvas);
        }
      } catch (err) {
        console.error("도면 데이터 로드 실패:", err);
        if (!cancelled) setLoadError("네트워크 오류로 도면 데이터를 불러오지 못했습니다.");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    loadProjectData();

    return () => { cancelled = true; };
  }, [projectId, reloadNonce]);

  // 2. 2D 도면 드래깅 및 상호작용 관련 마우스 핸들러
  const handleSvgMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    // 2D SVG 상의 클릭 이벤트를 통해 누수 핀 배치 모드 처리
    if (activeTool === "leak_pin") {
      const rect = e.currentTarget.getBoundingClientRect();
      const clickX = Math.round(e.clientX - rect.left);
      const clickY = Math.round(e.clientY - rect.top);

      // 어느 방에 꽂혔는지 판별
      let hitRoomId = undefined;
      for (const r of rooms) {
        // Simple bounding box hit test for MVP
        const xs = r.polygon.map(p => p.x);
        const ys = r.polygon.map(p => p.y);
        if (clickX >= Math.min(...xs) && clickX <= Math.max(...xs) &&
            clickY >= Math.min(...ys) && clickY <= Math.max(...ys)) {
          hitRoomId = r.id;
          break;
        }
      }

      const newLeak: LeakSource = {
        point: { x: clickX, y: clickY },
        room_id: hitRoomId,
        description: "수동 교정 에디터로 배치한 누수원"
      };

      setLeakSources([newLeak]); // 핀은 하나만 배치 가능하도록 덮어쓰기
      setActiveTool("select"); // 완료 후 선택 모드로 자동 전환

      // SP6/P0-4: 법적 소견은 백엔드(compliance 엔진)만 생성할 수 있다.
      // (과거: 클라이언트가 「マンション標準管理規約第7条」등을 하드코딩해 소견을 조작 —
      //  근거 없는 법적 판정을 고객에게 표시하던 중대 결함)
      // 핀 배치 시점에는 기존 소견을 무효화하고, 저장 후 백엔드 응답으로만 갱신한다.
      setComplianceOpinions([]);
    }
  };

  const handleNodeMouseDown = (wallId: number, endpoint: "p1" | "p2", e: React.MouseEvent) => {
    e.stopPropagation();
    setDraggedNode({ wallId, endpoint });
  };

  const handleSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!draggedNode) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const currentX = Math.round(e.clientX - rect.left);
    const currentY = Math.round(e.clientY - rect.top);

    // 실시간 드래깅 벽 이동 처리
    setWalls(prevWalls => prevWalls.map(w => {
      if (w.id === draggedNode.wallId) {
        return {
          ...w,
          [draggedNode.endpoint]: { x: currentX, y: currentY }
        };
      }
      return w;
    }));
  };

  const handleSvgMouseUp = () => {
    setDraggedNode(null);
  };

  // 3. 델타 패치 백엔드 동기화 및 3D 실시간 재빌드 전송
  const handleSaveCorrections = async () => {
    if (!projectId) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      const operations = [];
      
      // 1. 벽 이동 패치 수집
      walls.forEach(w => {
        operations.push({
          operation: "move_wall",
          params: { wall_id: w.id, new_p1: w.p1, new_p2: w.p2 },
          author: "web-operator"
        });
      });

      // 2. 누수 핀 패치 수집
      if (leakSources.length > 0) {
        operations.push({
          operation: "place_leak_source",
          params: {
            point: leakSources[0].point,
            room_id: leakSources[0].room_id,
            description: leakSources[0].description
          },
          author: "web-operator"
        });
      }

      const payload = {
        // SP6/P0-4: 과거 "LEAK-EDIT-2026" 상수 하드코딩 — 모든 교정이 동일 케이스로 기록되던 결함.
        case_id: `LEAK-${projectId}`,
        operations: operations
      };

      const res = await fetch(`${API_BASE_URL}/api/v1/projects/${projectId}/correction`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(await getAuthHeaders())
        },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const result = await res.json();
        // 법적 소견은 백엔드 응답으로만 표시한다. 응답에 없으면 "판정 불가"로 남긴다.
        setComplianceOpinions(result.compliance_opinions || []);
        setSaveError(null);
      } else {
        const detail = res.status === 404
          ? "프로젝트를 찾을 수 없거나 접근 권한이 없습니다."
          : `교정 적용에 실패했습니다 (HTTP ${res.status}).`;
        setSaveError(detail);
      }
    } catch (err) {
      console.error(err);
      setSaveError("네트워크 오류로 교정 패치를 저장하지 못했습니다.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white flex flex-col font-sans">
      {/* 상단 헤더 바 */}
      <header className="px-6 py-4 bg-neutral-900/60 backdrop-blur-md border-b border-neutral-800 flex justify-between items-center z-20">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => router.push("/dashboard")} 
            className="p-2 hover:bg-neutral-800 rounded-lg transition-colors text-neutral-400 hover:text-white"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-lg font-bold tracking-wide">Japanbuild-Leak3D Editor</h1>
            <p className="text-xs text-neutral-400">Project ID: {projectId}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSaveCorrections}
            disabled={isSaving}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-neutral-800 disabled:text-neutral-500 text-white text-sm font-semibold rounded-lg shadow-lg hover:shadow-blue-500/20 transition-all cursor-pointer"
          >
            {isSaving ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            <span>3D 실시간 재빌드 적용</span>
          </button>
        </div>
      </header>

      {/* SP6/P0-5: 저장 실패는 배너로 명시한다. (과거: alert() 토스트 + "서킷 브레이커 가동" 은폐 문구) */}
      {saveError && (
        <div className="mx-6 mt-4 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-xl flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="text-red-300 text-sm font-semibold">교정 적용 실패</p>
            <p className="text-red-400/80 text-xs mt-0.5">{saveError}</p>
          </div>
          <button
            onClick={() => setSaveError(null)}
            className="text-red-400/70 hover:text-red-300 text-xs cursor-pointer"
          >
            닫기
          </button>
        </div>
      )}

      {/* 메인 2D-3D 분할 에디터 캔버스 */}
      <main className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-2 gap-6 overflow-hidden">
        
        {/* 좌측 2D 도면 편집 패널 */}
        <section className="flex flex-col bg-neutral-900/40 border border-neutral-800 rounded-2xl overflow-hidden shadow-xl backdrop-blur-sm">
          {/* 에디팅 도구 툴바 */}
          <div className="px-4 py-3 bg-neutral-900 border-b border-neutral-800 flex justify-between items-center">
            <span className="text-xs font-bold text-neutral-400 tracking-wider">LEFT: 2D 평면 도면 교정</span>
            <div className="flex gap-2">
              <button 
                onClick={() => setActiveTool("select")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${activeTool === "select" ? "bg-blue-600 text-white" : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"}`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>벽/방 선택 조정</span>
              </button>
              <button 
                onClick={() => setActiveTool("leak_pin")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${activeTool === "leak_pin" ? "bg-red-600 text-white" : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"}`}
              >
                <MapPin className="w-3.5 h-3.5" />
                <span>누수 핀 지정</span>
              </button>
            </div>
          </div>

          {/* SVG 2D 평면 에디터 영역 */}
          <div className="flex-1 min-h-[450px] relative bg-neutral-950 flex items-center justify-center overflow-hidden">
            {isLoading ? (
              <div className="flex flex-col items-center">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin mb-3" />
                <p className="text-neutral-500 text-sm">2D 도면 분석 데이터 로드 중...</p>
              </div>
            ) : loadError ? (
              /* SP6/P0-5: 실패를 숨기지 않는다. 가짜 도면보다 빈 화면이 안전하다. */
              <div className="flex flex-col items-center text-center px-8 max-w-md">
                <AlertTriangle className="w-10 h-10 text-amber-500 mb-3" />
                <p className="text-amber-400 text-sm font-semibold mb-1">도면 데이터를 불러올 수 없습니다</p>
                <p className="text-neutral-500 text-xs leading-relaxed mb-4">{loadError}</p>
                <button
                  onClick={() => setReloadNonce(n => n + 1)}
                  className="flex items-center gap-2 px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>다시 시도</span>
                </button>
              </div>
            ) : (
              <svg 
                className="w-full h-full min-h-[450px] cursor-crosshair select-none"
                viewBox={`0 0 ${canvas.width} ${canvas.height}`}
                onMouseDown={handleSvgMouseDown}
                onMouseMove={handleSvgMouseMove}
                onMouseUp={handleSvgMouseUp}
                onMouseLeave={handleSvgMouseUp}
              >
                {/* 격자선 무늬 */}
                <defs>
                  <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                    <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#222" strokeWidth="0.5" />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" />

                {/* 1. 룸 폴리곤 오버레이 */}
                {rooms.map(room => {
                  const pointsStr = room.polygon.map(p => `${p.x},${p.y}`).join(" ");
                  let colorClass = "fill-neutral-500/10 stroke-neutral-500/40";
                  const k = room.kind?.toLowerCase();
                  if (k === "toilet" || k === "wet") colorClass = "fill-blue-500/20 stroke-blue-500/50";
                  else if (k === "shaft" || k === "pipe_space") colorClass = "fill-orange-500/20 stroke-orange-500/50";
                  else if (k === "ldk") colorClass = "fill-emerald-500/20 stroke-emerald-500/50 animate-pulse";
                  else if (k === "bedroom" || k === "room") colorClass = "fill-purple-500/20 stroke-purple-500/50";
                  else if (k === "corridor") colorClass = "fill-cyan-500/15 stroke-cyan-500/40";

                  return (
                    <polygon
                      key={room.id}
                      points={pointsStr}
                      className={`${colorClass} hover:fill-blue-500/30 transition-colors cursor-pointer`}
                      onClick={() => setSelectedRoom(room)}
                    />
                  );
                })}

                {/* 2. 벽체 오버레이 및 노드 조절 핸들 */}
                {walls.map(wall => (
                  <g key={wall.id}>
                    <line
                      x1={wall.p1.x}
                      y1={wall.p1.y}
                      x2={wall.p2.x}
                      y2={wall.p2.y}
                      stroke="#64748b"
                      strokeWidth={Math.max(5, wall.thickness_px || 5)}
                      className="hover:stroke-blue-500 transition-colors cursor-pointer"
                      onClick={() => setSelectedWall(wall)}
                    />
                    {/* 끝점 p1 마운트 노드 */}
                    <circle
                      cx={wall.p1.x}
                      cy={wall.p1.y}
                      r={6}
                      fill="#3b82f6"
                      className="cursor-pointer hover:scale-125 transition-transform"
                      onMouseDown={(e) => handleNodeMouseDown(wall.id, "p1", e)}
                    />
                    {/* 끝점 p2 마운트 노드 */}
                    <circle
                      cx={wall.p2.x}
                      cy={wall.p2.y}
                      r={6}
                      fill="#3b82f6"
                      className="cursor-pointer hover:scale-125 transition-transform"
                      onMouseDown={(e) => handleNodeMouseDown(wall.id, "p2", e)}
                    />
                  </g>
                ))}

                {/* 3. 누수 핀 시각화 */}
                {leakSources.map((ls, idx) => (
                  <g key={idx}>
                    <circle cx={ls.point.x} cy={ls.point.y} r={12} fill="#ef4444" fillOpacity="0.3" className="animate-ping" />
                    <circle cx={ls.point.x} cy={ls.point.y} r={6} fill="#ef4444" stroke="#fff" strokeWidth={2} />
                  </g>
                ))}
              </svg>
            )}
          </div>
        </section>

        {/* 우측 3D WebGL 실시간 뷰어 패널 */}
        <section className="flex flex-col bg-neutral-900/40 border border-neutral-800 rounded-2xl overflow-hidden shadow-xl backdrop-blur-sm">
          <div className="px-4 py-3 bg-neutral-900 border-b border-neutral-800 flex justify-between items-center">
            <span className="text-xs font-bold text-neutral-400 tracking-wider">RIGHT: 3D WebGL 실시간 입체 뷰</span>
          </div>

          <div className="flex-1 relative">
            <ThreeDViewer 
              walls={walls}
              rooms={rooms}
              leakSources={leakSources}
              damageZones={damageZones}
              isLoading={isLoading}
            />
          </div>
        </section>
      </main>

      {/* 하단 일본 주택법 누수 책임 판정 소견서 오버레이 패널 */}
      <footer className="mx-6 mb-6 p-5 bg-neutral-900/80 backdrop-blur-lg border border-neutral-800 rounded-2xl shadow-2xl flex flex-col md:flex-row justify-between gap-6 z-10">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2.5">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <h3 className="text-sm font-bold tracking-wider text-emerald-400 uppercase">일본 맨션 구분소유법 기준 책임 판정 소견서</h3>
          </div>
          
          {complianceOpinions.length > 0 ? (
            complianceOpinions.map((op, idx) => (
              <div key={idx} className="space-y-2">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="px-2.5 py-1 bg-emerald-500/10 text-emerald-400 rounded-md border border-emerald-500/20 text-xs font-bold">
                    판정: {op.decision_label}
                  </span>
                  <span className="text-xs text-neutral-400">
                    법적 근거: {op.legal_basis}
                  </span>
                  <span className="text-xs text-neutral-400">
                    공간 분류: {op.room_type_jp} ({op.room_abbr_jp})
                  </span>
                </div>
                <p className="text-sm text-neutral-300 leading-relaxed pl-1">
                  {op.japanese_opinion}
                </p>
              </div>
            ))
          ) : (
            <p className="text-sm text-neutral-500 pl-1 leading-relaxed">
              2D 도면상의 누수 의심 구역에 **[누수 핀]**을 배치해 주십시오. 
              구분소유법 및 맨션 표준규약 조항에 따른 전유부/공용부 하자와 법적 분쟁 소견이 이곳에 실시간 빌드됩니다.
            </p>
          )}
        </div>

        {/*
          SP6/P0-4: 과거 이 영역에 「실시간 3D 재빌드 속도 평균 1.8초 (상수 유지)」,
          「파싱 보정 성공률 100% (작업자 보정 보증)」, 「일본 소견 지침 완벽 충족」이
          하드코딩되어 있었다. 측정 근거가 없는 성능·적합 주장이며, 일본 경품표시법상
          우량오인(優良誤認) 소지가 있는 표시다. 실측값만 표시하도록 교체한다.
        */}
        <div className="md:w-72 flex flex-col justify-center border-t md:border-t-0 md:border-l border-neutral-800 pt-4 md:pt-0 md:pl-6 gap-2">
          <div className="flex justify-between items-center text-xs text-neutral-400">
            <span>인식된 공간</span>
            <span className="font-semibold text-neutral-200">{rooms.length}개</span>
          </div>
          <div className="flex justify-between items-center text-xs text-neutral-400">
            <span>인식된 벽체</span>
            <span className="font-semibold text-neutral-200">{walls.length}개</span>
          </div>
          <div className="flex justify-between items-center text-xs text-neutral-400">
            <span>소견 산출 주체</span>
            <span className="font-semibold text-neutral-200">
              {complianceOpinions.length > 0 ? "서버 컴플라이언스 엔진" : "미산출"}
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default function EditorPage() {
  return (
    <Suspense fallback={
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#030306] text-blue-400">
        <Loader2 className="w-10 h-10 animate-spin mb-4" />
        <p className="font-mono text-xs tracking-widest">LOADING SECURE EDITOR WORKSPACE...</p>
      </div>
    }>
      <EditorContent />
    </Suspense>
  );
}
