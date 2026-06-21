export default function ScenarioPanel({ scenario, trajectory, trajectoryIdx }) {
  if (!scenario) return null

  const pctDone = trajectory?.length
    ? Math.round((trajectoryIdx / trajectory.length) * 100)
    : null

  return (
    <div className="scenario-panel">
      <div className="scenario-head">
        <span className="scenario-icon">🎯</span>
        <div>
          <div className="scenario-title">{scenario.task_id || 'ADL Task'}</div>
          <div className="scenario-sub">{scenario.description || ''}</div>
        </div>
        {scenario.source && (
          <span className={`scenario-src ${scenario.source === 'library' ? 'lib' : 'llm'}`}>
            {scenario.source === 'library' ? 'ADL lib' : 'LLM'}
          </span>
        )}
      </div>

      <div className="scenario-rows">
        <div className="scenario-row">
          <span className="scenario-k">Posture</span>
          <span className="scenario-v">{scenario.posture || '—'}</span>
        </div>
        {scenario.success_condition && (
          <div className="scenario-row">
            <span className="scenario-k">Success when</span>
            <span className="scenario-v">{scenario.success_condition}</span>
          </div>
        )}
      </div>

      {scenario.waypoints?.length > 0 && (
        <div className="scenario-waypoints">
          <div className="scenario-section-label">Waypoints</div>
          {scenario.waypoints.map((wp, i) => (
            <div key={i} className="wp-row">
              <span className="wp-name">{wp.name}</span>
              <span className="wp-pos">[{wp.pos?.map((v) => v.toFixed(2)).join(', ')}]</span>
              {wp.weight > 1 && <span className="wp-primary">★ primary</span>}
            </div>
          ))}
        </div>
      )}

      {scenario.objects?.length > 0 && (
        <div className="scenario-objects">
          <div className="scenario-section-label">Scene objects</div>
          {scenario.objects.map((obj, i) => (
            <div key={i} className="obj-row">
              <span
                className="obj-color"
                style={{
                  background: obj.rgba
                    ? `rgba(${obj.rgba.map((v) => Math.round(v * 255)).join(',')})`
                    : '#444',
                }}
              />
              <span className="obj-name">{obj.name}</span>
              <span className="obj-prompt">{obj.prompt || ''}</span>
            </div>
          ))}
        </div>
      )}

      {pctDone !== null && (
        <div className="traj-bar">
          <div className="traj-label">
            Playback {pctDone}% · frame {trajectoryIdx}/{trajectory.length}
          </div>
          <div className="traj-track">
            <div className="traj-fill" style={{ width: `${pctDone}%` }} />
          </div>
        </div>
      )}
    </div>
  )
}
