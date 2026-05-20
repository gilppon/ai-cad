"use client";

import { useEffect, useRef, useState } from "react";
import { Box as BoxIcon, Loader2 } from "lucide-react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

interface Point3D {
  x: number;
  y: number;
  z?: number;
}

interface WallData {
  id: number;
  p1: Point3D;
  p2: Point3D;
  thickness_px?: number;
  kind?: string;
}

interface RoomData {
  id: number;
  polygon: Point3D[];
  kind?: string;
  area_m2?: number;
  height_mm?: number;
}

interface LeakSourceData {
  point: Point3D;
  room_id?: number;
  description?: string;
  confidence?: number;
}

interface DamageZoneData {
  id: number;
  damage_type: string;
  severity: string;
  polygon: Point3D[];
  room_id?: number;
}

interface ThreeDViewerProps {
  walls?: WallData[];
  rooms?: RoomData[];
  leakSources?: LeakSourceData[];
  damageZones?: DamageZoneData[];
  isLoading?: boolean;
  hudTab?: "summary" | "geology" | "inspect" | "construction" | "fire" | "pipeline";
  selectedFloor?: string;
}

export default function ThreeDViewer({
  walls = [],
  rooms = [],
  leakSources = [],
  damageZones = [],
  isLoading = false,
  hudTab = "summary",
  selectedFloor = "2F",
}: ThreeDViewerProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [rendererLoaded, setRendererLoaded] = useState(false);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);

  // 3D 씬 내의 2F 핵심 타겟 위치 트래킹용
  const [pinPos, setPinPos] = useState<{ x: number; y: number } | null>(null);
  const target3DPos = useRef<THREE.Vector3>(new THREE.Vector3(80, 22, -15));
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);

  // 네온 배리어 & 오렌지 스캔 밴드 애니메이션용 레퍼런스
  const barrierRef = useRef<THREE.Mesh | null>(null);
  const scanBandRef = useRef<THREE.Mesh | null>(null);
  const scanWireRef = useRef<THREE.LineSegments | null>(null);
  const innerEquipmentsRef = useRef<THREE.Group | null>(null);

  useEffect(() => {
    if (!mountRef.current) return;

    const width = mountRef.current.clientWidth || 600;
    const height = mountRef.current.clientHeight || 450;

    // 1. Scene, Camera, Renderer 초기 설정 + 딥스페이스 포그 안개(Fog)
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x04040a); 
    scene.fog = new THREE.FogExp2(0x04040a, 0.0032); // 웅장한 기화식 깊이 묘사 안개
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, width / height, 1, 2000);
    camera.position.set(240, 200, 320); // 영화적 대각선 앵글
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    
    mountRef.current.innerHTML = "";
    mountRef.current.appendChild(renderer.domElement);

    // 2. 조명 조절 (사이버네틱 네온 반사 극대화)
    const ambientLight = new THREE.AmbientLight(0x0e153b, 1.8); // 풍부한 푸른빛 베이스 광
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 2.0); // 주광
    dirLight.position.set(150, 300, 100);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    dirLight.shadow.bias = -0.001;
    scene.add(dirLight);

    // 미래형 네온 포인트 라이트 쌍
    const neonBlueLight = new THREE.PointLight(0x00d2ff, 4, 300);
    neonBlueLight.position.set(60, 60, 60);
    scene.add(neonBlueLight);

    const neonOrangeLight = new THREE.PointLight(0xffaa00, 3, 200);
    neonOrangeLight.position.set(-60, 30, -60);
    scene.add(neonOrangeLight);

    // 3. 극상의 3D 메탈릭 반사 바닥판 (Metal Plate Floor)
    const floorGeo = new THREE.BoxGeometry(600, 2, 500);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x090a16,
      roughness: 0.15,
      metalness: 0.95,
    });
    const floorMesh = new THREE.Mesh(floorGeo, floorMat);
    floorMesh.position.y = -1.5;
    floorMesh.receiveShadow = true;
    scene.add(floorMesh);

    // 3.1. 메탈릭 바닥판 위의 세련된 네온 블루 격자판
    const gridHelper = new THREE.GridHelper(500, 50, 0x1e3a8a, 0x0f172a); 
    gridHelper.position.y = -0.4;
    scene.add(gridHelper);

    // 4. Orbit Controls (카메라 제어)
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 - 0.05; 
    controlsRef.current = controls;

    const createdObjects: THREE.Object3D[] = [];
    const SCALE = 0.22; 
    const OFFSET_X = 200; 
    const OFFSET_Z = 150;

    // A. 지면 바운더리 네온 펜스 장막 (Neon Aura Barrier Wall) 생성
    const fenceColor = hudTab === "geology" ? 0xff7700 : hudTab === "inspect" ? 0xff0055 : 0x00d2ff;
    const fenceMat = new THREE.LineBasicMaterial({ color: fenceColor, linewidth: 2 });
    
    const minX = -130, maxX = 130;
    const minZ = -110, maxZ = 110;
    
    // 바닥/공중 네온 링
    const bottomPoints = [
      new THREE.Vector3(minX, 0, minZ),
      new THREE.Vector3(maxX, 0, minZ),
      new THREE.Vector3(maxX, 0, maxZ),
      new THREE.Vector3(minX, 0, maxZ),
      new THREE.Vector3(minX, 0, minZ)
    ];
    const bottomGeom = new THREE.BufferGeometry().setFromPoints(bottomPoints);
    const bottomLine = new THREE.Line(bottomGeom, fenceMat);
    scene.add(bottomLine);
    createdObjects.push(bottomLine);

    const topPoints = bottomPoints.map(p => new THREE.Vector3(p.x, 20, p.z));
    const topGeom = new THREE.BufferGeometry().setFromPoints(topPoints);
    const topLine = new THREE.Line(topGeom, fenceMat);
    scene.add(topLine);
    createdObjects.push(topLine);

    // 모서리 사이버네틱 빔 4개
    const corners = [
      { x: minX, z: minZ }, { x: maxX, z: minZ },
      { x: maxX, z: maxZ }, { x: minX, z: maxZ }
    ];
    corners.forEach(c => {
      const colGeom = new THREE.CylinderGeometry(1.0, 1.0, 20, 8);
      const colMat = new THREE.MeshStandardMaterial({
        color: fenceColor,
        emissive: fenceColor,
        emissiveIntensity: 0.6,
        roughness: 0.1,
        metalness: 0.9,
        transparent: true,
        opacity: 0.8
      });
      const colMesh = new THREE.Mesh(colGeom, colMat);
      colMesh.position.set(c.x, 10, c.z);
      scene.add(colMesh);
      createdObjects.push(colMesh);
    });

    // 반투명 3D 홀로그램 배리어 장막 메쉬 세우기 (애니메이션 펄싱 대상)
    const barrierGeo = new THREE.BoxGeometry(260, 20, 220);
    const barrierMaterial = new THREE.MeshBasicMaterial({
      color: fenceColor,
      transparent: true,
      opacity: 0.12,
      side: THREE.DoubleSide
    });
    const barrierMesh = new THREE.Mesh(barrierGeo, barrierMaterial);
    barrierMesh.position.y = 10;
    scene.add(barrierMesh);
    barrierRef.current = barrierMesh;
    createdObjects.push(barrierMesh);

    // B. 초정밀 하이테크 건물 (수학적 촘촘한 창문 프레임 벽체) 동적 빌드 함수
    const buildCyberneticWall = (p1x: number, p1z: number, p2x: number, p2z: number, wallHeight: number, thickness: number, opacity: number, colorVal: number) => {
      const wallGroup = new THREE.Group();
      
      const dx = p2x - p1x;
      const dz = p2z - p1z;
      const length = Math.sqrt(dx * dx + dz * dz);
      if (length < 0.1) return wallGroup;

      const angle = -Math.atan2(dz, dx) + Math.PI / 2;

      // 층 단위 설정 (일반 45 높이는 3개 층, 지질 25 높이는 2개 층)
      const numFloors = wallHeight > 30 ? 3 : 2;
      const floorH = wallHeight / numFloors;
      
      // 메탈릭 뼈대 프레임 재질
      const frameMat = new THREE.MeshStandardMaterial({
        color: 0x111c30, // 다크 티타늄 메탈릭 프레임
        roughness: 0.2,
        metalness: 0.9,
      });

      // 반투명 네온 블루 글래스 창문 재질
      const glassMat = new THREE.MeshStandardMaterial({
        color: 0x00f0ff,
        emissive: 0x00a0ff,
        emissiveIntensity: 0.15,
        transparent: true,
        opacity: opacity,
        roughness: 0.1,
        metalness: 0.95,
      });

      // 먹매김 시공 모드(wireframe) 대응
      if (hudTab === "construction") {
        frameMat.wireframe = true;
        glassMat.wireframe = true;
        glassMat.opacity = 0.15;
      }

      // 층별 촘촘한 기둥 및 가로 보 조립 루프
      for (let f = 0; f < numFloors; f++) {
        const floorY = f * floorH + floorH / 2;
        
        // 1) 층간 슬래브 보 (가로 보)
        const slabGeo = new THREE.BoxGeometry(thickness + 0.4, 0.8, length);
        const slab = new THREE.Mesh(slabGeo, frameMat);
        slab.position.set(0, f * floorH, 0);
        wallGroup.add(slab);

        // 2) 촘촘한 세로 창문 기둥 (Column) 배치
        const colSpacing = 8.0; // 8단위 간격으로 조밀 배치
        const numCols = Math.max(2, Math.floor(length / colSpacing));
        
        for (let i = 0; i <= numCols; i++) {
          const colZ = -length / 2 + (length / numCols) * i;
          const colGeo = new THREE.CylinderGeometry(thickness / 2 + 0.1, thickness / 2 + 0.1, floorH, 8);
          const col = new THREE.Mesh(colGeo, frameMat);
          col.position.set(0, floorY, colZ);
          wallGroup.add(col);
        }

        // 3) 기둥과 기둥 사이 반투명 글래스 창문 조각들 삽입 (정밀 X-Ray 밀도)
        for (let i = 0; i < numCols; i++) {
          const wCenterZ = -length / 2 + (length / numCols) * (i + 0.5);
          const wWidth = (length / numCols) - 1.2; // 틈새 확보
          
          const glassGeo = new THREE.BoxGeometry(thickness - 0.2, floorH - 1.2, wWidth);
          const glass = new THREE.Mesh(glassGeo, glassMat);
          glass.position.set(0, floorY, wCenterZ);
          wallGroup.add(glass);

          // 소형 수평 윈도우 프레임 보강선
          const trimGeo = new THREE.BoxGeometry(thickness + 0.1, 0.3, wWidth);
          const trim = new THREE.Mesh(trimGeo, frameMat);
          trim.position.set(0, floorY, wCenterZ);
          wallGroup.add(trim);
        }
      }

      // 옥상 마감 보
      const roofSlabGeo = new THREE.BoxGeometry(thickness + 0.4, 1.0, length);
      const roofSlab = new THREE.Mesh(roofSlabGeo, frameMat);
      roofSlab.position.set(0, wallHeight, 0);
      wallGroup.add(roofSlab);

      // 월드 좌표 배치 및 회전
      wallGroup.position.set((p1x + p2x) / 2, 0, (p1z + p2z) / 2);
      wallGroup.rotation.y = angle;

      return wallGroup;
    };

    // Walls 리스트 돌면서 수학적 정밀 팩토리 빌딩 세우기
    walls.forEach((wall) => {
      const p1x = (wall.p1.x - OFFSET_X) * SCALE;
      const p1z = (wall.p1.y - OFFSET_Z) * SCALE;
      const p2x = (wall.p2.x - OFFSET_X) * SCALE;
      const p2z = (wall.p2.y - OFFSET_Z) * SCALE;

      const thickness = (wall.thickness_px || 10.0) * SCALE * (hudTab === "construction" ? 0.5 : 1.3);
      const wallHeight = hudTab === "geology" ? 22 : 45; 

      let wallOpacity = 0.55;
      let wallColor = 0x223355; 
      
      if (hudTab === "inspect") {
        wallOpacity = 0.18; // 엑스레이 극대화를 위한 극도의 투시
        wallColor = 0x112244;
      } else if (hudTab === "construction") {
        wallOpacity = 0.65;
        wallColor = 0x334466;
      }

      const wallMeshGroup = buildCyberneticWall(p1x, p1z, p2x, p2z, wallHeight, thickness, wallOpacity, wallColor);
      scene.add(wallMeshGroup);
      createdObjects.push(wallMeshGroup);
    });

    // C. 방 바닥 (Rooms) 생성 (반투명 격자 오버레이)
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

      let color = 0x08162f; 
      if (room.kind === "toilet") color = 0x0066aa; 
      else if (room.kind === "shaft") color = 0xaa4400; 
      else if (room.kind === "kitchen") color = 0x008877; 
      else if (room.kind === "bedroom") color = 0x223355;
      else if (room.kind === "ldk") color = 0x0b255e; 

      const extrudeSettings = { depth: 1.5, bevelEnabled: false };
      const geom = new THREE.ExtrudeGeometry(shape, extrudeSettings);
      const mat = new THREE.MeshStandardMaterial({
        color: color,
        roughness: 0.15,
        metalness: 0.8,
        transparent: true,
        opacity: hudTab === "inspect" ? 0.25 : 0.6,
      });

      const mesh = new THREE.Mesh(geom, mat);
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.y = 0.4;
      mesh.receiveShadow = true;
      scene.add(mesh);
      createdObjects.push(mesh);
    });

    // D. X-Ray 내부 정비 장치 그룹 (X-Ray 복잡성 밀도 극대화)
    const innerEquipments = new THREE.Group();
    innerEquipmentsRef.current = innerEquipments;
    scene.add(innerEquipments);
    createdObjects.push(innerEquipments);

    // 복잡도 묘사용 모형 서버 랙, 메탈릭 원형 탱크 촘촘히 묘사
    const renderInnerMachinery = () => {
      // 1) 고밀도 서버 랙 뭉치들 배치 (에너지 글로우 핀 포함)
      const rackPositions = [
        { x: -50, z: -20, h: 18, floor: 0 },
        { x: -30, z: -20, h: 18, floor: 0 },
        { x: -10, z: -20, h: 18, floor: 0 },
        { x: 30, z: 20, h: 16, floor: 1 },
        { x: 50, z: 20, h: 16, floor: 1 },
      ];

      rackPositions.forEach((pos, idx) => {
        const floorY = pos.floor * 15 + 0.6;
        const rackGeo = new THREE.BoxGeometry(6, pos.h, 6);
        const rackMat = new THREE.MeshStandardMaterial({
          color: 0x111c30,
          roughness: 0.25,
          metalness: 0.95
        });
        const rack = new THREE.Mesh(rackGeo, rackMat);
        rack.position.set(pos.x, floorY + pos.h / 2, pos.z);
        innerEquipments.add(rack);

        // 정면 전광판 네온 펄스 도트 라인
        const ledGeo = new THREE.BoxGeometry(0.1, pos.h - 2, 4.5);
        const ledColor = idx % 2 === 0 ? 0x00ff66 : 0xff3300;
        const ledMat = new THREE.MeshBasicMaterial({
          color: ledColor,
          transparent: true,
          opacity: 0.95
        });
        const led = new THREE.Mesh(ledGeo, ledMat);
        led.position.set(pos.x + 3.05, floorY + pos.h / 2, pos.z);
        innerEquipments.add(led);
      });

      // 2) 가로형/세로형 대형 메탈릭 실린더 오일 탱크
      const tankSpecs = [
        { x: -70, y: 1, z: 40, r: 5.5, h: 12, rotateX: false },
        { x: -70, y: 15, z: 40, r: 4.0, h: 10, rotateX: true },
        { x: 80, y: 1, z: -40, r: 6.0, h: 14, rotateX: false }
      ];

      tankSpecs.forEach(spec => {
        const tGeo = new THREE.CylinderGeometry(spec.r, spec.r, spec.h, 16);
        const tMat = new THREE.MeshStandardMaterial({
          color: 0x2e3b52,
          roughness: 0.1,
          metalness: 0.9
        });
        const tank = new THREE.Mesh(tGeo, tMat);
        tank.position.set(spec.x, spec.y + spec.h / 2, spec.z);
        if (spec.rotateX) {
          tank.rotation.x = Math.PI / 2;
        }
        innerEquipments.add(tank);

        // 탱크 보강 띠 (네온 오라)
        const ringGeo = new THREE.CylinderGeometry(spec.r + 0.15, spec.r + 0.15, 0.8, 16);
        const ringMat = new THREE.MeshBasicMaterial({ color: 0x00d2ff });
        const ring1 = new THREE.Mesh(ringGeo, ringMat);
        ring1.position.set(spec.x, spec.y + spec.h / 3, spec.z);
        if (spec.rotateX) ring1.rotation.x = Math.PI / 2;
        innerEquipments.add(ring1);
      });
    };

    // 엑스레이 밀도를 위해 모든 모드에서 기계장비 배치하되 모드별 가시성 제어
    renderInnerMachinery();

    // E. 6대 HUD 탭별 테마 맞춤 3D 메쉬 동적 생성
    
    // 1) GEOLOGY (지질 특성) -> 지반 보강용 파일 및 3단 복합 지층 블록 생성
    if (hudTab === "geology") {
      const pileCoordinates = [
        { x: -65, z: -55 }, { x: 65, z: -55 },
        { x: -65, z: 55 }, { x: 65, z: 55 },
        { x: -25, z: -25 }, { x: 25, z: -25 },
        { x: -25, z: 25 }, { x: 25, z: 25 }
      ];
      
      pileCoordinates.forEach(pile => {
        const pileGeom = new THREE.CylinderGeometry(2.5, 1.8, 45, 12);
        const pileMat = new THREE.MeshStandardMaterial({
          color: 0xffaa00,
          emissive: 0xff7700,
          emissiveIntensity: 0.65,
          roughness: 0.2,
          metalness: 0.95
        });
        const pileMesh = new THREE.Mesh(pileGeom, pileMat);
        pileMesh.position.set(pile.x, -22.5, pile.z);
        scene.add(pileMesh);
        createdObjects.push(pileMesh);
      });

      const layers = [
        { color: 0x483a2e, depth: -10, height: 10 },
        { color: 0x2f2e2d, depth: -20, height: 10 },
        { color: 0x141f1d, depth: -35, height: 20 }
      ];

      layers.forEach(layer => {
        const blockGeom = new THREE.BoxGeometry(240, layer.height, 200);
        const blockMat = new THREE.MeshStandardMaterial({
          color: layer.color,
          transparent: true,
          opacity: 0.5,
          roughness: 0.85,
          metalness: 0.2
        });
        const blockMesh = new THREE.Mesh(blockGeom, blockMat);
        blockMesh.position.set(0, layer.depth - layer.height / 2, 0);
        scene.add(blockMesh);
        createdObjects.push(blockMesh);
      });
    }

    // 2) INSPECT (중간 검사) -> 누수 배관 누설 원천 핀 및 사이버네틱 아웃라인
    if (hudTab === "inspect") {
      leakSources.forEach((ls) => {
        const lx = (ls.point.x - OFFSET_X) * SCALE;
        const lz = (ls.point.y - OFFSET_Z) * SCALE;
        const ly = 32;

        // 3D 핑크 네온 물방울 핀
        const geom = new THREE.SphereGeometry(6, 24, 24);
        const mat = new THREE.MeshStandardMaterial({
          color: 0xff0055,
          emissive: 0xff0055,
          emissiveIntensity: 1.2,
          roughness: 0.05,
          metalness: 0.95
        });
        const sphere = new THREE.Mesh(geom, mat);
        sphere.position.set(lx, ly, lz);
        scene.add(sphere);
        createdObjects.push(sphere);

        // 핑크 네온 얇은 파이프
        const pipeGeom = new THREE.CylinderGeometry(1.2, 1.2, 75, 12);
        pipeGeom.rotateZ(Math.PI / 2);
        const pipeMat = new THREE.MeshStandardMaterial({
          color: 0xff0055,
          emissive: 0xff0055,
          emissiveIntensity: 0.8,
        });
        const pipe = new THREE.Mesh(pipeGeom, pipeMat);
        pipe.position.set(lx, ly + 2.5, lz);
        scene.add(pipe);
        createdObjects.push(pipe);

        // 낙수 사이버 광선 기둥
        const dropGeom = new THREE.CylinderGeometry(0.3, 1.2, ly, 16);
        const dropMat = new THREE.MeshBasicMaterial({
          color: 0x00d2ff,
          transparent: true,
          opacity: 0.8
        });
        const drop = new THREE.Mesh(dropGeom, dropMat);
        drop.position.set(lx, ly / 2, lz);
        scene.add(drop);
        createdObjects.push(drop);
      });

      // 바닥 피해 존에 세련된 네온 핑크 아웃라인 및 격자망
      damageZones.forEach((dz) => {
        if (!dz.polygon || dz.polygon.length < 3) return;
        
        const points = dz.polygon.map(pt => new THREE.Vector3((pt.x - OFFSET_X) * SCALE, 0.8, -(pt.y - OFFSET_Z) * SCALE));
        points.push(points[0]); 
        
        const lineGeom = new THREE.BufferGeometry().setFromPoints(points);
        const lineMat = new THREE.LineBasicMaterial({ color: 0xff0055, linewidth: 3 });
        const outline = new THREE.Line(lineGeom, lineMat);
        scene.add(outline);
        createdObjects.push(outline);
      });
    }

    // 3) CONSTRUCTION (먹매김 시공) -> 네온 그린 레이저 가이드 삼각망
    if (hudTab === "construction") {
      const laserColor = 0x00ff66;
      const laserMat = new THREE.LineDashedMaterial({
        color: laserColor,
        dashSize: 5,
        gapSize: 2.5,
      });

      const points1 = [new THREE.Vector3(-110, 22, -90), new THREE.Vector3(110, 22, 90)];
      const geom1 = new THREE.BufferGeometry().setFromPoints(points1);
      const line1 = new THREE.Line(geom1, laserMat);
      line1.computeLineDistances();
      scene.add(line1);
      createdObjects.push(line1);

      const points2 = [new THREE.Vector3(-110, 22, 90), new THREE.Vector3(110, 22, -90)];
      const geom2 = new THREE.BufferGeometry().setFromPoints(points2);
      const line2 = new THREE.Line(geom2, laserMat);
      line2.computeLineDistances();
      scene.add(line2);
      createdObjects.push(line2);

      const targetPoints = [
        { x: -55, y: 0, z: -35 },
        { x: 65, y: 0, z: 25 },
        { x: 15, y: 0, z: 75 }
      ];
      targetPoints.forEach(p => {
        const coneGeom = new THREE.ConeGeometry(3.5, 9, 12);
        coneGeom.rotateX(Math.PI);
        const coneMat = new THREE.MeshBasicMaterial({ color: laserColor });
        const cone = new THREE.Mesh(coneGeom, coneMat);
        cone.position.set(p.x, 16, p.z);
        scene.add(cone);
        createdObjects.push(cone);

        const linePts = [new THREE.Vector3(p.x, 16, p.z), new THREE.Vector3(p.x, 0.8, p.z)];
        const lineGeom = new THREE.BufferGeometry().setFromPoints(linePts);
        const line = new THREE.Line(lineGeom, new THREE.LineDashedMaterial({ color: laserColor, dashSize: 2, gapSize: 1 }));
        line.computeLineDistances();
        scene.add(line);
        createdObjects.push(line);
      });
    }

    // 4) FIRE (소방 계통) -> 소방 구획 강조 및 경보 비콘
    if (hudTab === "fire") {
      const firewallGeom = new THREE.BoxGeometry(8, 42, 85);
      const firewallMat = new THREE.MeshStandardMaterial({
        color: 0xff3300,
        emissive: 0xff3300,
        emissiveIntensity: 0.75,
        transparent: true,
        opacity: 0.45
      });
      const firewall = new THREE.Mesh(firewallGeom, firewallMat);
      firewall.position.set(38, 21, 20);
      scene.add(firewall);
      createdObjects.push(firewall);

      const sprinklerPos = [
        { x: -45, z: -45 }, { x: 5, z: -45 },
        { x: -45, z: 25 }, { x: 5, z: 25 }
      ];
      sprinklerPos.forEach(sp => {
        const nodeGeom = new THREE.SphereGeometry(2.5, 12, 12);
        const nodeMat = new THREE.MeshBasicMaterial({ color: 0xff5500 });
        const mesh = new THREE.Mesh(nodeGeom, nodeMat);
        mesh.position.set(sp.x, 42, sp.z);
        scene.add(mesh);
        createdObjects.push(mesh);

        const ringGeom = new THREE.RingGeometry(10, 12, 32);
        const ringMat = new THREE.MeshBasicMaterial({ color: 0xff3300, side: THREE.DoubleSide, transparent: true, opacity: 0.65 });
        const ring = new THREE.Mesh(ringGeom, ringMat);
        ring.rotation.x = Math.PI / 2;
        ring.position.set(sp.x, 0.8, sp.z);
        scene.add(ring);
        createdObjects.push(ring);
      });
    }

    // 5) PIPELINE (설비 관로) -> 3D 실린더형 네온 관로망
    if (hudTab === "pipeline") {
      const pipeSpecs = [
        { points: [new THREE.Vector3(-105, 12, -55), new THREE.Vector3(85, 12, -55), new THREE.Vector3(85, 36, -55), new THREE.Vector3(85, 36, 65)], color: 0x00d2ff, radius: 2.5 },
        { points: [new THREE.Vector3(-105, 18, -48), new THREE.Vector3(80, 18, -48), new THREE.Vector3(80, 31, -48), new THREE.Vector3(80, 31, 58)], color: 0xff2a44, radius: 2.0 },
        { points: [new THREE.Vector3(-45, 0.8, 35), new THREE.Vector3(-45, 45, 35)], color: 0xff7700, radius: 3.8 }
      ];

      pipeSpecs.forEach(spec => {
        for (let i = 0; i < spec.points.length - 1; i++) {
          const p1 = spec.points[i];
          const p2 = spec.points[i + 1];
          const distance = p1.distanceTo(p2);
          
          const cylinderGeom = new THREE.CylinderGeometry(spec.radius, spec.radius, distance, 12);
          const cylinderMat = new THREE.MeshStandardMaterial({
            color: spec.color,
            emissive: spec.color,
            emissiveIntensity: 0.6,
            roughness: 0.15,
            metalness: 0.95
          });
          const pipeSegment = new THREE.Mesh(cylinderGeom, cylinderMat);
          pipeSegment.position.copy(p1).add(p2).multiplyScalar(0.5);
          
          const direction = new THREE.Vector3().subVectors(p2, p1).normalize();
          const alignAxis = new THREE.Vector3(0, 1, 0);
          const quaternion = new THREE.Quaternion().setFromUnitVectors(alignAxis, direction);
          pipeSegment.setRotationFromQuaternion(quaternion);
          
          scene.add(pipeSegment);
          createdObjects.push(pipeSegment);
        }
      });
    }

    // F. 2F 층별 오렌지/블루 더블 스캔 밴드 (Selected Floor Aura)
    if (selectedFloor === "2F") {
      const glowColor = 0xff7700;
      const glowMat = new THREE.MeshBasicMaterial({
        color: glowColor,
        transparent: true,
        opacity: 0.38,
        side: THREE.DoubleSide
      });

      const bandWidth = 245;
      const bandDepth = 205;
      const bandHeight = 7.5;
      const bandY = 22.5; 

      const bandGeom = new THREE.BoxGeometry(bandWidth + 12, bandHeight, bandDepth + 12);
      const edges = new THREE.EdgesGeometry(bandGeom);
      const lineMat = new THREE.LineBasicMaterial({ color: glowColor, linewidth: 3 });
      
      const glowWireframe = new THREE.LineSegments(edges, lineMat);
      glowWireframe.position.set(0, bandY, 0);
      scene.add(glowWireframe);
      scanWireRef.current = glowWireframe;
      createdObjects.push(glowWireframe);

      const glowMesh = new THREE.Mesh(bandGeom, glowMat);
      glowMesh.position.set(0, bandY, 0);
      scene.add(glowMesh);
      scanBandRef.current = glowMesh;
      createdObjects.push(glowMesh);

      // 하단 네온 블루 서브 링 밴드
      const subBandGeom = new THREE.BoxGeometry(bandWidth + 18, 1.8, bandDepth + 18);
      const subGlowMat = new THREE.MeshBasicMaterial({ color: 0x00d2ff, transparent: true, opacity: 0.65 });
      const subGlowMesh = new THREE.Mesh(subBandGeom, subGlowMat);
      subGlowMesh.position.set(0, bandY - 11, 0);
      scene.add(subGlowMesh);
      createdObjects.push(subGlowMesh);
    }

    // 옥상 구조 데코레이션 (summary/geology 모드 고유 하이테크 데코)
    if (hudTab === "summary" || hudTab === "geology") {
      const heliGeom = new THREE.CylinderGeometry(25, 25, 2.5, 32);
      const heliMat = new THREE.MeshStandardMaterial({ color: 0x1a2942, roughness: 0.75, metalness: 0.8 });
      const heli = new THREE.Mesh(heliGeom, heliMat);
      heli.position.set(-35, 46.5, -25);
      scene.add(heli);
      createdObjects.push(heli);

      const stackGeom = new THREE.CylinderGeometry(4.5, 4.5, 14, 8);
      const stackMat = new THREE.MeshStandardMaterial({ color: 0x101a2d, metalness: 0.95 });
      const stack = new THREE.Mesh(stackGeom, stackMat);
      stack.position.set(55, 52, 45);
      scene.add(stack);
      createdObjects.push(stack);

      // 송신 철탑 (Wireframe Cone)
      const towerGeom = new THREE.ConeGeometry(6, 24, 6);
      const towerMat = new THREE.MeshStandardMaterial({ color: 0x00d2ff, wireframe: true });
      const tower = new THREE.Mesh(towerGeom, towerMat);
      tower.position.set(70, 57, -60);
      scene.add(tower);
      createdObjects.push(tower);
    }

    setRendererLoaded(true);

    // 6. Animation Loop (역동성 증진을 위한 펄스/스캐닝 연출)
    let animationFrameId: number;
    const tempV = new THREE.Vector3();
    const clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();
      
      controls.update();

      // A. 네온 장막 오라 펄싱 (Futuristic Aura Pulsing)
      if (barrierRef.current) {
        const mat = barrierRef.current.material as THREE.MeshBasicMaterial;
        mat.opacity = 0.08 + Math.sin(elapsedTime * 2.0) * 0.04;
      }

      // B. 2층 오렌지 스캔 밴드 왕복 스캐닝 (Scanning Motion)
      if (scanBandRef.current && scanWireRef.current) {
        const sweepY = 22.5 + Math.sin(elapsedTime * 2.5) * 3.5;
        scanBandRef.current.position.y = sweepY;
        scanWireRef.current.position.y = sweepY;
      }

      // C. X-Ray 기계실 내부 장비 LED 간헐성 브레싱 효과
      if (innerEquipmentsRef.current) {
        innerEquipmentsRef.current.children.forEach((child, idx) => {
          if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshBasicMaterial) {
            child.material.opacity = 0.5 + Math.sin(elapsedTime * 4.0 + idx) * 0.45;
          }
        });
      }
      
      // 3D 공간 상의 타겟 좌표를 2D 브라우저 픽셀 좌표로 변환하여 2F 플로팅 HUD 핀 동적 추적
      if (cameraRef.current && mountRef.current) {
        tempV.copy(target3DPos.current);
        tempV.project(cameraRef.current);
        
        const x = (tempV.x * 0.5 + 0.5) * width;
        const y = (tempV.y * -0.5 + 0.5) * height;
        
        if (tempV.z < 1) {
          setPinPos({ x, y });
        } else {
          setPinPos(null);
        }
      }

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!mountRef.current || !cameraRef.current) return;
      const w = mountRef.current.clientWidth;
      const h = mountRef.current.clientHeight;
      cameraRef.current.aspect = w / h;
      cameraRef.current.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    // 7. Cleanup
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", handleResize);
      
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
  }, [walls, rooms, leakSources, damageZones, hudTab, selectedFloor]);

  return (
    <div className="w-full h-full min-h-[480px] md:min-h-[520px] relative bg-[#040408] border border-neutral-900 rounded-3xl overflow-hidden shadow-2xl">
      {/* 3D Canvas Mount Point */}
      <div ref={mountRef} className="w-full h-full min-h-[480px] md:min-h-[520px] z-0" />

      {/* 로딩 인디케이터 */}
      {(isLoading || !rendererLoaded) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-neutral-950/90 backdrop-blur-md z-10 transition-opacity duration-300">
          <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
          <p className="text-blue-400 font-bold tracking-widest text-sm uppercase">3D CYBERNETIC SCENE BUILDING...</p>
          <p className="text-xs text-neutral-500 mt-1 font-mono">Loading WebGL Real-time Correction Engine</p>
        </div>
      )}

      {/* 우상단 조작 알림 HUD 스타일 */}
      <div className="absolute top-4 right-4 bg-neutral-950/80 backdrop-blur-md px-3.5 py-2 rounded-xl border border-neutral-900 text-[10px] font-mono text-neutral-400 flex items-center gap-2 select-none pointer-events-none z-10 shadow-2xl">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping"></span>
        <span className="text-blue-400 font-bold">DRAG TO ROTATE SCENE</span>
      </div>

      {/* 좌하단 설명 카드 HUD 스타일 */}
      <div className="absolute bottom-4 left-4 bg-neutral-950/85 backdrop-blur-xl px-5 py-4 rounded-2xl border border-neutral-950 shadow-2xl max-w-[280px] z-10 pointer-events-none">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <h4 className="text-xs font-black text-white tracking-widest uppercase font-mono">BIM-3D COMPLIANCE HUD</h4>
        </div>
        <p className="text-[10px] text-neutral-400 leading-relaxed font-sans">
          국토교통성(MLIT) 적합성 자동 검격 시뮬레이터. 마우스 휠로 줌인/줌아웃, 우클릭 드래그로 시점 이동이 가능합니다.
        </p>
      </div>

      {/* 2F 특정 강조 층 안내 라인 오버레이 (스크린샷 3층 완벽 매칭 플로팅 UI) */}
      {selectedFloor === "2F" && pinPos && (
        <div 
          className="absolute pointer-events-none select-none z-20 transition-all duration-75"
          style={{ 
            left: `${pinPos.x}px`, 
            top: `${pinPos.y}px` 
          }}
        >
          {/* 가상 레이저 커넥션 포인터 */}
          <div className="relative flex items-center">
            {/* 타겟 핀 원구 */}
            <div className="w-4 h-4 -ml-2 -mt-2 rounded-full border-2 border-orange-500 bg-orange-950/80 flex items-center justify-center animate-pulse">
              <div className="w-1.5 h-1.5 rounded-full bg-orange-500"></div>
            </div>
            
            {/* 우측으로 뻗어나가는 사선 레이저 지시선 */}
            <div className="absolute left-2 top-0 flex items-center">
              <svg width="100" height="40" className="overflow-visible">
                <line x1="0" y1="0" x2="60" y2="-15" stroke="#f97316" strokeWidth="1.5" strokeDasharray="3,2" />
                <line x1="60" y1="-15" x2="150" y2="-15" stroke="#f97316" strokeWidth="1.5" />
              </svg>
              
              {/* 플로팅 배지 */}
              <div 
                className="absolute bg-orange-950/95 border border-orange-500/80 backdrop-blur-md px-3 py-1.5 rounded-xl flex items-center gap-2 shadow-2xl whitespace-nowrap"
                style={{ transform: "translate(60px, -27px)" }}
              >
                <span className="w-2 h-2 rounded-full bg-orange-500 animate-ping"></span>
                <span className="text-[10px] font-black text-orange-400 font-mono tracking-widest uppercase">
                  2F 適合性要調整区画
                </span>
                <span className="text-[8px] text-neutral-400 font-mono border-l border-orange-500/40 pl-1.5">
                  #201 AREA
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
