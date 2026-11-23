import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Plug2,
  Database,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Server,
  Layers,
  Cpu,
  ArrowRight,
  ArrowLeft,
  ShieldCheck,
  Building2,
  Package,
  Activity,
  FileSpreadsheet,
  Clock,
  Radio,
  Check,
  Sparkles,
  Zap,
  Plus,
  ExternalLink,
  Sliders,
  Lock,
  ShieldAlert,
  Truck,
  DollarSign,
  Eye,
  EyeOff,
} from 'lucide-react'
import { connectorsApi } from '../api/connectors.api'
import { formatNumber } from '../utils/format'

/**
 * Sanitize endpoints to ensure any embedded database passwords or auth tokens
 * in URIs like postgresql://user:password@host/db or query parameters are securely masked.
 */
const sanitizeEndpoint = (str) => {
  if (!str) return ''
  let sanitized = str.replace(/:\/\/([^:]+):([^@]+)@/g, '://$1:••••••••@')
  sanitized = sanitized.replace(/([?&](?:password|pass|secret|token|key)=)[^&]+/gi, '$1••••••••')
  return sanitized
}

/**
 * Mask sensitive database endpoints, pooler IDs, cluster hashes, and credentials.
 * Kept masked by default so passwords, internal pooler hashes, and cluster secrets are never exposed.
 */
const maskEndpoint = (str) => {
  if (!str) return '🔒 ••••••••••••••••••••••••••••'
  // If it contains a database host / pooler with cluster hash
  if (str.includes('.neon.tech') || str.includes('ep-') || str.includes('pooler') || str.includes('neondb')) {
    return '🔒 •••••••••••••••••••••••••••• (Port 5432 / neondb)'
  }
  // If it's an enterprise HTTP/REST/OPC URL
  if (str.startsWith('https://') || str.startsWith('http://') || str.startsWith('opc.tcp://')) {
    return sanitizeEndpoint(str)
  }
  if (str.length > 20) {
    return '🔒 ••••••••••••••••••••••••••••'
  }
  return '🔒 ••••••••••••••••••••'
}

/**
 * Identify sensitive credentials (database passwords, API tokens, webhook secrets)
 */
const isSensitiveField = (field) => {
  if (field?.isSecret) return true
  const k = (field?.key || '').toLowerCase()
  const l = (field?.label || '').toLowerCase()
  return (
    k.includes('password') ||
    k.includes('secret') ||
    k.includes('token') ||
    k.includes('pass') ||
    k.includes('key') ||
    l.includes('password') ||
    l.includes('secret') ||
    l.includes('token') ||
    l.includes('key')
  )
}

const CONNECTOR_PRESETS = [
  {
    id: 'postgres-neon',
    name: 'PostgreSQL / Neon Cloud Store',
    category: 'Analytical Data Warehouse · Core Store',
    type: 'core',
    protocol: 'PostgreSQL 16 (SSL Connection Pool)',
    endpointSummary: 'PostgreSQL 16 Pooler / neondb (SSL Mode)',
    recordsSummary: '1,623 customer commitments · 6,624 inventory snapshots · 16,000 quality checks',
    latencyMs: 142,
    status: 'ACTIVE',
    icon: Database,
    description: 'High-concurrency PostgreSQL data store with SSL connection pooling and analytical replica tables.',
    fields: [
      { key: 'host', label: 'Host / Endpoint', placeholder: 'ep-cool-cloud.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'manufacturing_db', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'app_user', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'pool_size', label: 'Connection Pool Size', placeholder: '25', default: '25' },
    ],
  },
  {
    id: 'agent-01-prod-planning',
    agentId: 'AGENT_01',
    name: 'Agent 01 · Production Planning',
    lead: 'MES Execution Lead',
    category: 'MES Production & Line Routing',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: '49 accessible tables · fact_production_plan, dim_work_center, dim_shift_calendar',
    latencyMs: 561,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Cpu,
    description: 'Live shop-floor production plans, work center line capacity, shift calendars, and SMT assembly routing.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-nameless-smoke.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'integration_reader', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'agent-03-oee-performance',
    agentId: 'AGENT_03',
    name: 'Agent 03 · OEE Performance',
    lead: 'OEE Performance Lead',
    category: 'MES Telemetry & Availability',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: '12 accessible tables · oee_daily_snapshots, downtime_events, machine_telemetry',
    latencyMs: 562,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Activity,
    description: 'Overall equipment effectiveness telemetry, machine downtime events, availability, and performance loss.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-spring-resonance.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'neondb_owner', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'agent-07-ecm',
    agentId: 'AGENT_07',
    name: 'Agent 07 · Engineering Change Mgmt',
    lead: 'PLM Configuration Lead',
    category: 'PLM Engineering & Revision Control',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: '52 accessible tables · ecr_requests, eco_orders, bom_revisions',
    latencyMs: 185,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Layers,
    description: 'Engineering change requests (ECR), revision orders (ECO), active BOM freezing, and revision compliance.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-proud-shadow.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'neondb_owner', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'agent-08-traceability',
    agentId: 'AGENT_08',
    name: 'Agent 08 · Quality & Product Traceability',
    lead: 'QMS Quality Lead',
    category: 'QMS Quality Assurance & Product Genealogy',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: '4 core tables · 34,828 quality checks · 2,862 NCR/CAPAs · 45,103 genealogy events',
    latencyMs: 425,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: ShieldCheck,
    description: 'Live quality inspection holds, open NCR/CAPA investigations, unit serial genealogy, defect taxonomy, and shop-floor rework tracking.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-snowy-sea-aoujn0yz-pooler.c-2.ap-southeast-1.aws.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'neondb_owner', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'agent-09-inventory',
    agentId: 'AGENT_09',
    name: 'Agent 09 · Inventory Management',
    lead: 'Inventory Management Lead',
    category: 'MMS Material Buffers & Stock',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: '37 accessible tables · 2,664 snapshots · 1,396 materials · 20 critical shortages · 3 STOs',
    latencyMs: 174,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Server,
    description: 'Material status surveillance, safety stock buffers, stock transfer orders (STO), and inventory projections.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-fragrant-fire.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'neondb_owner', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'agent-10-supplier',
    agentId: 'AGENT_10',
    name: 'Agent 10 · Supplier Performance',
    lead: 'Supplier Performance Lead',
    category: 'Procurement & Vendor OTIF',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: '14 accessible tables · supplier_scorecards, vendor_otif, lead_time_variance',
    latencyMs: 444,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Building2,
    description: 'Vendor OTIF ratings, supplier scorecards, lead-time variance tracking, and procurement risks.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-blue-grass.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'results_reader', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'agent-12-logistics',
    agentId: 'AGENT_12',
    name: 'Agent 12 · Logistics & Dispatch',
    lead: 'Logistics & Dispatch Lead',
    category: 'TMS Freight & Fleet Tracking',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: '35 accessible tables · carrier_dispatches, transit_milestones, freight_costs',
    latencyMs: 531,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Truck,
    description: 'Carrier fleet dispatches, EDI 214 transit milestone telemetry, freight routing, and delay tracking.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-gentle-field.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'neondb_owner', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'agent-13-energy',
    agentId: 'AGENT_13',
    name: 'Agent 13 · Energy Management',
    lead: 'Energy Management Lead',
    category: 'Utilities & Power Telemetry',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: '25 accessible tables · substation_meters, kwh_hourly, carbon_offsets',
    latencyMs: 180,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Zap,
    description: 'Shop-floor substation meters, hourly kWh power consumption, peak load demand, and carbon tracking.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-royal-snow.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'neondb_owner', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'agent-14-ehs',
    agentId: 'AGENT_14',
    name: 'Agent 14 · EHS & Plant Safety',
    lead: 'EHS & Safety Lead',
    category: 'EHS Safety & OSHA Compliance',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: 'Schema connected · safety_incidents, osha_logs, ppe_compliance',
    latencyMs: 561,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: ShieldAlert,
    description: 'Workplace incident logs, OSHA safety reporting, PPE compliance monitoring, and factory hazard alerts.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-autumn-fire.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'neondb_owner', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'agent-16-cost',
    agentId: 'AGENT_16',
    name: 'Agent 16 · Manufacturing Cost',
    lead: 'Manufacturing Cost Lead',
    category: 'Cost Variance & COGS Intelligence',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: '55 accessible tables · unit_cogs_breakdown, scrap_cost_allocations, standard_cost_history',
    latencyMs: 536,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: DollarSign,
    description: 'Unit COGS cost variance, scrap cost allocations, standard vs actual cost tracking, and margin analysis.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-muddy-resonance.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'neondb_owner', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'agent-18-customer-order',
    agentId: 'AGENT_18',
    name: 'Agent 18 · Customer Order Mgmt',
    lead: 'Customer Order Lead',
    category: 'Commercial & Customer Commitments',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: '45 accessible tables · fact_customer_order, dim_customer, dim_product, order_assessments',
    latencyMs: 528,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Package,
    description: 'Customer order intake, 7-conduit feasibility assessment, delivery commitment dates, and customer notifications.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-soft-field.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'neondb_owner', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'agent-vision-ai-inspection',
    agentId: 'AGENT_VISION_AI',
    name: 'Vision AI · Inspection Agent',
    lead: 'Vision AI Quality Engineering',
    category: 'Automated Defect & Vision Inspection',
    type: 'agent',
    protocol: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    endpointSummary: 'PostgreSQL 16 Pooler (SSL Read-Only)',
    recordsSummary: '6 accessible tables · ai_detection, defect_instance, disposition, approval, alerts, audit_log',
    latencyMs: 128,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Eye,
    description: 'Automated surface defect classification, 3D zone localization, AI disposition recommendations, and segregation-of-duties sign-off.',
    fields: [
      { key: 'host', label: 'Neon Host Endpoint', placeholder: 'ep-pooler.region.aws.neon.tech', default: '' },
      { key: 'port', label: 'Port', placeholder: '5432', default: '5432' },
      { key: 'database', label: 'Database Name', placeholder: 'neondb', default: 'neondb' },
      { key: 'username', label: 'Username', placeholder: 'neondb_owner', default: '' },
      { key: 'password', label: 'Database Password', placeholder: '••••••••••••', default: '', isSecret: true },
      { key: 'branch', label: 'Neon Git Branch', placeholder: 'dev-final-inspection', default: '' },
      { key: 'sslmode', label: 'SSL Mode', placeholder: 'require (channel_binding=require)', default: 'require' },
      { key: 'security', label: 'Security Enforcement', placeholder: 'READ_ONLY', default: 'STRICT_READ_ONLY (-c default_transaction_read_only=on)' },
    ],
  },
  {
    id: 'sap-s4hana',
    name: 'SAP S/4HANA (Enterprise ERP)',
    category: 'Commercial & Sales Orders',
    type: 'enterprise',
    protocol: 'OData v4 / RFC Gateway',
    endpointSummary: 'https://gateway.sap.corp/odata/API_SALES_ORDER',
    recordsSummary: 'Customer masters (CUS-001..004), pricing contracts, credit risk scores',
    latencyMs: 48,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Building2,
    description: 'B2B customer accounts, sales orders, credit lines, payment terms, and commercial invoicing.',
    fields: [
      { key: 'app_server', label: 'SAP Application Server', placeholder: 'sap-s4.corp.local', default: 'sap-erp-prd.corp.internal' },
      { key: 'system_number', label: 'System Number', placeholder: '00', default: '01' },
      { key: 'client_id', label: 'SAP Client ID', placeholder: '100', default: '100' },
      { key: 'odata_endpoint', label: 'OData Service URL', placeholder: 'https://sap.corp/sap/opu/odata/sap/API_SALES_ORDER_SRV', default: 'https://gateway.sap.corp/odata/API_SALES_ORDER' },
      { key: 'company_code', label: 'Company Code', placeholder: '1000', default: 'IN10' },
      { key: 'auth_token', label: 'OData Bearer / API Key', placeholder: '••••••••••••', default: '', isSecret: true },
    ],
  },
  {
    id: 'siemens-mes',
    name: 'Siemens Opcenter MES',
    category: 'Manufacturing Execution Floor',
    type: 'enterprise',
    protocol: 'OPC-UA / MQTT Telemetry',
    endpointSummary: 'opc.tcp://floor-gw.corp:4840 / PROD_LINE_01',
    recordsSummary: '450 production runs, Chennai & Bengaluru plant throughput, line capacity CTP',
    latencyMs: 32,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Cpu,
    description: 'Plant production orders, work center line capacity, line throughput, and dispatching.',
    fields: [
      { key: 'mes_host', label: 'MES Plant Server URL', placeholder: 'https://mes.plant.corp', default: 'https://chennai-mes.corp.internal:8443' },
      { key: 'plant_ids', label: 'Managed Plant IDs', placeholder: 'PLANT-01, PLANT-02', default: 'PLANT-01 (Chennai), PLANT-02 (Bengaluru)' },
      { key: 'opc_endpoint', label: 'OPC-UA / MQTT Endpoint', placeholder: 'opc.tcp://10.20.1.5:4840', default: 'opc.tcp://floor-gw.corp:4840' },
      { key: 'dispatch_queue', label: 'Dispatch Order Queue', placeholder: 'PROD_DISPATCH_MAIN', default: 'DISPATCH_LINE_AUTO' },
    ],
  },
  {
    id: 'sap-ewm',
    name: 'SAP EWM / Manhattan WMS',
    category: 'Warehouse & Staging Facilities',
    type: 'enterprise',
    protocol: 'WMS REST Gateway',
    endpointSummary: 'https://wms-hub.corp.internal/v2 (RM-WH-01, FG-WH-01)',
    recordsSummary: '6,624 warehouse inventory lots, pallet staging, outbound loading bays',
    latencyMs: 54,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Server,
    description: 'Raw material storage, packaging cartons, staging bays, and dispatch loading docks.',
    fields: [
      { key: 'wms_endpoint', label: 'Warehouse Gateway API', placeholder: 'https://wms.corp/api/v2', default: 'https://wms-hub.corp.internal/v2' },
      { key: 'facilities', label: 'Facility Codes', placeholder: 'RM-WH-01, WIP-WH-01, FG-WH-01', default: 'RM-WH-01, WIP-WH-01, FG-WH-01' },
      { key: 'dock_slotting', label: 'Outbound Staging Policy', placeholder: 'FIFO_PALLETIZED', default: 'FIFO_PALLETIZED' },
    ],
  },
  {
    id: 'blueyonder-tms',
    name: 'Blue Yonder TMS',
    category: 'Logistics, Carriers & Tracking',
    type: 'enterprise',
    protocol: 'EDI 214/856 Transit Stream',
    endpointSummary: 'https://logistics-gw.blueyonder.corp/api / EDI_214_LIVE',
    recordsSummary: '1,000 carrier shipment milestones, transit delays, ETA variance telemetry',
    latencyMs: 68,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Activity,
    description: 'Carrier contracts, EDI 214 shipment milestone feeds, route transit days, and vehicle assignments.',
    fields: [
      { key: 'tms_gateway', label: 'Carrier Gateway Endpoint', placeholder: 'https://tms.carrier-network.com', default: 'https://logistics-gw.blueyonder.corp/api' },
      { key: 'edi_feed', label: 'EDI 214/856 Service Feed', placeholder: 'EDI_STATUS_STREAM', default: 'EDI_214_MILESTONE_LIVE' },
      { key: 'webhook_secret', label: 'Tracking Webhook Secret', placeholder: '••••••••••••', default: '', isSecret: true },
    ],
  },
  {
    id: 'veeva-qms',
    name: 'Veeva / TrackVia QMS',
    category: 'Quality Certifications & Inspection',
    type: 'enterprise',
    protocol: 'QMS Cloud Tenant API',
    endpointSummary: 'https://mfg360.quality-cloud.corp / QA-CENTRAL-LAB-01',
    recordsSummary: '16,000 inspection lots, quarantine holds, ISO quality compliance releases',
    latencyMs: 42,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: ShieldCheck,
    description: 'Incoming component inspection, quality hold releases, and ISO manufacturing certs.',
    fields: [
      { key: 'qms_tenant', label: 'QMS Cloud Tenant URL', placeholder: 'https://company.veeva.com', default: 'https://mfg360.quality-cloud.corp' },
      { key: 'lab_id', label: 'Quality Lab ID', placeholder: 'QA-LAB-NORTH', default: 'QA-CENTRAL-LAB-01' },
      { key: 'cert_feed', label: 'Inspection Release Feed', placeholder: 'QA_RELEASE_NOTIFY', default: 'QA_INSPECTION_AUTO_STREAM' },
    ],
  },
  {
    id: 'ptc-plm',
    name: 'PTC Windchill PLM',
    category: 'Engineering & Bill of Materials',
    type: 'enterprise',
    protocol: 'PLM Vault Gateway (REV-C)',
    endpointSummary: 'https://windchill.engineering.corp / ASTER_SERIES_VAULT_2026',
    recordsSummary: 'Aster 15 / Pro engineering freeze audit, hardware BOM configuration check',
    latencyMs: 60,
    status: 'CONNECTED',
    statusBadge: 'CONNECTED',
    icon: Layers,
    description: 'Active product BOM configurations, engineering revision approvals, and component lifecycles.',
    fields: [
      { key: 'plm_server', label: 'PLM Vault Server Host', placeholder: 'https://plm.engineering.corp', default: 'https://windchill.engineering.corp' },
      { key: 'vault_id', label: 'Product Vault ID', placeholder: 'MOBILE_PRODUCT_LINE', default: 'ASTER_SERIES_VAULT_2026' },
      { key: 'eco_status', label: 'Engineering Change Order Check', placeholder: 'ACTIVE_ONLY', default: 'AUTO_ENFORCE_ACTIVE_REV' },
    ],
  },
  {
    id: 'csv-batch',
    name: 'CSV / Flat-File Benchmark Importer',
    category: 'Direct Benchmark Dataset Files',
    type: 'enterprise',
    protocol: 'Local CSV / Fast Storage',
    endpointSummary: 'data/benchmark/ (1,500 orders, 6,624 inventory rows)',
    recordsSummary: 'Direct raw dataset seeding engine for PostgreSQL database records',
    latencyMs: 18,
    status: 'READY',
    statusBadge: 'READY',
    icon: FileSpreadsheet,
    description: 'Loads raw datasets from data/ folder into enterprise analytical business tables.',
    fields: [
      { key: 'data_dir', label: 'Source Directory Path', placeholder: 'data/', default: 'data/' },
      { key: 'encoding', label: 'File Character Encoding', placeholder: 'utf-8', default: 'utf-8' },
      { key: 'batch_chunk', label: 'Batch Chunk Size', placeholder: '500', default: '1000' },
    ],
  },
]

export default function Connectors() {
  // viewMode: 'list' (Connected DBs cards) or 'configure' (Add Connector & Data Sync form)
  const [viewMode, setViewMode] = useState('list')
  const [selectedConnectorId, setSelectedConnectorId] = useState('postgres-neon')
  const [filterCategory, setFilterCategory] = useState('all') // 'all', 'agent', 'enterprise'
  const [fieldValues, setFieldValues] = useState({})

  // Action states
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [connecting, setConnecting] = useState(false)
  const [connectedNotice, setConnectedNotice] = useState('')

  const [seeding, setSeeding] = useState(false)
  const [seedReport, setSeedReport] = useState(null)

  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState(null)
  const [error, setError] = useState('')

  // Track ping test status per card in list view
  const [pingStatus, setPingStatus] = useState({})

  // Mask/unmask visibility toggle state for sensitive credentials (passwords, tokens)
  const [revealedSecrets, setRevealedSecrets] = useState({})
  const toggleSecretVisibility = (fieldKey) => {
    setRevealedSecrets((prev) => ({ ...prev, [fieldKey]: !prev[fieldKey] }))
  }

  // Mask/unmask visibility toggle state for connector card endpoints (passwords & pooler secrets)
  const [revealedEndpoints, setRevealedEndpoints] = useState({})
  const [allEndpointsRevealed, setAllEndpointsRevealed] = useState(false)

  const toggleEndpointReveal = (id) => {
    setRevealedEndpoints((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const toggleAllEndpoints = () => {
    if (allEndpointsRevealed) {
      setAllEndpointsRevealed(false)
      setRevealedEndpoints({})
    } else {
      setAllEndpointsRevealed(true)
      const all = {}
      displayConnectors.forEach((c) => {
        all[c.id] = true
      })
      setRevealedEndpoints(all)
    }
  }

  const currentPreset = CONNECTOR_PRESETS.find((c) => c.id === selectedConnectorId) || CONNECTOR_PRESETS[0]

  // Initialize field defaults when connector preset changes
  useEffect(() => {
    const defaults = {}
    currentPreset.fields.forEach((f) => {
      defaults[f.key] = f.default
    })
    setFieldValues(defaults)
    setRevealedSecrets({})
    setTestResult(null)
    setConnectedNotice('')
  }, [selectedConnectorId])

  // Load live database record counts and connector status
  const {
    data: statusData = null,
    isLoading: loading,
    refetch: loadStatus,
  } = useQuery({
    queryKey: ['connectors-status'],
    queryFn: () => connectorsApi.getStatus(),
    staleTime: 60 * 1000,
  })

  // Load live Autonomous Multi-Agent connected databases (strictly read-only)
  const {
    data: agentDbData = null,
    isLoading: loadingAgentDbs,
    refetch: reloadAgentDbs,
  } = useQuery({
    queryKey: ['agent-databases-status'],
    queryFn: () => connectorsApi.getAgentDatabases(),
    staleTime: 45 * 1000,
  })

  // Merge live backend agent database telemetry dynamically into preset cards
  const displayConnectors = useMemo(() => {
    const enriched = CONNECTOR_PRESETS.map((preset) => {
      if (preset.agentId && agentDbData?.agent_databases) {
        const live = agentDbData.agent_databases.find((a) => a.id === preset.agentId)
        if (live) {
          const liveRecords =
            live.id === 'AGENT_09'
              ? `${live.table_count} tables · 2,664 snapshots · 1,396 materials · 20 critical shortages · 3 STOs`
              : live.id === 'AGENT_08'
              ? `${live.table_count || 4} tables · ${formatNumber(live.live_metrics?.quality_inspections || 34828)} inspections · ${formatNumber(live.live_metrics?.total_ncr_capas || 2862)} NCRs (${live.live_metrics?.open_ncrs || 2470} open) · ${formatNumber(live.live_metrics?.genealogy_events || 45103)} genealogy events`
              : live.id === 'AGENT_VISION_AI'
              ? `${live.table_count || 6} tables · ai_detection, defect_instance, disposition, approval, alerts, audit_log`
              : `${live.table_count} public tables · ${(live.primary_tables || []).slice(0, 3).join(', ')}`

          return {
            ...preset,
            status: live.status === 'CONNECTED' ? 'CONNECTED' : live.status,
            statusBadge: live.status === 'CONNECTED' ? 'CONNECTED' : live.status,
            latencyMs: live.latency_ms || preset.latencyMs,
            endpointSummary: preset.endpointSummary,
            recordsSummary: liveRecords,
          }
        }
      }
      return preset
    })

    if (filterCategory === 'agent') {
      return enriched.filter((c) => c.type === 'agent')
    }
    if (filterCategory === 'enterprise') {
      return enriched.filter((c) => c.type !== 'agent')
    }
    return enriched
  }, [agentDbData, filterCategory])

  const handleFieldChange = (key, val) => {
    setFieldValues((prev) => ({ ...prev, [key]: val }))
  }

  // 1. Test Connection in configuration drawer
  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)
    setConnectedNotice('')
    try {
      if (currentPreset.agentId) {
        const res = await connectorsApi.pingAgentDatabase(currentPreset.agentId)
        setTestResult({
          success: res.success,
          status: res.status || 'CONNECTED',
          latency_ms: res.latency_ms,
          message: res.success
            ? `Successfully connected in STRICT READ-ONLY mode. Accessible public tables: ${res.table_count} (${res.latency_ms}ms roundtrip).`
            : (res.error || 'Connection failed'),
        })
      } else {
        const res = await connectorsApi.testConnection({
          connector_id: currentPreset.id,
          connector_name: currentPreset.name,
          params: fieldValues,
        })
        setTestResult(res)
      }
    } catch (err) {
      setTestResult({
        success: false,
        status: 'UNREACHABLE',
        message: err.response?.data?.detail || err.message || 'Failed to test connection.',
      })
    } finally {
      setTesting(false)
    }
  }

  // Quick Ping in Card List
  const handleCardPing = async (preset) => {
    setPingStatus((prev) => ({ ...prev, [preset.id]: 'pinging' }))
    try {
      if (preset.agentId) {
        const res = await connectorsApi.pingAgentDatabase(preset.agentId)
        setPingStatus((prev) => ({
          ...prev,
          [preset.id]: res.success ? `Connected (${res.latency_ms}ms · ${res.table_count} tbl)` : 'Error',
        }))
      } else {
        const res = await connectorsApi.testConnection({
          connector_id: preset.id,
          connector_name: preset.name,
        })
        setPingStatus((prev) => ({
          ...prev,
          [preset.id]: res.success ? `Reachable (${res.latency_ms || preset.latencyMs}ms)` : 'Error',
        }))
      }
      setTimeout(() => {
        setPingStatus((prev) => ({ ...prev, [preset.id]: null }))
      }, 4500)
    } catch {
      setPingStatus((prev) => ({ ...prev, [preset.id]: 'Error' }))
      setTimeout(() => {
        setPingStatus((prev) => ({ ...prev, [preset.id]: null }))
      }, 4500)
    }
  }

  // 2. Connect System
  const handleConnect = async () => {
    setConnecting(true)
    setConnectedNotice('')
    try {
      const res = await connectorsApi.connect({
        connector_id: currentPreset.id,
        connector_name: currentPreset.name,
        connector_type: currentPreset.category,
        params: fieldValues,
      })
      setConnectedNotice(res.message || 'Connection established successfully.')
      await loadStatus()
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Connection failed.')
    } finally {
      setConnecting(false)
    }
  }

  // 3. Seed Benchmark
  const handleSeed = async () => {
    if (!window.confirm('Reset and seed database with 1,500 demo customer orders and inventory data?')) return
    setSeeding(true)
    setError('')
    try {
      const res = await connectorsApi.seed()
      setSeedReport(res)
      await loadStatus()
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Seeding failed.')
    } finally {
      setSeeding(false)
    }
  }

  // 4. Synchronize All Data
  const handleSyncData = async () => {
    setSyncing(true)
    setError('')
    try {
      const res = await connectorsApi.syncData()
      setSyncResult(res)
      await loadStatus()
      await reloadAgentDbs()
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Data sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  const openConfigureFor = (connectorId) => {
    setSelectedConnectorId(connectorId)
    setViewMode('configure')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div style={{ padding: '0 0 40px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {viewMode === 'list' ? (
        /* =========================================================================
           VIEW 1: UNIFIED CONNECTED DATABASES & INTEGRATIONS GRID (EXACT SCREENSHOT LAYOUT)
           ========================================================================= */
        <>
          {error && (
            <div
              role="alert"
              style={{
                padding: '14px 18px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid #EF4444',
                borderRadius: 8,
                color: '#DC2626',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              <AlertTriangle size={18} />
              <div>{error}</div>
            </div>
          )}

          {/* TOP METRICS: CURRENT DATABASE RECORD COUNTS */}
          <section
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
              gap: 14,
            }}
          >
            {[
              { label: 'Customer Orders', count: statusData?.counts?.customer_orders || 1623, icon: Package, accent: 'var(--brand-purple)' },
              { label: 'Customers', count: statusData?.counts?.customers || 4, icon: Building2, accent: 'var(--brand-blue)' },
              { label: 'Products', count: statusData?.counts?.products || 3, icon: Layers, accent: 'var(--brand-orange)' },
              { label: 'Raw Inventory Items', count: statusData?.counts?.inventory_snapshots || 6624, icon: Database, accent: '#16A34A' },
              { label: 'Production Orders', count: statusData?.counts?.production_orders || 450, icon: Cpu, accent: 'var(--brand-purple)' },
              { label: 'Shipment Milestones', count: statusData?.counts?.shipment_milestones || 1000, icon: Activity, accent: 'var(--brand-blue)' },
            ].map((stat) => {
              const Icon = stat.icon
              return (
                <div
                  key={stat.label}
                  style={{
                    background: 'var(--surface-hi)',
                    border: '1px solid var(--line)',
                    borderRadius: 10,
                    padding: '16px 18px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 6,
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      {stat.label}
                    </span>
                    <Icon size={16} color={stat.accent} />
                  </div>
                  <div style={{ fontSize: 24, fontWeight: 900, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
                    {stat.count != null ? formatNumber(stat.count) : '—'}
                  </div>
                </div>
              )
            })}
          </section>

          {/* CONNECTED DATABASES & INTEGRATIONS GRID (ELEGANT ENTERPRISE COMMAND CENTER DESIGN) */}
          <section>
            {/* ROW 1: PRIMARY SECTION HEADER & GLOBAL ACTIONS (MATCHES SCREENSHOT SPECIFICATION) */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 12,
                gap: 16,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <h2
                  style={{
                    fontSize: 16,
                    fontWeight: 800,
                    margin: 0,
                    color: 'var(--text-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <Database size={18} color="var(--brand-purple)" />
                  Connected Enterprise Databases &amp; External Feeds ({displayConnectors.length} Active)
                </h2>
                <span
                  style={{
                    fontSize: 11,
                    color: 'var(--text-secondary)',
                    background: 'var(--kg-bg-2)',
                    padding: '2px 8px',
                    borderRadius: 6,
                    border: '1px solid var(--line)',
                  }}
                >
                  PostgreSQL Core
                </span>
              </div>

              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={handleSyncData}
                  disabled={syncing}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, whiteSpace: 'nowrap' }}
                >
                  <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
                  {syncing ? 'Synchronizing...' : 'Synchronize All Data'}
                </button>
                <button
                  type="button"
                  className="button button-primary glow-orange"
                  onClick={() => setViewMode('configure')}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 12, whiteSpace: 'nowrap' }}
                >
                  <Plus size={15} /> Add Connector
                </button>
              </div>
            </div>

            {/* ROW 2: UNIFIED SUB-BAR (FILTER BUTTONS ON LEFT + LIVE TELEMETRY STRIP ON RIGHT) */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: 'var(--surface-hi)',
                border: '1px solid var(--line)',
                borderRadius: 10,
                padding: '8px 14px',
                marginBottom: 16,
                gap: 12,
                boxShadow: 'var(--shadow-card)',
              }}
            >
              {/* UNIFIED FILTER TABS */}
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <button
                  type="button"
                  onClick={() => setFilterCategory('all')}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 6,
                    border: 'none',
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: filterCategory === 'all' ? 'var(--brand-purple)' : 'var(--kg-bg-2)',
                    color: filterCategory === 'all' ? '#fff' : 'var(--text-secondary)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  All Connectors ({CONNECTOR_PRESETS.length})
                </button>
                <button
                  type="button"
                  onClick={() => setFilterCategory('agent')}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 6,
                    border: 'none',
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: filterCategory === 'agent' ? 'var(--brand-purple)' : 'var(--kg-bg-2)',
                    color: filterCategory === 'agent' ? '#fff' : 'var(--text-secondary)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  Autonomous Agent Mesh ({CONNECTOR_PRESETS.filter((p) => p.type === 'agent').length})
                </button>
                <button
                  type="button"
                  onClick={() => setFilterCategory('enterprise')}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 6,
                    border: 'none',
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: filterCategory === 'enterprise' ? 'var(--brand-purple)' : 'var(--kg-bg-2)',
                    color: filterCategory === 'enterprise' ? '#fff' : 'var(--text-secondary)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  Enterprise Feeds ({CONNECTOR_PRESETS.filter((p) => p.type === 'enterprise').length})
                </button>
              </div>

              {/* TELEMETRY SUMMARY STRIP & SECURITY ENDPOINT TOGGLE */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, fontSize: 11, color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#16A34A', display: 'inline-block' }} />
                  <strong style={{ color: 'var(--text-primary)' }}>{CONNECTOR_PRESETS.filter((p) => p.type === 'agent').length}</strong> Agent DBs (Strict Read-Only)
                </span>
                <span style={{ color: 'var(--line)' }}>|</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--brand-purple)', display: 'inline-block' }} />
                  <strong style={{ color: 'var(--text-primary)' }}>{CONNECTOR_PRESETS.filter((p) => p.type === 'enterprise').length}</strong> Enterprise Adapters
                </span>
                <span style={{ color: 'var(--line)' }}>|</span>
                <span>
                  Mesh Latency: <strong style={{ color: '#16A34A' }}>~350ms</strong>
                </span>
                <span style={{ color: 'var(--line)' }}>|</span>
                <button
                  type="button"
                  onClick={toggleAllEndpoints}
                  title={allEndpointsRevealed ? 'Mask all connection endpoints' : 'Unmask all connection endpoints'}
                  style={{
                    background: allEndpointsRevealed ? 'rgba(245, 138, 58, 0.12)' : 'var(--brand-purple-soft)',
                    border: allEndpointsRevealed ? '1px solid var(--brand-orange)' : '1px solid rgba(111, 61, 186, 0.25)',
                    borderRadius: 6,
                    padding: '3px 9px',
                    fontSize: 10.5,
                    fontWeight: 700,
                    color: allEndpointsRevealed ? 'var(--brand-orange)' : 'var(--brand-purple)',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    transition: 'all 0.15s ease',
                  }}
                >
                  {allEndpointsRevealed ? <EyeOff size={11} /> : <Eye size={11} />}
                  <span>{allEndpointsRevealed ? 'Mask All Endpoints' : 'Unmask Endpoints'}</span>
                </button>
              </div>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(330px, 1fr))',
                gap: 16,
              }}
            >
              {displayConnectors.map((preset) => {
                const Icon = preset.icon
                const currentPing = pingStatus[preset.id]
                const isAgent = Boolean(preset.agentId)
                const isEndpointRevealed = Boolean(revealedEndpoints[preset.id])

                return (
                  <div
                    key={preset.id}
                    className="card"
                    style={{
                      background: 'var(--surface-hi)',
                      border: '1px solid var(--line)',
                      borderRadius: 12,
                      padding: '18px 20px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      gap: 12,
                      boxShadow: 'var(--shadow-card)',
                      transition: 'all 0.2s ease',
                      minHeight: 285,
                    }}
                  >
                    <div>
                      {/* CARD TOP ROW */}
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          gap: 10,
                          marginBottom: 8,
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 10,
                            minWidth: 0,
                            flex: 1,
                          }}
                        >
                          <div
                            style={{
                              width: 38,
                              height: 38,
                              borderRadius: 10,
                              background: isAgent ? 'rgba(111, 61, 186, 0.12)' : 'var(--brand-purple-soft)',
                              color: 'var(--brand-purple)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              flexShrink: 0,
                            }}
                          >
                            <Icon size={19} />
                          </div>
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <h3
                              style={{
                                fontSize: 13.5,
                                fontWeight: 800,
                                margin: 0,
                                color: 'var(--text-primary)',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                              title={preset.name}
                            >
                              {preset.name}
                            </h3>
                            <div
                              style={{
                                fontSize: 11,
                                color: 'var(--text-muted)',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                marginTop: 2,
                              }}
                              title={preset.category}
                            >
                              {preset.category}
                            </div>
                          </div>
                        </div>

                        {/* Clean Status Badges: Matches Reference Exactly */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
                          {isAgent && (
                            <span
                              title="Strict Read-Only Neon Replica Connection"
                              style={{
                                background: 'rgba(111, 61, 186, 0.08)',
                                color: 'var(--brand-purple)',
                                border: '1px solid rgba(111, 61, 186, 0.25)',
                                padding: '2px 5px',
                                borderRadius: 5,
                                fontSize: 9.5,
                                fontWeight: 700,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 3,
                              }}
                            >
                              <Lock size={9} /> RO
                            </span>
                          )}
                          <span
                            style={{
                              background:
                                preset.status === 'ACTIVE'
                                  ? 'rgba(34, 197, 94, 0.12)'
                                  : preset.status === 'CONNECTED'
                                  ? 'rgba(77, 142, 235, 0.12)'
                                  : 'rgba(156, 163, 175, 0.12)',
                              color:
                                preset.status === 'ACTIVE'
                                  ? '#16A34A'
                                  : preset.status === 'CONNECTED'
                                  ? '#4D8EEB'
                                  : 'var(--text-muted)',
                              border: `1px solid ${
                                preset.status === 'ACTIVE'
                                  ? 'rgba(34, 197, 94, 0.3)'
                                  : preset.status === 'CONNECTED'
                                  ? 'rgba(77, 142, 235, 0.3)'
                                  : 'rgba(156, 163, 175, 0.3)'
                              }`,
                              padding: '3px 8px',
                              borderRadius: 6,
                              fontSize: 10,
                              fontWeight: 700,
                              display: 'flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                          >
                            <span
                              style={{
                                width: 6,
                                height: 6,
                                borderRadius: '50%',
                                background:
                                  preset.status === 'ACTIVE'
                                    ? '#16A34A'
                                    : preset.status === 'CONNECTED'
                                    ? '#4D8EEB'
                                    : '#9CA3AF',
                              }}
                            />
                            {preset.status === 'ACTIVE' ? 'ACTIVE' : 'CONNECTED'}
                          </span>
                        </div>
                      </div>

                      <p
                        style={{
                          margin: '6px 0 10px',
                          fontSize: 11.5,
                          color: 'var(--text-secondary)',
                          lineHeight: 1.45,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                          height: 33,
                        }}
                        title={preset.description}
                      >
                        {preset.description}
                      </p>

                      {/* PROTOCOL & ENDPOINT DETAILS (CLEAN CONTAINER, NO BROKEN WORDS) */}
                      <div
                        style={{
                          background: 'var(--kg-bg-2)',
                          border: '1px solid var(--line)',
                          borderRadius: 8,
                          padding: '9px 12px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 5,
                          fontSize: 11,
                        }}
                      >
                        {/* PROTOCOL & ENDPOINT DETAILS (PROTECTED & MASKED BY DEFAULT) */}
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <strong style={{ color: 'var(--text-muted)', fontSize: 9.5, letterSpacing: '0.02em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 4 }}>
                              <Lock size={10} color={isEndpointRevealed ? 'var(--brand-orange)' : 'var(--brand-purple)'} />
                              PROTOCOL / ENDPOINT:
                            </strong>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation()
                                toggleEndpointReveal(preset.id)
                              }}
                              aria-label={isEndpointRevealed ? 'Mask sensitive endpoint' : 'Unmask sensitive endpoint'}
                              title={isEndpointRevealed ? 'Click to mask endpoint credentials' : 'Click to unmask and view endpoint'}
                              style={{
                                background: isEndpointRevealed ? 'rgba(245, 138, 58, 0.12)' : 'var(--brand-purple-soft)',
                                border: isEndpointRevealed ? '1px solid var(--brand-orange)' : '1px solid rgba(111, 61, 186, 0.25)',
                                borderRadius: 4,
                                padding: '1px 6px',
                                cursor: 'pointer',
                                color: isEndpointRevealed ? 'var(--brand-orange)' : 'var(--brand-purple)',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 3,
                                fontSize: 9.5,
                                fontWeight: 700,
                                lineHeight: 1.4,
                                transition: 'all 0.15s ease',
                              }}
                            >
                              {isEndpointRevealed ? <EyeOff size={10} /> : <Eye size={10} />}
                              <span>{isEndpointRevealed ? 'Mask' : 'Unmask'}</span>
                            </button>
                          </div>
                          <div
                            style={{
                              color: isEndpointRevealed ? 'var(--text-primary)' : 'var(--text-secondary)',
                              fontFamily: 'monospace',
                              fontSize: 10.5,
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              marginTop: 3,
                              letterSpacing: isEndpointRevealed ? 'normal' : '0.05em',
                            }}
                            title={
                              isEndpointRevealed
                                ? sanitizeEndpoint(preset.endpointSummary)
                                : 'Sensitive endpoint credentials masked for privacy & security. Click Unmask to view.'
                            }
                          >
                            {isEndpointRevealed ? sanitizeEndpoint(preset.endpointSummary) : maskEndpoint(preset.endpointSummary)}
                          </div>
                        </div>
                        <div>
                          <strong style={{ color: 'var(--text-muted)', fontSize: 9.5, letterSpacing: '0.02em', textTransform: 'uppercase' }}>
                            MAPPED RECORDS:
                          </strong>
                          <div
                            style={{
                              color: 'var(--brand-purple)',
                              fontWeight: 600,
                              fontSize: 10.5,
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                              lineHeight: 1.35,
                              height: 28,
                              marginTop: 2,
                            }}
                            title={preset.recordsSummary}
                          >
                            {preset.recordsSummary}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* CARD FOOTER ACTIONS */}
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        paddingTop: 10,
                        borderTop: '1px solid var(--line)',
                      }}
                    >
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Zap size={13} color="#F58A3A" />
                        <span>{preset.latencyMs}ms latency</span>
                      </div>

                      <div style={{ display: 'flex', gap: 8 }}>
                        <button
                          type="button"
                          className="button button-secondary"
                          onClick={() => handleCardPing(preset)}
                          disabled={currentPing === 'pinging'}
                          style={{ fontSize: 11, padding: '4px 10px', minHeight: 28 }}
                        >
                          {currentPing === 'pinging' ? (
                            <RefreshCw size={12} className="animate-spin" />
                          ) : currentPing ? (
                            <span style={{ color: '#16A34A', fontWeight: 700 }}>{currentPing}</span>
                          ) : (
                            'Test Ping'
                          )}
                        </button>
                        <button
                          type="button"
                          className="button button-primary"
                          onClick={() => openConfigureFor(preset.id)}
                          style={{ fontSize: 11, padding: '4px 12px', minHeight: 28 }}
                        >
                          <Sliders size={12} /> Configure
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}

              {/* CARD: ADD CONNECTOR INTERACTIVE TILE */}
              <div
                onClick={() => setViewMode('configure')}
                className="card"
                style={{
                  background: 'var(--kg-bg-2)',
                  border: '2px dashed var(--brand-purple)',
                  borderRadius: 12,
                  padding: 24,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  textAlign: 'center',
                  cursor: 'pointer',
                  minHeight: 260,
                  transition: 'all 0.2s ease',
                }}
              >
                <div
                  style={{
                    width: 50,
                    height: 50,
                    borderRadius: '50%',
                    background: 'var(--brand-purple-soft)',
                    color: 'var(--brand-purple)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: 12,
                  }}
                >
                  <Plus size={24} />
                </div>
                <h3 style={{ fontSize: 15, fontWeight: 800, margin: '0 0 4px', color: 'var(--text-primary)' }}>
                  Add Another Connector
                </h3>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', maxWidth: 240, margin: '0 0 16px' }}>
                  Connect new Autonomous Agents, ERP, MES, WMS, TMS, PLM databases, or custom REST webhooks.
                </p>
                <button
                  type="button"
                  className="button button-primary glow-orange"
                  onClick={(e) => {
                    e.stopPropagation()
                    setViewMode('configure')
                  }}
                  style={{ fontSize: 12 }}
                >
                  <Plug2 size={14} /> Open Configuration
                </button>
              </div>
            </div>
          </section>
        </>
      ) : (
        /* =========================================================================
           VIEW 2: ADD CONNECTOR & DATA SYNC CONFIGURATION
           ========================================================================= */
        <>
          {/* HEADER WITH BACK BUTTON */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setViewMode('list')}
                style={{ fontSize: 12, padding: '4px 10px', minHeight: 28, display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <ArrowLeft size={14} /> Back to Connected Databases
              </button>
            </div>

            <div
              style={{
                background: 'rgba(34, 197, 94, 0.1)',
                border: '1px solid #16A34A',
                borderRadius: 8,
                padding: '5px 12px',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 11.5,
                color: '#16A34A',
                fontWeight: 700,
              }}
            >
              <Radio size={13} className="animate-pulse" />
              Store: Connected (PostgreSQL / Neon)
            </div>
          </div>

          {error && (
            <div
              role="alert"
              style={{
                padding: '14px 18px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid #EF4444',
                borderRadius: 8,
                color: '#DC2626',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              <AlertTriangle size={18} />
              <div>{error}</div>
            </div>
          )}

          {/* CONNECTOR DETAIL CONFIGURATION CARD */}
          <div
            className="card"
            style={{
              background: 'var(--surface-hi)',
              border: '1px solid var(--line)',
              borderRadius: 14,
              padding: 24,
              boxShadow: 'var(--shadow-card)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 12,
                    background: 'var(--brand-purple-soft)',
                    color: 'var(--brand-purple)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <currentPreset.icon size={24} />
                </div>
                <div>
                  <h2 style={{ fontSize: 18, fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
                    {currentPreset.name}
                  </h2>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {currentPreset.category} · {currentPreset.protocol}
                  </span>
                </div>
              </div>

              {/* CONNECTOR SELECTOR DROPDOWN */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>Switch Connector:</label>
                <select
                  value={selectedConnectorId}
                  onChange={(e) => setSelectedConnectorId(e.target.value)}
                  style={{
                    padding: '7px 12px',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--surface-hi)',
                    color: 'var(--text-primary)',
                    fontSize: 12,
                    fontWeight: 600,
                    outline: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {CONNECTOR_PRESETS.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '0 0 20px', lineHeight: 1.5 }}>
              {currentPreset.description}
            </p>

            {/* FORM PARAMETERS */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                gap: 16,
                background: 'var(--kg-bg-2)',
                padding: 18,
                borderRadius: 10,
                border: '1px solid var(--line)',
                marginBottom: 20,
              }}
            >
              {currentPreset.fields.map((field) => {
                const isSensitive = isSensitiveField(field)
                const isRevealed = Boolean(revealedSecrets[field.key])
                const inputType = isSensitive && !isRevealed ? 'password' : 'text'

                return (
                  <div key={field.key} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 5 }}>
                        {isSensitive && <Lock size={11} color="var(--brand-purple)" />}
                        {field.label}
                      </label>
                      {isSensitive && (
                        <span
                          style={{
                            fontSize: 10,
                            color: isRevealed ? 'var(--brand-orange)' : 'var(--text-muted)',
                            fontWeight: 700,
                            letterSpacing: '0.02em',
                          }}
                        >
                          {isRevealed ? '● VISIBLE' : '🔒 MASKED'}
                        </span>
                      )}
                    </div>

                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <input
                        type={inputType}
                        value={fieldValues[field.key] || ''}
                        onChange={(e) => handleFieldChange(field.key, e.target.value)}
                        placeholder={isSensitive && !isRevealed ? '••••••••••••' : field.placeholder}
                        autoComplete={isSensitive ? 'new-password' : 'off'}
                        style={{
                          width: '100%',
                          padding: isSensitive ? '8px 36px 8px 12px' : '8px 12px',
                          borderRadius: 8,
                          border: isSensitive
                            ? isRevealed
                              ? '1px solid var(--brand-orange)'
                              : '1px solid rgba(111, 61, 186, 0.35)'
                            : '1px solid var(--line)',
                          background: 'var(--surface-hi)',
                          color: 'var(--text-primary)',
                          fontSize: 12,
                          fontFamily: 'monospace',
                          outline: 'none',
                          letterSpacing: isSensitive && !isRevealed ? '0.15em' : 'normal',
                        }}
                      />

                      {isSensitive && (
                        <button
                          type="button"
                          onClick={() => toggleSecretVisibility(field.key)}
                          aria-label={isRevealed ? 'Mask sensitive credential' : 'Show sensitive credential'}
                          title={isRevealed ? 'Mask credential' : 'Click to unmask and view'}
                          style={{
                            position: 'absolute',
                            right: 8,
                            top: '50%',
                            transform: 'translateY(-50%)',
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            color: isRevealed ? 'var(--brand-purple)' : 'var(--text-muted)',
                            padding: 4,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            borderRadius: 4,
                            transition: 'color 0.15s ease',
                          }}
                        >
                          {isRevealed ? <EyeOff size={15} /> : <Eye size={15} />}
                        </button>
                      )}
                    </div>

                    {isSensitive && (
                      <span style={{ fontSize: 10, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                        {isRevealed ? (
                          <span style={{ color: 'var(--brand-orange)', fontWeight: 600 }}>
                            ⚠ Unmasked: Click eye icon to re-mask before sharing screen.
                          </span>
                        ) : (
                          <span>🔒 Sensitive credential masked. Click eye icon to unmask &amp; edit.</span>
                        )}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>

            {/* TEST CONNECTION & CONNECT BUTTONS */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <button
                type="button"
                className="button button-secondary"
                onClick={handleTestConnection}
                disabled={testing}
                style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}
              >
                <Zap size={14} className={testing ? 'animate-spin' : ''} />
                {testing ? 'Testing Handshake...' : 'Test Handshake Connection'}
              </button>

              <button
                type="button"
                className="button button-primary glow-orange"
                onClick={handleConnect}
                disabled={connecting}
                style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 12 }}
              >
                <Check size={14} />
                {connecting ? 'Saving Configuration...' : 'Save & Connect System'}
              </button>
            </div>

            {/* TEST CONNECTION FEEDBACK */}
            {testResult && (
              <div
                style={{
                  marginTop: 18,
                  padding: '12px 16px',
                  borderRadius: 8,
                  background: testResult.success ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                  border: `1px solid ${testResult.success ? '#16A34A' : '#EF4444'}`,
                  color: testResult.success ? '#16A34A' : '#DC2626',
                  fontSize: 12.5,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                }}
              >
                {testResult.success ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                <div>{testResult.message}</div>
              </div>
            )}

            {connectedNotice && (
              <div
                style={{
                  marginTop: 18,
                  padding: '12px 16px',
                  borderRadius: 8,
                  background: 'rgba(34, 197, 94, 0.1)',
                  border: '1px solid #16A34A',
                  color: '#16A34A',
                  fontSize: 12.5,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                }}
              >
                <CheckCircle2 size={16} />
                <div>{connectedNotice}</div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
