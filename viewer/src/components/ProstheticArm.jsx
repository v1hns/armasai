import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Line, Html } from '@react-three/drei'
import * as THREE from 'three'

// ── Material factory ──────────────────────────────────────────────────────────
function useMaterials(params) {
  return useMemo(() => {
    const primary = params.primaryColor || '#0d1117'
    const accent = params.accentColor || '#00d4ff'
    const isCF = params.material === 'carbon_fiber'
    const isTi = params.material === 'titanium'

    return {
      body: {
        color: primary,
        roughness: isCF ? 0.15 : isTi ? 0.25 : 0.55,
        metalness: isCF ? 0.4 : isTi ? 0.85 : 0.1,
        envMapIntensity: 1.5,
      },
      joint: {
        color: accent,
        roughness: 0.08,
        metalness: 0.95,
        emissive: accent,
        emissiveIntensity: 0.12,
        envMapIntensity: 2.0,
      },
      socket: {
        color: '#1e1e2e',
        roughness: 0.35,
        metalness: 0.2,
      },
      grip: {
        color: '#111118',
        roughness: 0.7,
        metalness: 0.05,
      },
      stripe: {
        color: accent,
        roughness: 0.1,
        metalness: 0.8,
        emissive: accent,
        emissiveIntensity: 0.25,
      },
    }
  }, [params.primaryColor, params.accentColor, params.material])
}

// ── Socket cap (shoulder attachment) ─────────────────────────────────────────
function SocketCap({ radius, mat }) {
  return (
    <group>
      {/* Main socket body */}
      <mesh castShadow>
        <cylinderGeometry args={[radius, radius * 1.25, radius * 2, 32]} />
        <meshStandardMaterial {...mat.socket} />
      </mesh>
      {/* Flange ring */}
      <mesh position={[0, -radius, 0]} castShadow>
        <torusGeometry args={[radius * 1.2, radius * 0.12, 16, 48]} />
        <meshStandardMaterial {...mat.joint} />
      </mesh>
      {/* Accent stripe */}
      <mesh position={[0, radius * 0.3, 0]} castShadow>
        <cylinderGeometry args={[radius * 1.27, radius * 1.27, radius * 0.18, 32]} />
        <meshStandardMaterial {...mat.stripe} />
      </mesh>
    </group>
  )
}

// ── Carbon-fiber tube segment ─────────────────────────────────────────────────
function ArmTube({ length, radius, mat, stripes = true }) {
  return (
    <group>
      {/* Main tube */}
      <mesh castShadow>
        <cylinderGeometry args={[radius, radius, length, 32, 1, false]} />
        <meshStandardMaterial {...mat.body} />
      </mesh>
      {/* End caps */}
      <mesh position={[0, length / 2, 0]}>
        <circleGeometry args={[radius, 32]} />
        <meshStandardMaterial {...mat.body} side={THREE.BackSide} />
      </mesh>
      <mesh position={[0, -length / 2, 0]} rotation={[Math.PI, 0, 0]}>
        <circleGeometry args={[radius, 32]} />
        <meshStandardMaterial {...mat.body} side={THREE.BackSide} />
      </mesh>
      {/* Accent stripe bands */}
      {stripes && (
        <>
          <mesh position={[0, length * 0.3, 0]}>
            <cylinderGeometry args={[radius + 0.05, radius + 0.05, 0.4, 32]} />
            <meshStandardMaterial {...mat.stripe} />
          </mesh>
          <mesh position={[0, -length * 0.3, 0]}>
            <cylinderGeometry args={[radius + 0.05, radius + 0.05, 0.4, 32]} />
            <meshStandardMaterial {...mat.stripe} />
          </mesh>
        </>
      )}
    </group>
  )
}

// ── Elbow / joint assembly ────────────────────────────────────────────────────
function ElbowJoint({ radius, stiffness, mat }) {
  const jr = radius * 1.3
  return (
    <group>
      {/* Main joint sphere */}
      <mesh castShadow>
        <sphereGeometry args={[jr, 32, 32]} />
        <meshStandardMaterial {...mat.joint} />
      </mesh>
      {/* Structural flanges */}
      <mesh castShadow>
        <torusGeometry args={[jr, jr * 0.18, 16, 32]} />
        <meshStandardMaterial {...mat.body} />
      </mesh>
      <mesh rotation={[0, Math.PI / 2, 0]} castShadow>
        <torusGeometry args={[jr * 0.75, jr * 0.12, 16, 32]} />
        <meshStandardMaterial {...mat.joint} />
      </mesh>
      {/* Hinge pin */}
      <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[jr * 0.14, jr * 0.14, jr * 2.8, 16]} />
        <meshStandardMaterial color="#888" metalness={0.95} roughness={0.05} />
      </mesh>
      {/* Stiffness indicator dot — brighter = stiffer */}
      <mesh position={[0, 0, jr + 0.2]}>
        <sphereGeometry args={[jr * 0.22, 16, 16]} />
        <meshStandardMaterial
          color={stiffness > 1.5 ? '#f59e0b' : '#22c55e'}
          emissive={stiffness > 1.5 ? '#f59e0b' : '#22c55e'}
          emissiveIntensity={0.6}
          roughness={0.1}
          metalness={0.5}
        />
      </mesh>
    </group>
  )
}

// ── Wrist connector ───────────────────────────────────────────────────────────
function WristConnector({ radius, mat }) {
  return (
    <group>
      <mesh castShadow>
        <cylinderGeometry args={[radius * 0.9, radius * 1.1, radius * 2.5, 16]} />
        <meshStandardMaterial {...mat.joint} />
      </mesh>
      <mesh position={[0, 0, 0]} castShadow>
        <torusGeometry args={[radius * 0.95, radius * 0.15, 16, 32]} />
        <meshStandardMaterial {...mat.stripe} />
      </mesh>
    </group>
  )
}

// ── Two-jaw gripper terminal device ──────────────────────────────────────────
function Gripper({ gripWidth, armRadius, mat }) {
  // gripWidth in scene units (cm equivalent)
  const palmR = armRadius
  const jawLen = Math.max(gripWidth * 1.2, 5)
  const jawW = armRadius * 0.7
  const jawH = armRadius * 0.5
  const halfGap = gripWidth / 2 + jawW / 2

  // Jaw shape: tapered rectangular prism
  const jawShape = useMemo(() => {
    const s = new THREE.Shape()
    s.moveTo(-jawW / 2, 0)
    s.lineTo(jawW / 2, 0)
    s.lineTo(jawW / 3, jawLen)
    s.lineTo(-jawW / 3, jawLen)
    s.closePath()
    return s
  }, [jawW, jawLen])

  return (
    <group>
      {/* Palm */}
      <mesh castShadow>
        <cylinderGeometry args={[palmR, palmR * 0.85, palmR * 2, 32]} />
        <meshStandardMaterial {...mat.body} />
      </mesh>

      {/* Jaw 1 */}
      <group position={[halfGap, -palmR - jawLen / 2, 0]}>
        <mesh castShadow>
          <boxGeometry args={[jawW, jawLen, jawH]} />
          <meshStandardMaterial {...mat.grip} />
        </mesh>
        {/* Grip pad */}
        <mesh position={[-jawW * 0.45, 0, 0]}>
          <boxGeometry args={[jawW * 0.15, jawLen * 0.8, jawH * 0.9]} />
          <meshStandardMaterial color="#222" roughness={0.95} metalness={0} />
        </mesh>
      </group>

      {/* Jaw 2 (mirror) */}
      <group position={[-halfGap, -palmR - jawLen / 2, 0]}>
        <mesh castShadow>
          <boxGeometry args={[jawW, jawLen, jawH]} />
          <meshStandardMaterial {...mat.grip} />
        </mesh>
        <mesh position={[jawW * 0.45, 0, 0]}>
          <boxGeometry args={[jawW * 0.15, jawLen * 0.8, jawH * 0.9]} />
          <meshStandardMaterial color="#222" roughness={0.95} metalness={0} />
        </mesh>
      </group>

      {/* Actuator rod between jaws */}
      <mesh position={[0, -palmR * 1.2, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.3, 0.3, gripWidth + jawW * 2, 12]} />
        <meshStandardMaterial color="#555" metalness={0.9} roughness={0.1} />
      </mesh>
    </group>
  )
}

// ── Dimension annotation ───────────────────────────────────────────────────────
function DimLine({ start, end, label, color = '#00d4ff' }) {
  const points = [new THREE.Vector3(...start), new THREE.Vector3(...end)]
  const mid = [
    (start[0] + end[0]) / 2,
    (start[1] + end[1]) / 2 + 1,
    (start[2] + end[2]) / 2,
  ]
  return (
    <>
      <Line points={points} color={color} lineWidth={1} dashed dashSize={1} gapSize={0.5} />
      <Html position={mid} center style={{ pointerEvents: 'none' }}>
        <div style={{
          background: 'rgba(0,0,0,0.7)', border: `1px solid ${color}`,
          borderRadius: 4, padding: '2px 6px', fontSize: 10,
          fontFamily: 'JetBrains Mono, monospace', color, whiteSpace: 'nowrap',
          transform: 'translateX(8px)',
        }}>
          {label}
        </div>
      </Html>
    </>
  )
}

// ── Main assembled prosthetic arm ─────────────────────────────────────────────
export default function ProstheticArm({ params, wireframe, showDimensions }) {
  const mat = useMaterials(params)
  const groupRef = useRef()

  // Convert meters → scene units (1 unit ≈ 1 cm for readability)
  const upperLen = params.upper_arm_len * 100
  const foreLen = params.forearm_len * 100
  const gripW = params.grip_width * 100
  const armR = (params.arm_radius || 0.030) * 100
  const elbowDeg = params.elbow_angle ?? 30
  const elbowRad = (elbowDeg * Math.PI) / 180

  // Gentle idle animation
  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.3) * 0.08
    }
  })

  // Key Y positions (arm points downward in Y, origin at shoulder)
  const socketH = armR * 2
  const upperMid = -(socketH + upperLen / 2)
  const elbowY = -(socketH + upperLen)
  const jrSize = armR * 1.3 // joint radius in scene units
  const wristH = armR * 2.5
  const palmH = armR * 2

  // After elbow the forearm is angled
  const foreEndX = Math.sin(elbowRad) * foreLen
  const foreEndY = -Math.cos(elbowRad) * foreLen

  return (
    <group ref={groupRef} position={[0, upperLen / 2 + socketH, 0]}>
      {/* ── Shoulder socket ── */}
      <group position={[0, 0, 0]}>
        <SocketCap radius={armR * 1.4} mat={mat} />
      </group>

      {/* ── Upper arm tube ── */}
      <group position={[0, upperMid, 0]}>
        <ArmTube length={upperLen} radius={armR} mat={mat} />
      </group>

      {/* ── Elbow joint ── */}
      <group position={[0, elbowY, 0]}>
        <ElbowJoint radius={armR} stiffness={params.joint_stiffness} mat={mat} />

        {/* ── Forearm (rotated at elbow) ── */}
        <group rotation={[0, 0, -elbowRad]}>
          <group position={[0, -(jrSize + foreLen / 2), 0]}>
            <ArmTube length={foreLen} radius={armR * 0.9} mat={mat} />
          </group>

          {/* ── Wrist ── */}
          <group position={[0, -(jrSize + foreLen), 0]}>
            <WristConnector radius={armR * 0.9} mat={mat} />

            {/* ── Gripper ── */}
            <group position={[0, -wristH / 2, 0]}>
              <Gripper gripWidth={gripW} armRadius={armR * 0.85} mat={mat} />
            </group>
          </group>
        </group>
      </group>

      {/* Wireframe overlay */}
      {wireframe && (
        <mesh>
          <sphereGeometry args={[upperLen + foreLen, 24, 24]} />
          <meshBasicMaterial color="#00d4ff" wireframe transparent opacity={0.04} />
        </mesh>
      )}

      {/* ── Dimension annotations ── */}
      {showDimensions && (
        <>
          <DimLine
            start={[-armR * 3, 0, 0]}
            end={[-armR * 3, elbowY, 0]}
            label={`↕ ${(params.upper_arm_len * 100).toFixed(1)} cm`}
          />
          <DimLine
            start={[-armR * 3, elbowY, 0]}
            end={[-armR * 3 + foreEndX - armR * 3, elbowY + foreEndY, 0]}
            label={`↕ ${(params.forearm_len * 100).toFixed(1)} cm`}
            color="#7c3aed"
          />
          <DimLine
            start={[gripW / 2, elbowY + foreEndY - jrSize - foreLen - wristH - palmH, 0]}
            end={[-gripW / 2, elbowY + foreEndY - jrSize - foreLen - wristH - palmH, 0]}
            label={`↔ ${(params.grip_width * 100).toFixed(1)} cm`}
            color="#22c55e"
          />
        </>
      )}
    </group>
  )
}
