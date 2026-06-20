import { DEFAULT_PARAMS } from '../lib/defaults.js'

function Slider({ label, unit, value, min, max, step, onChange, color = '#00d4ff' }) {
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <label style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
          {label}
        </label>
        <span style={{ fontSize: 11, color, fontFamily: 'var(--mono)', fontWeight: 600 }}>
          {typeof value === 'number' ? (unit === 'cm' ? (value * 100).toFixed(1) : value.toFixed(2)) : value} {unit}
        </span>
      </div>
      <div style={{ position: 'relative', height: 4, background: 'var(--border)', borderRadius: 2 }}>
        <div style={{ position: 'absolute', left: 0, width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.1s' }} />
        <input
          type="range" min={min} max={max} step={step} value={value}
          onChange={e => onChange(parseFloat(e.target.value))}
          style={{
            position: 'absolute', top: -6, left: 0, width: '100%',
            opacity: 0, cursor: 'pointer', height: 16,
          }}
        />
      </div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
        color: 'var(--text-muted)', textTransform: 'uppercase',
        marginBottom: 12, paddingBottom: 6, borderBottom: '1px solid var(--border)',
      }}>
        {title}
      </div>
      {children}
    </div>
  )
}

const MATERIALS = ['carbon_fiber', 'titanium', 'polymer']

export default function ParameterPanel({ params, onChange }) {
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
      <Section title="Arm Dimensions">
        <Slider
          label="upper_arm_len" unit="cm"
          value={params.upper_arm_len} min={0.18} max={0.42} step={0.005}
          onChange={v => onChange({ upper_arm_len: v })}
        />
        <Slider
          label="forearm_len" unit="cm"
          value={params.forearm_len} min={0.15} max={0.36} step={0.005}
          onChange={v => onChange({ forearm_len: v })}
        />
        <Slider
          label="arm_radius" unit="cm"
          value={params.arm_radius || 0.030} min={0.015} max={0.050} step={0.002}
          onChange={v => onChange({ arm_radius: v })}
          color="#7c3aed"
        />
      </Section>

      <Section title="Joint Parameters">
        <Slider
          label="joint_stiffness" unit="N·m/rad"
          value={params.joint_stiffness} min={0.3} max={3.5} step={0.05}
          onChange={v => onChange({ joint_stiffness: v })}
          color="#f59e0b"
        />
        <Slider
          label="elbow_angle" unit="°"
          value={params.elbow_angle ?? 30} min={0} max={140} step={1}
          onChange={v => onChange({ elbow_angle: v })}
          color="#f59e0b"
        />
      </Section>

      <Section title="Terminal Device">
        <Slider
          label="grip_width" unit="cm"
          value={params.grip_width} min={0.03} max={0.16} step={0.005}
          onChange={v => onChange({ grip_width: v })}
          color="#22c55e"
        />
      </Section>

      <Section title="Material & Color">
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          {MATERIALS.map(m => (
            <button
              key={m}
              onClick={() => onChange({ material: m })}
              style={{
                flex: 1, padding: '6px 4px', fontSize: 10, borderRadius: 6,
                border: `1px solid ${params.material === m ? 'var(--accent)' : 'var(--border)'}`,
                background: params.material === m ? 'rgba(0,212,255,0.1)' : 'transparent',
                color: params.material === m ? 'var(--accent)' : 'var(--text-muted)',
                cursor: 'pointer', fontFamily: 'var(--mono)', letterSpacing: '0.02em',
              }}
            >
              {m.replace('_', ' ')}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10 }}>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', flex: 1 }}>Primary</label>
          <input
            type="color" value={params.primaryColor || '#0d1117'}
            onChange={e => onChange({ primaryColor: e.target.value })}
            style={{ width: 36, height: 24, border: 'none', borderRadius: 4, background: 'none', cursor: 'pointer' }}
          />
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <label style={{ fontSize: 11, color: 'var(--text-muted)', flex: 1 }}>Accent</label>
          <input
            type="color" value={params.accentColor || '#00d4ff'}
            onChange={e => onChange({ accentColor: e.target.value })}
            style={{ width: 36, height: 24, border: 'none', borderRadius: 4, background: 'none', cursor: 'pointer' }}
          />
        </div>
      </Section>

      <Section title="Joint Limits">
        <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.8 }}>
          <div>
            elbow: <span style={{ color: 'var(--text)' }}>
              [{(params.joint_limits?.elbow?.[0] ?? 0).toFixed(0)}°,{' '}
              {(params.joint_limits?.elbow?.[1] ?? 120).toFixed(0)}°]
            </span>
          </div>
          <div>
            wrist: <span style={{ color: 'var(--text)' }}>
              [{(params.joint_limits?.wrist?.[0] ?? -45).toFixed(0)}°,{' '}
              {(params.joint_limits?.wrist?.[1] ?? 45).toFixed(0)}°]
            </span>
          </div>
        </div>
      </Section>
    </div>
  )
}
