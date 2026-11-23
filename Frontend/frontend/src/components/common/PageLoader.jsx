import { LoaderCircle } from 'lucide-react'

export function PageLoader({ fullScreen = false }) {
  return (
    <div
      className="page-loader-centered"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        minHeight: fullScreen ? '100vh' : 'calc(100vh - 120px)',
        height: '100%',
        flex: 1,
      }}
      role="status"
      aria-label="Loading"
    >
      <LoaderCircle
        className="spin"
        size={42}
        style={{
          color: 'var(--dr-purple, var(--brand-purple, #6f3dba))',
        }}
      />
      <span className="sr-only">Loading</span>
    </div>
  )
}
