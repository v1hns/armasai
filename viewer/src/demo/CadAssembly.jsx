import { Suspense, useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Grid, Environment, Html } from '@react-three/drei'
import * as THREE from 'three'
import { CAD_PARTS } from './demoData.js'

// ── Materials (matches the studio viewer palette) ─────────────────────────────
function useMats(params) {
  return useMemo(() => {
    const primary = params.primaryColor || '#0d1117'
    const accent = params.accentColor || '#00d4ff'
    return {
      body: { color: primary, roughness: 0.18, metalness: 0.45, envMapIntensity: 1.5 },
      joint: { color: accent, roughness: 0.08, metalness: 0.95, emissive: accent, emissiveIntensity: 0.15, envMapIntensity: 2 },
      socket: { color: '#1e1e2e', roughness: 0.35, metalness: 0.25 },
      grip: { color: '#111118', roughness: 0.7, metalness: 0.05 },
      stripe: { color: accent, roughness: 0.1, metalness: 0.8, emissive: accent, emissiveIntensity: 0.3 },
    }
  }, [params.primaryColor, params.accentColor])
}

// ── Entrance wrapper: each part scales up when revealed ───────────────────────
// (Scale only — never touch position; the part's place is fixed by its <At y>.)
function Part({ show, children }) {
  const ref = useRef()
  const lit = useRef(0) // 0..1 progress
  useFrame((_, dt) => {
    const target = show ? 1 : 0
    lit.current += (target - lit.current) * Math.min(1, dt * 6)
    const p = lit.current
    if (ref.current) {
      ref.current.visible = p > 0.01
      ref.current.scale.setScalar(p)
    }
  })
  return <group ref={ref}>{children}</group>
}

// Position a part group at y; the inner <Part> only scales in.
function At({ y, show, children }) {
  return (
    <group position={[0, y, 0]} userData={{ _y: y }}>
      <Part show={show}>{children}</Part>
    </group>
  )
}

function Socket({ r, mat }) {
  return (
    <group>
      <mesh castShadow><cylinderGeometry args={[r, r * 1.25, r * 2, 32]} /><meshStandardMaterial {...mat.socket} /></mesh>
      <mesh position={[0, -r, 0]} castShadow><torusGeometry args={[r * 1.2, r * 0.12, 16, 48]} /><meshStandardMaterial {...mat.joint} /></mesh>
      <mesh position={[0, r * 0.3, 0]}><cylinderGeometry args={[r * 1.27, r * 1.27, r * 0.18, 32]} /><meshStandardMaterial {...mat.stripe} /></mesh>
    </group>
  )
}

function Tube({ len, r, mat }) {
  return (
    <group>
      <mesh castShadow><cylinderGeometry args={[r, r, len, 32]} /><meshStandardMaterial {...mat.body} /></mesh>
      <mesh position={[0, len * 0.3, 0]}><cylinderGeometry args={[r + 0.05, r + 0.05, 0.4, 32]} /><meshStandardMaterial {...mat.stripe} /></mesh>
      <mesh position={[0, -len * 0.3, 0]}><cylinderGeometry args={[r + 0.05, r + 0.05, 0.4, 32]} /><meshStandardMaterial {...mat.stripe} /></mesh>
    </group>
  )
}

function Elbow({ r, stiffness, mat }) {
  const jr = r * 1.3
  return (
    <group>
      <mesh castShadow><sphereGeometry args={[jr, 32, 32]} /><meshStandardMaterial {...mat.joint} /></mesh>
      <mesh castShadow><torusGeometry args={[jr, jr * 0.18, 16, 32]} /><meshStandardMaterial {...mat.body} /></mesh>
      <mesh rotation={[0, 0, Math.PI / 2]} castShadow><cylinderGeometry args={[jr * 0.14, jr * 0.14, jr * 2.8, 16]} /><meshStandardMaterial color="#888" metalness={0.95} roughness={0.05} /></mesh>
      <mesh position={[0, 0, jr + 0.2]}><sphereGeometry args={[jr * 0.22, 16, 16]} /><meshStandardMaterial color={stiffness > 1.5 ? '#f59e0b' : '#22c55e'} emissive={stiffness > 1.5 ? '#f59e0b' : '#22c55e'} emissiveIntensity={0.6} /></mesh>
    </group>
  )
}

function Wrist({ r, mat }) {
  return (
    <group>
      <mesh castShadow><cylinderGeometry args={[r * 0.9, r * 1.1, r * 2.5, 16]} /><meshStandardMaterial {...mat.joint} /></mesh>
      <mesh><torusGeometry args={[r * 0.95, r * 0.15, 16, 32]} /><meshStandardMaterial {...mat.stripe} /></mesh>
    </group>
  )
}

function Gripper({ gripW, r, mat }) {
  const palmR = r
  const jawLen = Math.max(gripW * 1.2, 5)
  const jawW = r * 0.7
  const halfGap = gripW / 2 + jawW / 2
  return (
    <group>
      <mesh castShadow><cylinderGeometry args={[palmR, palmR * 0.85, palmR * 2, 32]} /><meshStandardMaterial {...mat.body} /></mesh>
      {[halfGap, -halfGap].map((x, i) => (
        <mesh key={i} position={[x, -palmR - jawLen / 2, 0]} castShadow>
          <boxGeometry args={[jawW, jawLen, r * 0.5]} /><meshStandardMaterial {...mat.grip} />
        </mesh>
      ))}
      <mesh position={[0, -palmR * 1.2, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.3, 0.3, gripW + jawW * 2, 12]} /><meshStandardMaterial color="#555" metalness={0.9} roughness={0.1} /></mesh>
    </group>
  )
}

// ── The arm, assembled straight (top→down) so each part reads as "added" ───────
// qpos = [shoulder_flex, shoulder_abduct, elbow, wrist] in radians (MuJoCo convention)
function Arm({ params, revealed, qpos }) {
  const mat = useMats(params)
  const ref = useRef()
  const idleRef = useRef(0)
  useFrame((s, dt) => {
    // Idle sway only when not playing back a trajectory
    if (!qpos) {
      idleRef.current += dt * 0.25
      if (ref.current) ref.current.rotation.y = Math.sin(idleRef.current) * 0.25
    } else {
      if (ref.current) ref.current.rotation.y = 0
    }
  })

  const r = (params.arm_radius || 0.03) * 100
  const upperLen = params.upper_arm_len * 100
  const foreLen = params.forearm_len * 100
  const gripW = params.grip_width * 100

  // Vertical stack, origin at shoulder, arm points down (−Y).
  const socketH = r * 2
  const elbowD = r * 2.6
  const wristH = r * 2.5
  const gripH = r * 2.2

  // qpos in radians: [shoulder_flex(Y), shoulder_abduct(X), elbow(Y), wrist(X)]
  const sf  = qpos?.[0] ?? 0  // shoulder flexion
  const sa  = qpos?.[1] ?? 0  // shoulder abduction
  const elb = qpos?.[2] ?? 0  // elbow
  const wr  = qpos?.[3] ?? 0  // wrist

  let y = 0
  const ySocket = y - socketH / 2; y -= socketH
  const yUpper = y - upperLen / 2; y -= upperLen
  const yElbow = y - elbowD / 2; y -= elbowD
  const yFore = y - foreLen / 2; y -= foreLen
  const yWrist = y - wristH / 2; y -= wristH
  const yGrip = y - gripH / 2; y -= gripH
  const total = -y
  // Center the arm's geometric centroid on the origin so it frames cleanly.
  const centerOff = total / 2

  // Hierarchical offsets for kinematic joint animation:
  // shoulder group → elbow group → wrist group
  const shoulderPivotY = ySocket  // pivot at socket bottom
  const elbowPivotY    = yElbow   // pivot at elbow center

  return (
    <group ref={ref} position={[0, centerOff, 0]}>
      {/* Socket: fixed to mount — no joint rotation */}
      <At y={ySocket} show={revealed > 0}><Socket r={r * 1.4} mat={mat} /></At>

      {/* Shoulder group: upper arm + elbow + forearm + wrist + gripper all rotate together */}
      <group position={[0, shoulderPivotY, 0]} rotation={[sa, sf, 0]}>
        <At y={yUpper - shoulderPivotY} show={revealed > 1}><Tube len={upperLen} r={r} mat={mat} /></At>

        {/* Elbow group: forearm + wrist + gripper rotate relative to upper arm */}
        <group position={[0, elbowPivotY - shoulderPivotY, 0]} rotation={[0, elb, 0]}>
          <At y={yElbow - elbowPivotY} show={revealed > 2}><Elbow r={r} stiffness={params.joint_stiffness} mat={mat} /></At>
          <At y={yFore - elbowPivotY} show={revealed > 3}><Tube len={foreLen} r={r * 0.9} mat={mat} /></At>

          {/* Wrist group */}
          <group position={[0, yWrist - elbowPivotY, 0]} rotation={[wr, 0, 0]}>
            <At y={0} show={revealed > 4}><Wrist r={r * 0.9} mat={mat} /></At>
            <At y={yGrip - yWrist} show={revealed > 5}><Gripper gripW={gripW} r={r * 0.85} mat={mat} /></At>
          </group>
        </group>
      </group>

      {revealed > 0 && revealed <= CAD_PARTS.length && (
        <Html position={[0, centerOff * 0 + 2, 0]} center style={{ pointerEvents: 'none' }}>
          <div style={{
            background: 'rgba(0,212,255,0.12)', border: '1px solid #00d4ff',
            borderRadius: 6, padding: '3px 10px', whiteSpace: 'nowrap',
            fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#00d4ff',
            transform: 'translateY(-60px)', backdropFilter: 'blur(4px)',
          }}>
            ⚙ welding · {CAD_PARTS[Math.min(revealed - 1, CAD_PARTS.length - 1)].label}
          </div>
        </Html>
      )}
    </group>
  )
}

export default function CadAssembly({ params, revealed, qpos }) {
  // Full-model extent (same stack as <Arm>) for the framing proxy + grid floor.
  const r = (params.arm_radius || 0.03) * 100
  const total = r * 2 + (params.upper_arm_len || 0.3) * 100 + r * 2.6 +
    (params.forearm_len || 0.26) * 100 + r * 2.5 + r * 2.2
  const floorY = -total / 2 - 4

  return (
    <Canvas shadows gl={{ antialias: true, alpha: true }} camera={{ position: [total * 0.8, total * 0.45, total * 1.4], fov: 42, near: 1, far: total * 14 }} style={{ width: '100%', height: '100%' }}>
      <OrbitControls enableDamping dampingFactor={0.08} enablePan={false} target={[0, 0, 0]} minDistance={total * 0.8} maxDistance={total * 4} />
      <ambientLight intensity={0.7} />
      <hemisphereLight intensity={0.6} groundColor="#0a0a0f" />
      <directionalLight position={[40, 60, 30]} intensity={2.2} castShadow shadow-mapSize={[1024, 1024]} />
      <directionalLight position={[-30, 10, -20]} intensity={0.6} color="#7c3aed" />
      <pointLight position={[0, 0, 30]} intensity={0.9} color="#00d4ff" distance={160} />
      <Suspense fallback={null}>
        <Environment preset="city" />
      </Suspense>
      <Grid position={[0, floorY, 0]} args={[400, 400]} cellSize={5} cellThickness={0.5} sectionSize={20} sectionThickness={1} cellColor="#1a1a2e" sectionColor="#2a2a40" fadeDistance={total * 3} fadeStrength={1} infiniteGrid />
      <Arm params={params} revealed={revealed} qpos={qpos} />
    </Canvas>
  )
}
