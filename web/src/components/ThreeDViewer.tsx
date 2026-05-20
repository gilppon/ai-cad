"use client";

import { useEffect, useRef, useState } from "react";
import { Box as BoxIcon, Loader2, RefreshCw } from "lucide-react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

interface Point3D {
  x: float;
  y: float;
  z?: float;
}

interface WallData {
  id: int;
  p1: Point3D;
  p2: Point3D;
  thickness_px?: float;
  kind?: string;
}

interface RoomData {
  id: int;
  polygon: Point3D[];
  kind?: string;
  area_m2?: float;
  height_mm?: float;
}

interface LeakSourceData {
  point: Point3D;
  room_id?: int;
  description?: string;
  confidence?: float;
}

interface DamageZoneData {
  id: int;
  damage_type: string;
  severity: string;
  polygon: Point3D[];
  room_id?: int;
}

interface ThreeDViewerProps {
  walls?: WallData[];
  rooms?: RoomData[];
  leakSources?: LeakSourceData[];
  damageZones?: DamageZoneData[];
  isLoading?: boolean;
}

export default function ThreeDViewer({
  walls = [],
  rooms = [],
  leakSources = [],
  damageZones = [],
  isLoading = false,
}: ThreeDViewerProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [rendererLoaded, setRendererLoaded] = useState(false);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);

  useEffect(() => {
    if (!mountRef.current) return;

    // 1. Scene, Camera, Renderer 초기 설정
    const width = mountRef.current.clientWidth || 600;
    const height = mountRef.current.clientHeight || 450;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x171717); // Sleek Dark Mode Background
    sceneRef.current = scene;

    // 원근 카메라 구성
    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 2000);
    camera.position.set(100, 250, 400);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    
    // 이전에 있던 자식 캔버스가 있다면 제거
    mountRef.current.innerHTML = "";
    mountRef.current.appendChild(renderer.domElement);

    // 2. 조명 조절 (조명의 고급 세팅으로 3D 입체감 극대화)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(200, 400, 200);
    dirLight.castShadow = true;
    scene.add(dirLight);

    const dirLight2 = new THREE.DirectionalLight(0x3b82f6, 0.3); // 푸른색 보조조명으로 미래지향적 감각 부여
    dirLight2.position.set(-200, -200, -200);
    scene.add(dirLight2);

    // 3. Grid Helper 및 바닥 판넬
    const gridHelper = new THREE.GridHelper(800, 80, 0x444444, 0x222222);
    gridHelper.position.y = -0.5;
    scene.add(gridHelper);

    // 4. Orbit Controls (마우스 드래그/줌인/줌아웃)
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 - 0.05; // 바닥 아래로 카메라가 못 내려가도록 제한
    controlsRef.current = controls;

    // 5. 3D 메쉬 생성 가동
    const createdObjects: THREE.Object3D[] = [];

    // Scale conversion: px 단위 도면 좌표를 3D 공간 스케일로 축소
    const SCALE = 0.2; 
    const OFFSET_X = 250; // 센터 이동 오프셋
    const OFFSET_Z = 250;

    // 5-1. 방 바닥 (Room Floors) 생성
    rooms.forEach((room) => {
      if (!room.polygon || room.polygon.length < 3) return;

      const shape = new THREE.Shape();
      const first = room.polygon[0];
      shape.moveTo((first.x - OFFSET_X) * SCALE, -(first.y - OFFSET_Z) * SCALE);

      for (let i = 1; i < room.polygon.length; i++) {
        const pt = room.polygon[i];
        shape.lineTo((pt.x - OFFSET_X) * SCALE, -(pt.y - OFFSET_Z) * SCALE);
      }
      shape.closePath();

      // 방의 종류에 따른Harmonious HSL 테마 컬러 설정
      let color = 0x2d3748; // 기본 그레이
      if (room.kind === "toilet") color = 0x3182ce; // 욕실/화장실 블루
      else if (room.kind === "shaft" || room.kind === "shaft") color = 0xdd6b20; // 샤프트 오렌지 (주의)
      else if (room.kind === "kitchen") color = 0x319795; // 주방 틸
      else if (room.kind === "bedroom") color = 0x4a5568; // 침실
      else if (room.kind === "ldk") color = 0x2c5282; // LDK 딥블루

      // ExtrudeGeometry를 사용해 방 바닥 판넬 두께 3px 생성
      const extrudeSettings = { depth: 3, bevelEnabled: false };
      const geom = new THREE.ExtrudeGeometry(shape, extrudeSettings);
      const mat = new THREE.MeshStandardMaterial({
        color: color,
        roughness: 0.4,
        metalness: 0.1,
      });

      const mesh = new THREE.Mesh(geom, mat);
      mesh.rotation.x = -Math.PI / 2; // 바닥 수평 눕히기
      mesh.position.y = 0;
      scene.add(mesh);
      createdObjects.push(mesh);
    });

    // 5-2. 벽체 (Walls) 입체 생성
    walls.forEach((wall) => {
      const p1x = (wall.p1.x - OFFSET_X) * SCALE;
      const p1z = (wall.p1.y - OFFSET_Z) * SCALE;
      const p2x = (wall.p2.x - OFFSET_X) * SCALE;
      const p2z = (wall.p2.y - OFFSET_Z) * SCALE;

      // 두 끝점 간의 벡터 계산
      const dx = p2x - p1x;
      const dz = p2z - p1z;
      const length = Math.sqrt(dx * dx + dz * dz);
      if (length < 0.1) return;

      const thickness = (wall.thickness_px || 10.0) * SCALE * 1.5;
      const wallHeight = 45; // 3D 벽체 높이

      // 벽 박스 메시 생성
      const geom = new THREE.BoxGeometry(thickness, wallHeight, length);
      const mat = new THREE.MeshStandardMaterial({
        color: 0x4a5568, // 정갈한 시멘트 그레이
        roughness: 0.9,
      });

      const mesh = new THREE.Mesh(geom, mat);

      // 벽 중심 위치 및 각도 조절
      mesh.position.set((p1x + p2x) / 2, wallHeight / 2, (p1z + p2z) / 2);
      mesh.rotation.y = -Math.atan2(dz, dx) + Math.PI / 2;

      scene.add(mesh);
      createdObjects.push(mesh);
    });

    // 5-3. 누수원 (Leak Sources) 3D 레드 핀 생성
    leakSources.forEach((ls) => {
      const lx = (ls.point.x - OFFSET_X) * SCALE;
      const lz = (ls.point.y - OFFSET_Z) * SCALE;
      const ly = 40; // 누수는 주로 천장/상부 배관이므로 상단 배치

      // 빨간색 구형 누수 핀
      const geom = new THREE.SphereGeometry(7, 16, 16);
      const mat = new THREE.MeshStandardMaterial({
        color: 0xef4444, // 강렬한 레드
        emissive: 0xef4444,
        emissiveIntensity: 0.6,
      });
      const sphere = new THREE.Mesh(geom, mat);
      sphere.position.set(lx, ly, lz);

      // 하부로 뻗는 핀 기둥
      const cylinderGeom = new THREE.CylinderGeometry(1, 1, ly, 8);
      const cylinderMat = new THREE.MeshBasicMaterial({ color: 0xef4444 });
      const cylinder = new THREE.Mesh(cylinderGeom, cylinderMat);
      cylinder.position.set(lx, ly / 2, lz);

      scene.add(sphere);
      scene.add(cylinder);
      createdObjects.push(sphere);
      createdObjects.push(cylinder);
    });

    // 5-4. 피해 지역 (Damage Zones) 반투명 브러시 오버레이
    damageZones.forEach((dz) => {
      if (!dz.polygon || dz.polygon.length < 3) return;

      const shape = new THREE.Shape();
      const first = dz.polygon[0];
      shape.moveTo((first.x - OFFSET_X) * SCALE, -(first.y - OFFSET_Z) * SCALE);

      for (let i = 1; i < dz.polygon.length; i++) {
        const pt = dz.polygon[i];
        shape.lineTo((pt.x - OFFSET_X) * SCALE, -(pt.y - OFFSET_Z) * SCALE);
      }
      shape.closePath();

      // 피해 심각도에 따른 반투명 오렌지/레드 평면
      const geom = new THREE.ShapeGeometry(shape);
      const mat = new THREE.MeshBasicMaterial({
        color: dz.severity === "critical" || dz.severity === "high" ? 0xef4444 : 0xf97316,
        transparent: true,
        opacity: 0.6,
        side: THREE.DoubleSide,
      });

      const mesh = new THREE.Mesh(geom, mat);
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.y = 1; // 바닥 바로 위 오버레이
      scene.add(mesh);
      createdObjects.push(mesh);
    });

    setRendererLoaded(true);

    // 6. Animation Loop (지연 방지 렌더링 프레임)
    let animationFrameId: number;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };

    animate();

    // 7. Cleanup 리소스 해제
    return () => {
      cancelAnimationFrame(animationFrameId);
      createdObjects.forEach((obj) => {
        scene.remove(obj);
        if (obj instanceof THREE.Mesh) {
          obj.geometry.dispose();
          if (Array.isArray(obj.material)) {
            obj.material.forEach((m) => m.dispose());
          } else {
            obj.material.dispose();
          }
        }
      });
      controls.dispose();
      renderer.dispose();
    };
  }, [walls, rooms, leakSources, damageZones]);

  return (
    <div className="w-full h-full min-h-[450px] relative bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden shadow-2xl">
      {/* 3D Canvas Mount Point */}
      <div ref={mountRef} className="w-full h-full min-h-[450px] z-0" />

      {/* 로딩 인디케이터 */}
      {(isLoading || !rendererLoaded) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-neutral-950/80 backdrop-blur-md z-10 transition-opacity duration-300">
          <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
          <p className="text-blue-400 font-semibold tracking-wide">3D WebGL 장면 빌드 중...</p>
          <p className="text-xs text-neutral-500 mt-1">경량 메시 인젝션 엔진 가동</p>
        </div>
      )}

      {/* 우상단 조작 알림 */}
      <div className="absolute top-4 right-4 bg-neutral-950/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-neutral-800 text-xs text-neutral-400 flex items-center gap-1.5 select-none pointer-events-none z-10">
        <RefreshCw className="w-3.5 h-3.5 animate-spin-slow text-blue-400" />
        <span>마우스 드래그로 회전 가능</span>
      </div>

      {/* 좌하단 설명 카드 */}
      <div className="absolute bottom-4 left-4 bg-neutral-950/90 backdrop-blur-lg px-4 py-3 rounded-xl border border-neutral-800 shadow-xl max-w-[240px] z-10 pointer-events-none">
        <div className="flex items-center gap-2 mb-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse" />
          <h4 className="text-sm font-semibold text-white tracking-wide">Japanbuild-Leak3D</h4>
        </div>
        <p className="text-xs text-neutral-400 leading-relaxed">
          실시간 2D 평면 보정이 반영된 고성능 WebGL 입체 설명 모델입니다.
        </p>
      </div>
    </div>
  );
}
