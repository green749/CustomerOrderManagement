import { ChevronDown, ChevronUp, Wrench, CheckCircle, AlertCircle } from 'lucide-react'
import { useState } from 'react'

export function ToolTrace({ tools }) {
  const [open, setOpen] = useState(false)
  if (!tools?.length) return null

  return (
    <div className="tool-trace" style={{ margin: '8px 0', border: '1px solid var(--line)', borderRadius: 8, overflow: 'hidden', background: 'var(--kg-bg-2)' }}>
      <button
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        type="button"
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 12px',
          background: 'transparent',
          border: 'none',
          color: 'var(--brand-orange)',
          fontSize: 11,
          fontWeight: 700,
          cursor: 'pointer',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Wrench size={13} />
          {tools.length} Operational Tool{tools.length === 1 ? '' : 's'} Executed &amp; Verified
        </span>
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>

      {open && (
        <div className="tool-trace-list" style={{ padding: '8px 12px', borderTop: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {tools.map((tool, index) => {
            const isError = tool.status === 'error' || Boolean(tool.output?.error)
            return (
              <div
                key={tool.id ?? index}
                style={{
                  padding: 8,
                  borderRadius: 6,
                  background: 'rgba(0, 0, 0, 0.25)',
                  border: `1px solid ${isError ? 'rgba(239, 68, 68, 0.3)' : 'var(--line)'}`,
                  fontSize: 11,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <strong style={{ color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    {isError ? <AlertCircle size={12} color="#ef4444" /> : <CheckCircle size={12} color="#10b981" />}
                    Step {tool.step ?? index + 1}: {tool.tool ?? tool.name ?? 'tool_call'}
                  </strong>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      padding: '1px 6px',
                      borderRadius: 4,
                      background: isError ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                      color: isError ? '#ef4444' : '#10b981',
                    }}
                  >
                    {isError ? 'ERROR' : 'VERIFIED'}
                  </span>
                </div>

                {tool.thought && (
                  <div style={{ fontSize: 10, color: 'var(--text-secondary)', fontStyle: 'italic', margin: '4px 0' }}>
                    Reasoning: {tool.thought}
                  </div>
                )}

                {tool.input && Object.keys(tool.input).length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    <span style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Arguments:</span>
                    <pre style={{ margin: '2px 0 0', padding: 4, background: 'rgba(0, 0, 0, 0.3)', borderRadius: 4, fontSize: 10, overflowX: 'auto', color: 'var(--brand-blue)' }}>
                      {JSON.stringify(tool.input, null, 2)}
                    </pre>
                  </div>
                )}

                {tool.output && (
                  <div style={{ marginTop: 4 }}>
                    <span style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Database Result:</span>
                    <pre style={{ margin: '2px 0 0', padding: 4, background: 'rgba(0, 0, 0, 0.3)', borderRadius: 4, fontSize: 10, maxHeight: 100, overflowY: 'auto', color: 'var(--text-secondary)' }}>
                      {typeof tool.output === 'string' ? tool.output : JSON.stringify(tool.output, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
