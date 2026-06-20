import { useRef, useEffect, useState } from 'react'

const SUGGESTIONS = [
  'Adult male, 28cm residual limb, construction worker',
  'Child age 10, below-elbow amputation, active',
  'Make the forearm 5cm longer',
  'Switch to titanium material',
  'Increase grip width for large objects',
]

export default function ChatPanel({ messages, onSend, loading }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const submit = () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    onSend(text)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <div style={{
              maxWidth: '88%',
              padding: '8px 12px',
              borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
              background: msg.role === 'user' ? 'rgba(0,212,255,0.15)' : 'var(--surface2)',
              border: `1px solid ${msg.role === 'user' ? 'rgba(0,212,255,0.3)' : 'var(--border)'}`,
              fontSize: 13,
              lineHeight: 1.55,
              color: 'var(--text)',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', gap: 4, padding: '4px 8px' }}>
            {[0, 1, 2].map(i => (
              <div key={i} style={{
                width: 6, height: 6, borderRadius: '50%',
                background: 'var(--accent)',
                animation: `pulse 1s ${i * 0.2}s infinite`,
              }} />
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions (only show when short history) */}
      {messages.length <= 2 && (
        <div style={{ padding: '0 12px 8px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {SUGGESTIONS.map((s, i) => (
            <button
              key={i}
              onClick={() => { setInput(s) }}
              style={{
                padding: '4px 10px', fontSize: 11, borderRadius: 20,
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--text-muted)', cursor: 'pointer',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => { e.target.style.borderColor = 'var(--accent)'; e.target.style.color = 'var(--accent)' }}
              onMouseLeave={e => { e.target.style.borderColor = 'var(--border)'; e.target.style.color = 'var(--text-muted)' }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div style={{
        padding: '10px 12px',
        borderTop: '1px solid var(--border)',
        display: 'flex', gap: 8, alignItems: 'flex-end',
      }}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
          placeholder="Describe patient or request a change…"
          rows={2}
          style={{
            flex: 1, resize: 'none', background: 'var(--surface2)',
            border: '1px solid var(--border)', borderRadius: 8,
            padding: '8px 10px', fontSize: 13, color: 'var(--text)',
            fontFamily: 'var(--font)', lineHeight: 1.5, outline: 'none',
            transition: 'border-color 0.15s',
          }}
          onFocus={e => e.target.style.borderColor = 'var(--accent)'}
          onBlur={e => e.target.style.borderColor = 'var(--border)'}
        />
        <button
          onClick={submit}
          disabled={!input.trim() || loading}
          style={{
            width: 36, height: 36, borderRadius: 8, border: 'none',
            background: input.trim() && !loading ? 'var(--accent)' : 'var(--border)',
            color: input.trim() && !loading ? 'var(--bg)' : 'var(--text-muted)',
            fontSize: 16, cursor: input.trim() && !loading ? 'pointer' : 'default',
            transition: 'all 0.15s', flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          ↑
        </button>
      </div>

      <style>{`@keyframes pulse { 0%,100%{opacity:0.3;transform:scale(0.8)} 50%{opacity:1;transform:scale(1)} }`}</style>
    </div>
  )
}
