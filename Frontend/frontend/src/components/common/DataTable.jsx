import { useState, useEffect } from 'react'
import { EmptyState } from './EmptyState'
import { Database, Loader2 } from 'lucide-react'

export function DataTable({ columns, rows, getRowKey, loading = false, emptyTitle, emptyDescription, minWidth = 720, onRowClick }) {
  const [showColdStartNotice, setShowColdStartNotice] = useState(false)

  useEffect(() => {
    let timer
    if (loading) {
      timer = setTimeout(() => {
        setShowColdStartNotice(true)
      }, 2200)
    } else {
      setShowColdStartNotice(false)
    }
    return () => clearTimeout(timer)
  }, [loading])

  if (!loading && !rows.length) return <EmptyState title={emptyTitle ?? 'No records found'} description={emptyDescription} />
  return (
    <div className="table-scroll-container">
      {loading && showColdStartNotice && (
        <div
          role="status"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '10px 16px',
            marginBottom: 12,
            borderRadius: 8,
            background: 'rgba(255, 138, 36, 0.1)',
            border: '1px solid rgba(255, 138, 36, 0.3)',
            color: 'var(--dr-orange, #FF8A24)',
            fontSize: 12,
            fontWeight: 500,
          }}
        >
          <Database size={16} className="animate-pulse" />
          <span>Database waking up (PostgreSQL free tier cold start)... initial response may take a few seconds.</span>
        </div>
      )}
      <div className="table-scroll" style={{ overflowX: 'auto', overflowY: 'auto', width: '100%', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
        <table className="orders-table" style={{ minWidth, width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--line)' }}>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={column.className}
                  style={{
                    padding: '14px 20px',
                    textAlign: 'left',
                    fontSize: '11px',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: 'var(--text-muted)',
                    background: 'var(--kg-bg-2)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {column.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 6 }, (_, index) => (
                  <tr key={`loading-${index}`} style={{ borderTop: '1px solid var(--line)' }}>
                    {columns.map((column, colIdx) => (
                      <td key={column.key} style={{ padding: '14px 20px' }}>
                        <div
                          className="skeleton-line"
                          style={{
                            height: 14,
                            borderRadius: 4,
                            width: colIdx === 0 ? '70%' : colIdx === 1 ? '85%' : colIdx === 2 ? '50%' : '65%',
                            background: 'var(--line)',
                            opacity: 0.6,
                            animation: 'pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                          }}
                        />
                      </td>
                    ))}
                  </tr>
                ))
              : rows.map((row, rowIndex) => (
                  <tr
                    key={getRowKey(row)}
                    style={{
                      borderTop: '1px solid var(--line)',
                      transition: 'background 0.15s ease',
                      cursor: onRowClick ? 'pointer' : 'default',
                    }}
                    className={`table-row-hover ${onRowClick ? 'clickable-row' : ''}`}
                    onClick={(e) => {
                      if (onRowClick) {
                        if (e.target.closest('a') || e.target.closest('button')) return
                        onRowClick(row, rowIndex)
                      }
                    }}
                  >
                    {columns.map((column) => (
                      <td
                        key={column.key}
                        className={column.className}
                        style={{
                          padding: '14px 20px',
                          fontSize: '13px',
                          color: 'var(--text-secondary)',
                          whiteSpace: 'nowrap',
                          verticalAlign: 'middle',
                        }}
                      >
                        {column.render ? column.render(row, rowIndex) : row[column.key]}
                      </td>
                    ))}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
