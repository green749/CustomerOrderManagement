import { LoaderCircle } from 'lucide-react'

export function Loader({ compact = false }) {
  return (
    <div
      className={`page-loader${compact ? ' page-loader-compact' : ''}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        padding: compact ? '8px 0' : '32px 0',
      }}
      role="status"
      aria-label="Loading"
    >
      <LoaderCircle
        className="spin"
        size={compact ? 20 : 36}
        style={{
          color: 'var(--dr-purple, var(--brand-purple, #6f3dba))',
        }}
      />
      <span className="sr-only">Loading</span>
    </div>
  )
}
