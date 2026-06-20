import { Suspense, useRef } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid, Environment, PerspectiveCamera, GizmoHelper, GizmoViewport } from '@react-three/drei'
import ProstheticArm from './ProstheticArm.jsx'

function SceneInfo({ params }) {
  return (
    <div style={{
      position: 'absolute', bottom: 16, left: 16,
      background: 'rgba(10,10,15,0.8)', border: '1px solid #2a2a3a',
      borderRadius: 8, padding: '8px 12px',
      fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
      color: '#6b6b80', lineHeight: 1.8, backdropFilter: 'blur(8px)',
      pointerEvents: 'none',
    }}>
      <div style={{ color: '#00d4ff', marginBottom: 2, fontWeight: 600 }}>DESIGN PARAMS</div>
      <div>upper_arm  <span style={{ color: '#e8e8f0' }}>{(params.upper_arm_len * 100).toFixed(1)} cm</span></div>
      <div>forearm    <span style={{ color: '#e8e8f0' }}>{(params.forearm_len * 100).toFixed(1)} cm</span></div>
      <div>grip_width <span style={{ color: '#e8e8f0' }}>{(params.grip_width * 100).toFixed(1)} cm</span></div>
      <div>stiffness  <span style={{ color: '#e8e8f0' }}>{params.joint_stiffness.toFixed(2)} N·m/rad</span></div>
      <div>material   <span style={{ color: '#e8e8f0' }}>{params.material}</span></div>
    </div>
  )
}

function LoadingFallback() {
  return (
    <mesh>
      <sphereGeometry args={[0.5]} />
      <meshStandardMaterial color="#00d4ff" wireframe />
    </mesh>
  )
}

export default function Viewer3D({ params, wireframe, showDimensions }) {
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas shadows gl={{ antialias: true, alpha: false }}>
        <color attach="background" args={['#0a0a0f']} />
        <fog attach="fog" args={['#0a0a0f', 80, 200]} />

        <PerspectiveCamera makeDefault position={[60, 30, 60]} fov={35} near={0.1} far={500} />
        <OrbitControls
          enableDamping
          dampingFactor={0.06}
          minDistance={20}
          maxDistance={200}
          target={[0, 0, 0]}
        />

        <ambientLight intensity={0.3} />
        <directionalLight
          position={[40, 60, 30]}
          intensity={1.8}
          castShadow
          shadow-mapSize={[2048, 2048]}
          shadow-camera-left={-80}
          shadow-camera-right={80}
          shadow-camera-top={80}
          shadow-camera-bottom={-80}
        />
        <directionalLight position={[-30, 10, -20]} intensity={0.4} color="#7c3aed" />
        <pointLight position={[0, 0, 30]} intensity={0.6} color="#00d4ff" distance={120} />

        <Environment preset="city" />

        <Grid
          position={[0, -18, 0]}
          args={[200, 200]}
          cellSize={5}
          cellThickness={0.5}
          sectionSize={20}
          sectionThickness={1}
          cellColor="#1a1a2e"
          sectionColor="#2a2a40"
          fadeDistance={160}
          fadeStrength={1}
          infiniteGrid
        />

        <Suspense fallback={<LoadingFallback />}>
          <ProstheticArm params={params} wireframe={wireframe} showDimensions={showDimensions} />
        </Suspense>

        <GizmoHelper alignment="bottom-right" margin={[60, 60]}>
          <GizmoViewport
            axisColors={['#ff4060', '#22c55e', '#00d4ff']}
            labelColor="white"
          />
        </GizmoHelper>
      </Canvas>

      <SceneInfo params={params} />

      <div style={{
        position: 'absolute', top: 12, right: 12,
        color: '#2a2a3a', fontSize: 10, letterSpacing: '0.08em',
        fontFamily: 'JetBrains Mono, monospace',
        pointerEvents: 'none',
      }}>
        DRAG TO ORBIT · SCROLL TO ZOOM · RIGHT-DRAG TO PAN
      </div>
    </div>
  )
}
