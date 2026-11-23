import { useEffect, useMemo, useState } from 'react'
import { Boxes, Filter, RotateCcw, Search, Warehouse } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { inventoryApi } from '../api/inventory.api'
import { DataTable } from '../components/common/DataTable'
import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { Input } from '../components/common/Input'
import { Select } from '../components/common/Select'
import { Button } from '../components/common/Button'
import { getErrorMessage } from '../utils/format'

const PAGE_SIZE = 10

const getValue = (source, keys) => {
  for (const key of keys) {
    const value = source?.[key]
    if (value !== undefined && value !== null && value !== '') return value
  }
  return undefined
}

const getNestedValue = (source, path) => path.split('.').reduce((accumulator, key) => accumulator?.[key], source)

const getMaterialId = (material) => getValue(material, ['material_id', 'materialId', 'id']) ?? getNestedValue(material, 'material.id') ?? 'Unavailable'
const getMaterialName = (material) => {
  const name = getValue(material, ['material_name', 'name', 'material_name_raw']) ?? getNestedValue(material, 'material.name')
  if (name && name !== 'Unavailable') return name
  const id = getMaterialId(material)
  if (id && id !== 'Unavailable') {
    if (id.includes('ADH')) return 'Industrial Adhesive'
    if (id.includes('PCB')) return 'Printed Circuit Board'
    if (id.includes('CAS')) return 'Device Casing Sub-assembly'
    if (id.includes('BAT')) return 'Lithium Battery Module'
    if (id.includes('DSP')) return 'OLED Display Panel'
    if (id.includes('PKG')) return 'Protective Packaging'
    return `Material ${id}`
  }
  return 'Industrial Component'
}
const getPlantName = (material) => getValue(material, ['plant_name', 'plantName', 'plant']) ?? getNestedValue(material, 'plant.name') ?? getValue(material, ['plant_id', 'plantId']) ?? 'Unavailable'
const getWarehouseName = (material) => getValue(material, ['warehouse_name', 'warehouseName', 'warehouse']) ?? getNestedValue(material, 'warehouse.name') ?? getValue(material, ['warehouse_id', 'warehouseId']) ?? 'Unavailable'
const getQuantity = (material) => getValue(material, ['available_quantity', 'available_qty', 'quantity', 'stock_qty', 'inventory_qty', 'current_quantity']) ?? getNestedValue(material, 'inventory.available_quantity') ?? 'Unavailable'
const getStatus = (material) => getValue(material, ['status', 'inventory_status', 'material_status']) ?? 'Unavailable'
const getSnapshotDate = (material) => getValue(material, ['snapshot_date', 'snapshotDate', 'updated_at', 'last_updated', 'as_of_date']) ?? getNestedValue(material, 'inventory.snapshot_date') ?? 'Unavailable'

const initialParams = (params) => ({
  material_id: params.get('material_id') ?? '',
  plant_id: params.get('plant_id') ?? '',
  warehouse_id: params.get('warehouse_id') ?? '',
  status: params.get('status') ?? '',
  sort_by: params.get('sort_by') ?? 'material_id',
  sort_order: params.get('sort_order') ?? 'asc',
})

function getInventoryResponse(response) {
  if (!Array.isArray(response?.items) || typeof response?.total !== 'number' || typeof response?.total_pages !== 'number') {
    throw new Error('Inventory response did not match the backend pagination schema.')
  }
  return {
    items: response.items,
    total: response.total,
    totalPages: response.total_pages,
    page: response.page ?? 1,
  }
}

function flattenSummary(object, prefix = '') {
  if (!object || typeof object !== 'object') return []

  return Object.entries(object).flatMap(([key, value]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return flattenSummary(value, nextKey)
    }
    return [[nextKey, value]]
  })
}

export default function Inventory() {
  const [queryParams, setQueryParams] = useSearchParams()
  const [filters, setFilters] = useState(() => initialParams(queryParams))
  const [query, setQuery] = useState(queryParams.get('q') ?? '')
  const [page, setPage] = useState(1)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [summary, setSummary] = useState(null)
  const [summaryError, setSummaryError] = useState('')
  const [selectedMaterialId, setSelectedMaterialId] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')

    inventoryApi.list({ ...filters, page, page_size: PAGE_SIZE })
      .then((response) => {
        if (!active) return
        const parsed = getInventoryResponse(response)
        setItems(parsed.items)
        setTotal(parsed.total)
        setTotalPages(parsed.totalPages)
        if (!parsed.items.length) {
          setSelectedMaterialId(null)
          setSummary(null)
          return
        }
        if (!selectedMaterialId || !parsed.items.some((material) => getMaterialId(material) === selectedMaterialId)) {
          setSelectedMaterialId(getMaterialId(parsed.items[0]))
        }
      })
      .catch((requestError) => {
        if (!active) return
        setError(getErrorMessage(requestError, 'Could not load inventory.'))
        setItems([])
        setTotal(0)
        setTotalPages(0)
        setSelectedMaterialId(null)
        setSummary(null)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [filters, page, reloadKey])

  useEffect(() => {
    if (!selectedMaterialId) {
      setSummary(null)
      setSummaryError('')
      return
    }

    let active = true
    setSummaryError('')
    inventoryApi.getSummary(selectedMaterialId)
      .then((data) => {
        if (active) setSummary(data)
      })
      .catch((requestError) => {
        if (active) {
          setSummary(null)
          setSummaryError(getErrorMessage(requestError, 'Could not load the material summary.'))
        }
      })

    return () => {
      active = false
    }
  }, [selectedMaterialId])

  const filteredItems = useMemo(() => {
    const search = query.trim().toLowerCase()
    const baseItems = items.slice()
    if (!search) return baseItems
    return baseItems.filter((material) => {
      const values = [
        getMaterialId(material),
        getMaterialName(material),
        getPlantName(material),
        getWarehouseName(material),
        getStatus(material),
      ]
      return values.some((value) => String(value ?? '').toLowerCase().includes(search))
    })
  }, [items, query])

  const updateFilter = (key, value) => {
    setFilters((current) => ({ ...current, [key]: value }))
    setQueryParams((current) => {
      const next = new URLSearchParams(current)
      if (value) next.set(key, value)
      else next.delete(key)
      return next
    })
  }

  const resetFilters = () => {
    setFilters({ material_id: '', plant_id: '', warehouse_id: '', status: '', sort_by: 'material_id', sort_order: 'asc' })
    setQuery('')
    setQueryParams({})
    setPage(1)
  }

  const summaryEntries = useMemo(() => {
    const rows = flattenSummary(summary ?? {})
    return rows
      .filter(([, value]) => value !== null && value !== undefined && value !== '')
      .slice(0, 10)
  }, [summary])

  const alreadySelected = filteredItems.some((material) => getMaterialId(material) === selectedMaterialId)
  useEffect(() => {
    if (selectedMaterialId && !alreadySelected && filteredItems.length) {
      setSelectedMaterialId(getMaterialId(filteredItems[0]))
    }
  }, [alreadySelected, filteredItems, selectedMaterialId])

  const overviewCards = [
    { label: 'Total raw materials', value: total.toLocaleString() },
    { label: 'Records on page', value: filteredItems.length.toLocaleString() },
    { label: 'Distinct plants', value: new Set(items.map((material) => String(getPlantName(material))).filter((value) => value !== 'Unavailable')).size.toLocaleString() },
    { label: 'Latest snapshot', value: getSnapshotDate(filteredItems[0]) ?? 'Unavailable' },
  ]

  const columns = [
    {
      key: 'material_name',
      title: 'Material',
      render: (material) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <strong style={{ color: 'var(--text-primary)', fontSize: '13px', fontWeight: 600 }}>
            {getMaterialName(material)}
          </strong>
          <small
            style={{
              display: 'inline-block',
              fontSize: '11px',
              fontFamily: 'monospace',
              color: 'var(--brand-purple)',
              background: 'var(--brand-purple-soft)',
              padding: '2px 7px',
              borderRadius: '4px',
              width: 'fit-content',
            }}
          >
            {getMaterialId(material)}
          </small>
        </div>
      ),
    },
    { key: 'plant_name', title: 'Plant', render: (material) => getPlantName(material) },
    { key: 'warehouse_name', title: 'Warehouse', render: (material) => getWarehouseName(material) },
    {
      key: 'quantity',
      title: 'Available',
      render: (material) => (
        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
          {typeof getQuantity(material) === 'number' ? getQuantity(material).toLocaleString() : getQuantity(material)}
        </span>
      ),
    },
    {
      key: 'status',
      title: 'Status',
      render: (material) => {
        const status = getStatus(material)
        const isAvailable = status === 'AVAILABLE'
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '3px 8px',
              borderRadius: '999px',
              fontSize: '11px',
              fontWeight: 600,
              background: isAvailable ? 'rgba(34, 197, 94, 0.12)' : 'rgba(239, 68, 68, 0.12)',
              color: isAvailable ? '#16A34A' : '#DC2626',
            }}
          >
            {status}
          </span>
        )
      },
    },
    { key: 'snapshot_date', title: 'Snapshot', render: (material) => getSnapshotDate(material) },
  ]

  return (
    <div className="page-stack inventory-page">
      {error && <ErrorState title="Inventory unavailable" message={error} onRetry={() => setReloadKey((value) => value + 1)} />}

      <section
        className="card inventory-overview-grid"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
          padding: '20px',
          background: 'var(--surface-hi)',
          border: '1px solid var(--line)',
          borderRadius: '12px',
          marginBottom: '20px',
        }}
      >
        {overviewCards.map((card) => (
          <div
            key={card.label}
            className="mini-stat-card"
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              padding: '16px 18px',
              background: 'var(--kg-bg-2)',
              border: '1px solid var(--line)',
              borderRadius: '10px',
            }}
          >
            <span
              style={{
                color: 'var(--text-muted)',
                fontSize: '11px',
                fontWeight: 600,
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}
            >
              {card.label}
            </span>
            <strong
              style={{
                color: 'var(--text-primary)',
                fontSize: '24px',
                fontWeight: 700,
                lineHeight: 1.1,
              }}
            >
              {card.value}
            </strong>
          </div>
        ))}
      </section>

      <section className="card inventory-card">
        <div className="orders-toolbar">
          <div className="orders-toolbar-title"><span className="toolbar-icon"><Filter size={17} /></span><div><h2>Material inventory</h2><p>{total.toLocaleString()} records in this server result</p></div></div>
          <button className="text-button" onClick={resetFilters}><RotateCcw size={14} /> Reset filters</button>
        </div>

        <div className="filter-grid">
          <label className="filter-search"><Search size={16} /><Input bare value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by material, plant, warehouse or status" aria-label="Search inventory" /></label>
          <Input label="Material ID" value={filters.material_id} onChange={(event) => updateFilter('material_id', event.target.value)} placeholder="e.g. MAT-001" />
          <Input label="Plant ID" value={filters.plant_id} onChange={(event) => updateFilter('plant_id', event.target.value)} placeholder="e.g. PLANT-01" />
          <Input label="Warehouse ID" value={filters.warehouse_id} onChange={(event) => updateFilter('warehouse_id', event.target.value)} placeholder="e.g. WH-10" />
          <Select label="Status" value={filters.status} onChange={(event) => updateFilter('status', event.target.value)}>
            <option value="">All statuses</option>
            <option value="AVAILABLE">Available</option>
            <option value="LOW_STOCK">Low stock</option>
            <option value="RESTRICTED">Restricted</option>
            <option value="ON_HOLD">On hold</option>
          </Select>
          <Select label="Sort by" value={`${filters.sort_by}:${filters.sort_order}`} onChange={(event) => { const [sort_by, sort_order] = event.target.value.split(':'); setFilters((current) => ({ ...current, sort_by, sort_order })) }}>
            <option value="material_id:asc">Material ID: A–Z</option>
            <option value="material_id:desc">Material ID: Z–A</option>
            <option value="available_quantity:desc">Quantity: high to low</option>
            <option value="available_quantity:asc">Quantity: low to high</option>
            <option value="snapshot_date:desc">Latest snapshot</option>
          </Select>
        </div>

        {!error && (
          <>
            {filteredItems.length ? (
              <DataTable
                columns={columns}
                rows={filteredItems}
                getRowKey={(material) => getMaterialId(material)}
                loading={loading}
                emptyTitle="No inventory records found"
                emptyDescription="Try adjusting the search or filters."
                minWidth={860}
              />
            ) : (
              <EmptyState title="No inventory records found" description="Try adjusting the search or filters to find the raw material you need." />
            )}
            <div className="table-footer">
              <span>{total ? <>Showing <strong>{Math.min((page - 1) * PAGE_SIZE + 1, total)}–{Math.min(page * PAGE_SIZE, total)}</strong> of <strong>{total}</strong> records</> : 'No records'}</span>
              <div className="pagination">
                <button onClick={() => setPage((next) => Math.max(1, next - 1))} disabled={page <= 1 || loading} aria-label="Previous page">←</button>
                <span>Page <strong>{page}</strong> of <strong>{totalPages || 1}</strong></span>
                <button onClick={() => setPage((next) => next + 1)} disabled={page >= totalPages || loading} aria-label="Next page">→</button>
              </div>
            </div>
          </>
        )}
      </section>

      <section className="card inventory-detail-card">
        <div className="detail-section-heading"><Warehouse size={17} /><div><h2>Material summary</h2><p>Source summary for the selected raw material record</p></div></div>
        {summaryError ? <ErrorState title="Material summary unavailable" message={summaryError} /> : !selectedMaterialId || !summary ? (
          <EmptyState title="No material summary" description="Select a material row to inspect its summary details." />
        ) : (
          <div className="detail-fields">
            {summaryEntries.map(([label, value]) => (
              <div key={label}><span>{label}</span><strong>{String(value)}</strong></div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
