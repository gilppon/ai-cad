import React, { useMemo } from 'react';
import { Edges } from '@react-three/drei';

export interface ModelPart {
  type: 'box' | 'cylinder' | 'sphere';
  position: [number, number, number];
  size: [number, number, number];
  color?: string;
  name?: string;
}

interface DynamicModelProps {
  parts: ModelPart[];
}

export default function DynamicModel({ parts }: DynamicModelProps) {
  const renderedParts = useMemo(() => {
    return parts.map((part, index) => {
      const { type, position, size, color = '#4f46e5', name } = part;
      const partKey = `${name || type}-${index}-${position.join('_')}`;

      if (type === 'box') {
        return (
          <mesh key={partKey} position={position} castShadow receiveShadow>
            <boxGeometry args={size} />
            <meshStandardMaterial color={color} roughness={0.3} metalness={0.7} />
            <Edges scale={1.001} threshold={15} color="#1e1b4b" />
          </mesh>
        );
      }

      if (type === 'cylinder') {
        return (
          <mesh key={partKey} position={position} castShadow receiveShadow rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[size[0], size[1], size[2], 32]} />
            <meshStandardMaterial color={color} roughness={0.3} metalness={0.7} />
            <Edges scale={1.001} threshold={15} color="#1e1b4b" />
          </mesh>
        );
      }

      if (type === 'sphere') {
        return (
          <mesh key={partKey} position={position} castShadow receiveShadow>
            <sphereGeometry args={[size[0], size[1], size[2]]} />
            <meshStandardMaterial color={color} roughness={0.3} metalness={0.7} />
            <Edges scale={1.001} threshold={15} color="#1e1b4b" />
          </mesh>
        );
      }

      return null;
    });
  }, [parts]);

  return <group>{renderedParts}</group>;
}
