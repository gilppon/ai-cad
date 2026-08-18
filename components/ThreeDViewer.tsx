"use client";

import React, { useEffect, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, ContactShadows, Environment } from "@react-three/drei";
import * as THREE from "three";
import DynamicModel, { ModelPart } from "./DynamicModel";

interface ThreeDViewerProps {
  parts: ModelPart[];
  cameraPosition?: [number, number, number];
  autoRotate?: boolean;
}

/**
 * Recursively disposes of all Three.js geometries, materials, and textures
 * to prevent GPU/WebGL memory leaks on component unmount or state re-renders.
 */
function cleanupThreeScene(root: THREE.Object3D) {
  root.traverse((obj) => {
    if ((obj as THREE.Mesh).isMesh) {
      const mesh = obj as THREE.Mesh;
      if (mesh.geometry) {
        mesh.geometry.dispose();
      }
      if (mesh.material) {
        if (Array.isArray(mesh.material)) {
          mesh.material.forEach((mat) => {
            disposeMaterial(mat);
          });
        } else {
          disposeMaterial(mesh.material);
        }
      }
    }
  });
}

function disposeMaterial(mat: THREE.Material) {
  mat.dispose();
  // Dispose all associated textures
  for (const key of Object.keys(mat)) {
    const value = (mat as unknown as Record<string, unknown>)[key];
    if (value && typeof value === "object" && "isTexture" in value && (value as THREE.Texture).isTexture) {
      (value as THREE.Texture).dispose();
    }
  }
}

/**
 * Scene Manager with automatic WebGL memory cleanup lifecycle.
 */
function ManagedScene({ parts }: { parts: ModelPart[] }) {
  const sceneRef = useRef<THREE.Group>(null);

  useEffect(() => {
    const currentScene = sceneRef.current;
    return () => {
      if (currentScene) {
        cleanupThreeScene(currentScene);
      }
    };
  }, [parts]);

  return (
    <group ref={sceneRef}>
      <DynamicModel parts={parts} />
    </group>
  );
}

export default function ThreeDViewer({
  parts,
  cameraPosition = [0, 5, 10],
  autoRotate = false,
}: ThreeDViewerProps) {
  return (
    <div className="w-full h-full min-h-[400px] relative bg-slate-950 rounded-xl overflow-hidden shadow-2xl">
      <Canvas
        shadows
        camera={{ position: cameraPosition, fov: 45 }}
        gl={{
          antialias: true,
          powerPreference: "high-performance",
        }}
      >
        <ambientLight intensity={0.6} />
        <directionalLight
          position={[10, 15, 10]}
          intensity={1.2}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
        />
        <ManagedScene parts={parts} />
        <ContactShadows
          position={[0, -0.01, 0]}
          opacity={0.6}
          scale={20}
          blur={1.5}
          far={10}
        />
        <Environment preset="city" />
        <OrbitControls
          makeDefault
          autoRotate={autoRotate}
          autoRotateSpeed={0.8}
          maxPolarAngle={Math.PI / 2 - 0.05}
          minDistance={2}
          maxDistance={30}
        />
      </Canvas>
    </div>
  );
}
