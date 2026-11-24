import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Layers,
  LayoutDashboard,
  Server,
  Database,
  Cloud,
  FileSpreadsheet,
  Wrench,
  Calendar,
  Clock,
  BarChart3,
  Users,
  ExternalLink,
  ArrowUpRight,
  Maximize2,
  Minimize2,
  Factory,
  Cpu,
  FileText,
  Activity,
  CheckCircle2,
  Check,
  ChevronRight,
  ShieldCheck,
  Shield,
  ShieldAlert,
  Bot,
  Mail,
  Zap,
  Building2,
  Warehouse,
  Truck,
  Sparkles,
  Lock,
  AlertTriangle,
  Flame,
  ArrowRight,
  Info,
  CheckSquare,
  RefreshCw,
  Code,
  Terminal,
  Bell,
  Target,
  TrendingUp,
  Send,
} from 'lucide-react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from 'recharts'
import { dashboardApi } from '../api/dashboard.api'
import { formatINR } from '../utils/format'

// Enterprise Architecture Graphic Assets
import erpMmsImg from '../assets/architecture/erp_mms.png'
import mesWmsImg from '../assets/architecture/mes_wms.png'
import qmsTmsImg from '../assets/architecture/qms_tms.png'
import fastapiGatewayImg from '../assets/architecture/fastapi_gateway.png'
import agent1AssistantImg from '../assets/architecture/agent1_assistant.png'
import agent2FeasibilityImg from '../assets/architecture/agent2_feasibility.png'
import agent3SurveillanceImg from '../assets/architecture/agent3_surveillance.png'
import governanceApprovalImg from '../assets/architecture/governance_approval.png'
import closedloopEmailImg from '../assets/architecture/closedloop_email.png'
import closedloopVisualizationImg from '../assets/architecture/closedloop_visualization.png'
import closedloopAlertsImg from '../assets/architecture/closedloop_alerts.png'

// Dynamic Swagger Docs URL (pointing to production FastAPI backend or env VITE_API_BASE_URL)
const rawBaseApi = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '').replace(/\/api$/, '') || 'https://customerordermanagement-yq6q.onrender.com'
const SWAGGER_DOCS_URL = `${rawBaseApi}/api/docs`

// -----------------------------------------------------------------------------
// COMPREHENSIVE TECHNICAL CARD BLUEPRINTS (CLICKABLE DETAILS FOR BOTTOM-LEFT)
// -----------------------------------------------------------------------------
const CARD_SPECS = {
  // STAGE 1: SOURCE SYSTEM (7 ENTERPRISE SILOS)
  sources: {
    id: 'sources',
    title: '1. Source System – 7 Enterprise Silos',
    subtitle: 'SAP S/4HANA, Siemens Opcenter, Veeva QMS & Logistics Ingestion',
    badge: 'STAGE 1 · DATA INGESTION',
    color: '#b91c1c',
    bg: '#fef2f2',
    icon: Factory,
    image: erpMmsImg,
    role: 'Centralizes continuous operational synchronization across 7 fragmented departmental systems without writing directly to legacy production databases.',
    protocols: 'SAP RFC / OData v4, Siemens MindSphere API, Manhattan REST, Veeva QMS Webhooks, Carrier EDI 214',
    tables: ['dim_customer', 'dim_product', 'dim_plant', 'dim_machine', 'dim_material', 'fact_inventory_daily_snapshot'],
    executionSteps: [
      'Ingests customer purchase order demand lines with committed requested delivery dates.',
      'Audits BOM component requirements against daily on-hand balances across manufacturing sites.',
      'Streams real-time machine run-status and work-center queue depths from Siemens MES.',
      'Captures partner API webhooks and carrier GPS delivery updates via unified ingestion bus.',
    ],
    inputs: ['ERP Purchase Orders (EDI 850)', 'MES Shop Floor SCADA', 'WMS Inventory Snapshots', 'Logistics API Webhooks'],
    outputs: ['Canonical FactCustomerOrder records', 'Material reservation queues', 'Plant capacity baseline matrices'],
    link: '/orders',
    linkLabel: 'Inspect Order Book',
  },
  erp_mms: {
    id: 'erp_mms',
    title: 'ERP & MMS (SAP / OData / BOM)',
    subtitle: 'Sales Order Intake, Contractual Pricing & Bill of Materials Scheduling',
    badge: 'ENTERPRISE SILO · COMMERCIAL & MATERIALS',
    color: '#0284c7',
    bg: '#f0f9ff',
    icon: Database,
    image: erpMmsImg,
    role: 'Synchronizes commercial sales contracts and pricing agreements from SAP S/4HANA with component inventory schedules from Master Production Scheduling (MMS).',
    protocols: 'SAP OData v4 · RFC / BAPI · MMS Material Master API · EDI 850 / 855',
    tables: ['fact_customer_order', 'dim_customer', 'dim_product', 'dim_material', 'fact_inventory_daily_snapshot'],
    executionSteps: [
      'Ingests customer purchase order demand lines across 4 Tier-1 accounts (Retailer North, MobileMart, Global Devices, Digital Bazaar).',
      'Validates commercial credit limits, contractual pricing, and payment terms in SAP S/4HANA.',
      'Simulates BOM component availability and supplier receipt dates across 3 smartphone models.',
      'Flags material shortages and lead time buffers before order commitment.',
    ],
    inputs: ['Customer sales agreements', 'BOM Master Structures', 'Supplier component delivery dates'],
    outputs: ['Validated commercial demand', 'Material shortage alerts', 'Inventory reservation tokens'],
    link: '/orders',
    linkLabel: 'Inspect Order Book',
  },
  mes_wms: {
    id: 'mes_wms',
    title: 'MES & WMS (Siemens / Inventory)',
    subtitle: 'Shop-Floor WIP Execution, Machine Work Centers & Finished Goods Stock',
    badge: 'ENTERPRISE SILO · MANUFACTURING & STORAGE',
    color: '#10b981',
    bg: '#f0fdf4',
    icon: Factory,
    image: mesWmsImg,
    role: 'Monitors real-time machine run-rates, routing work centers, preventative maintenance cycles, and warehouse bin allocations across Chennai & Bengaluru plants.',
    protocols: 'Siemens Opcenter API · Manhattan Associates WMS REST · OPC-UA Telemetry',
    tables: ['dim_plant', 'dim_machine', 'fact_production_order', 'fact_inventory_daily_snapshot'],
    executionSteps: [
      'Tracks active production work orders across 8 specialized manufacturing machines (Chennai & Bengaluru).',
      'Monitors machine utilization, maintenance downtime, and assembly queue depth.',
      'Evaluates usable finished goods stock vs allocated demand for instantaneous fulfillment.',
      'Publishes real-time assembly milestone timestamps to the central analytical bus.',
    ],
    inputs: ['Line schedule plans', 'Machine status telemetry', 'Bin storage locations'],
    outputs: ['Completed production units', 'WIP stage progress updates', 'Inventory reservation tokens'],
    link: '/inventory',
    linkLabel: 'Inspect Inventory & Machines',
  },
  qms_tms: {
    id: 'qms_tms',
    title: 'QMS & TMS (QA Holds / Logistics)',
    subtitle: 'Batch Quality Release Clearances & Multimodal Freight Transit Tracking',
    badge: 'ENTERPRISE SILO · QUALITY & TRANSIT',
    color: '#8b5cf6',
    bg: '#faf5ff',
    icon: Truck,
    image: qmsTmsImg,
    role: 'Enforces strict quality release standards (16,000+ inspected batches, 96.5% yield) and monitors multimodal freight transit milestones across carrier partners.',
    protocols: 'Veeva QMS Webhooks · Carrier EDI 214 Freight Tracking · REST GPS feeds',
    tables: ['fact_quality_inspection', 'fact_shipment_milestone'],
    executionSteps: [
      'Inspects finished assembly lots: classifies batches into Release, Quarantine Hold, or Scrap.',
      'Blocks shipping manifests automatically if QA quarantine hold is active.',
      'Tracks multi-carrier transit milestones (BlueDart, Safexpress, DHL, Delhivery).',
      'Calculates carrier delivery reliability and estimated transit arrival dates (ETAs).',
    ],
    inputs: ['QA test certificates', 'Inspection sample parameters', 'Carrier tracking events'],
    outputs: ['Quality release clearances', 'Carrier transit delay variance alerts', 'Shipment milestone events'],
    link: '/monitoring',
    linkLabel: 'View Quality & Transit Status',
  },

  // STAGE 2: API GATEWAY
  gateway: {
    id: 'gateway',
    title: '2. API Gateway – FastAPI Engine',
    subtitle: 'High-Throughput ASGI Router, Port 8000 & Real-Time SSE Streamer',
    badge: 'STAGE 2 · API GATEWAY',
    color: '#1e40af',
    bg: '#eff6ff',
    icon: Server,
    image: fastapiGatewayImg,
    role: 'High-throughput async backend routing queries, enforcing JWT role-based access control (RBAC), and streaming real-time multi-agent reasoning steps via Server-Sent Events (SSE).',
    protocols: 'FastAPI (Python 3.12) · Port 8000 · HTTP/2 REST · SSE Stream · JWT Bearer',
    tables: ['users', 'user_roles', 'audit_logs', 'system_settings'],
    executionSteps: [
      'Validates all incoming payloads through strict Pydantic v2 schemas.',
      'Enforces Segregation of Duties (SoD) and department-specific access boundaries.',
      'Streams live step-by-step LLM reasoning tokens and tool executions to the React UI.',
      'Caches database analytics queries with 60-second in-memory invalidation.',
    ],
    inputs: ['Client HTTP REST requests', 'Enterprise webhook payloads', 'Bearer JWT credentials'],
    outputs: ['Normalized canonical JSON responses', 'Server-Sent Event reasoning streams'],
    link: '/settings',
    linkLabel: 'View Security & Permissions',
  },

  // STAGE 3: MULTI-AGENT CORE
  agent1: {
    id: 'agent1',
    title: 'Agent 1: Assistant (Natural Language Q&A - SQL)',
    subtitle: 'Conversational Order Q&A & Read-Only SQL Tool Execution',
    badge: 'STAGE 3 · COGNITIVE AGENT 1',
    color: '#6f3dba',
    bg: '#faf5ff',
    icon: Bot,
    image: agent1AssistantImg,
    role: 'Autonomous conversational assistant that answers multi-department operational questions using Domo AI Text Generation and read-only SQL tools.',
    protocols: 'Domo AI Text Generation API · ReAct Tool-Calling Loop · PostgreSQL Read-Only Tools',
    tables: ['fact_customer_order', 'fact_production_order', 'dim_customer', 'dim_product', 'dim_material'],
    executionSteps: [
      'Parses operator natural language intent (order status, inventory balances, machine capacity).',
      'Executes multi-step ReAct thought-action-observation cycles using 5 approved SQL tools.',
      'Never hallucinates: grounds every answer in real PostgreSQL database query facts.',
      'Streams conversational synthesis to the Operations Assistant drawer.',
    ],
    inputs: ['User natural language prompts', 'Database schema metadata', 'Tool execution outputs'],
    outputs: ['Transparent thought reasoning steps', 'Verifiable SQL facts & synthesized answers'],
    link: '/assistant',
    linkLabel: 'Open Operations Assistant',
  },
  agent2: {
    id: 'agent2',
    title: 'Agent 2: Feasibility (7-Dept Audit - Delivery Date)',
    subtitle: 'Sequential 7-Department Delivery Date Feasibility Engine',
    badge: 'STAGE 3 · COGNITIVE AGENT 2',
    color: '#0284c7',
    bg: '#f0f9ff',
    icon: Cpu,
    image: agent2FeasibilityImg,
    role: 'Autonomously audits customer order feasibility across all 7 operational departments sequentially (ERP → MMS → MES → WMS → QMS → TMS → PLM) to synthesize a realistic achievable date.',
    protocols: 'Deterministic Order Auditing · Domo AI Synthesis · Dynamic Rescheduling Engine',
    tables: ['order_assessments', 'department_readiness', 'commitment_proposals'],
    executionSteps: [
      'Evaluates commercial pricing, credit, and configuration validity in ERP & PLM.',
      'Simulates BOM component inventory and scheduled supplier receipts in MMS.',
      'Checks machine run capacity, shift schedules, and routing work centers in MES.',
      'Audits quality inspection lead times in QMS and carrier dispatch transit in TMS.',
      'Calculates days variance between Requested Date and Achievable Date.',
      'Generates human-governed commercial commitment proposal with confidence score.',
    ],
    inputs: ['Customer order draft / intake payload', 'Real-time multi-department readiness telemetry'],
    outputs: ['7-department readiness scorecards', 'Realistic achievable delivery date', 'Risk mitigation options'],
    link: '/assessments',
    linkLabel: 'Inspect Feasibility Assessments',
  },
  agent3: {
    id: 'agent3',
    title: 'Agent 3: Surveillance (24/7 Monitor - 3 Day SLA)',
    subtitle: '24/7 Background Order Radar & Automated 3-Day SLA Escalation',
    badge: 'STAGE 3 · COGNITIVE AGENT 3',
    color: '#10b981',
    bg: '#ecfdf5',
    icon: Activity,
    image: agent3SurveillanceImg,
    role: 'Continuously monitors all active customer orders against baseline delivery milestones, detects operational anomalies, and enforces a mandatory 3-day SLA follow-up escalation rule.',
    protocols: 'Background Cron Scheduler · SHA-256 Alert Deduplication · Ethereal SMTP',
    tables: ['order_monitoring_records', 'risk_alerts', 'email_notification_logs', 'monitoring_execution_logs'],
    executionSteps: [
      'Scans committed orders every 10 minutes against factory, quality, and transit milestones.',
      'Deduplicates alerts using SHA-256 fingerprinting to prevent repetitive email spam.',
      'Synthesizes delivery impact and recommended mitigation actions via Domo AI.',
      'Dispatches initial risk notifications to Operational Department and Customer Service.',
      'Enforces 3-day SLA: If issue remains unresolved >3 days, automatically dispatches urgent follow-up emails.',
    ],
    inputs: ['Active order milestones', 'Production order status updates', 'Quality holds & carrier tracking'],
    outputs: ['Risk alerts in My Work queue', 'Initial & 3-day follow-up SMTP email notifications'],
    link: '/monitoring',
    linkLabel: 'Open Surveillance Center',
  },

  // STAGE 4: GOVERNANCE
  governance: {
    id: 'governance',
    title: '4. Governance – Human Approval Gate',
    subtitle: 'Segregation of Duties (SoD) & 100% Commercial CS Sign-Off',
    badge: 'STAGE 4 · HUMAN GOVERNANCE GATE',
    color: '#1d4ed8',
    bg: '#eff6ff',
    icon: ShieldCheck,
    image: governanceApprovalImg,
    role: 'Prevents autonomous AI agents from binding the company to commercial agreements. Enforces mandatory human commercial approval before orders transition to active manufacturing.',
    protocols: 'Role-Based Access Control (RBAC) · Segregation of Duties (SoD) · Cryptographic Audit Trail',
    tables: ['commitment_proposals', 'users', 'audit_logs'],
    executionSteps: [
      'Receives Agent 2 synthesized feasibility proposals (confidence, achievable date, variance).',
      'Flags orders requiring commercial review in Customer Service My Work queue.',
      'Only authorized Customer Service Leads or Administrators can click "Approve Commercial Commitment".',
      'Records authorized user ID, timestamp, and decision notes permanently in the audit trail.',
      'Transitions order status from HUMAN_APPROVAL to CONFIRMED, triggering factory release.',
    ],
    inputs: ['Agent 2 Feasibility Proposals', 'Human CS Lead decision notes'],
    outputs: ['Approved order commitments', 'Formal customer delivery agreements', 'Immutable audit logs'],
    link: '/my-work?tab=approvals',
    linkLabel: 'Open Commercial Approvals',
  },

  // STAGE 5: CLOSED-LOOP
  dual_email: {
    id: 'dual_email',
    title: 'Email (Dual Routing & Dispatch)',
    subtitle: 'Automated Technical Notices to Plant Ops & Delivery Impact Summaries to CS',
    badge: 'STAGE 5 · EMAIL DISPATCH',
    color: '#d97706',
    bg: '#fffbeb',
    icon: Mail,
    image: closedloopEmailImg,
    role: 'Dispatches targeted automated notifications to ensure plant supervisors receive actionable technical instructions while customer service receives commercial impact summaries.',
    protocols: 'Ethereal / Gmail SMTP · Transactional HTML Notification Engine · SMTP Webhooks',
    tables: ['email_notification_logs', 'risk_alerts', 'fact_customer_order'],
    executionSteps: [
      'Dual Email Routing: Sends actionable technical notices to Plant Ops and delivery impact summaries to CS.',
      'Automated 3-Day Follow-Up: Dispatches urgent escalation reminders if issues remain unresolved >3 days.',
      'Deduplicates alert emails to prevent notification fatigue among plant operators.',
      'Stores immutable delivery timestamps and recipient email logs in Neon PostgreSQL 16.',
    ],
    inputs: ['Risk alerts & follow-up events', 'Customer delivery breach projections'],
    outputs: ['Targeted HTML emails to Plant Ops & CS', 'Audit records in email_notification_logs'],
    link: '/monitoring/outbox',
    linkLabel: 'Open Email Outbox',
  },
  command_portals: {
    id: 'command_portals',
    title: 'Visualization (Command Portals & Heatmaps)',
    subtitle: 'Real-Time Executive Command Center, Heatmaps & Operational Analytics',
    badge: 'STAGE 5 · VISUALIZATION',
    color: '#0284c7',
    bg: '#f0f9ff',
    icon: LayoutDashboard,
    image: closedloopVisualizationImg,
    role: 'Provides enterprise-wide transparency into active order book progress, customer delivery commitments, and plant throughput with zero mock data.',
    protocols: 'React 18 · Recharts SVG · Neon PostgreSQL 16 Telemetry · Zero Mock Data',
    tables: ['fact_customer_order', 'dim_customer', 'fact_production_order'],
    executionSteps: [
      'Aggregates commercial order inflow (₹212.58 Cr across 1,619 orders) in real-time.',
      'Renders customer delivery date & progress heatmap across 5 delivery time windows.',
      'Tracks shop-floor WIP assembly progress across Chennai and Bengaluru facilities.',
      'Visualizes 8-dimension operational slicing and cross-departmental lead times.',
    ],
    inputs: ['Enterprise operational metrics', 'Live PostgreSQL telemetry', 'Operator filter selections'],
    outputs: ['Interactive visual dashboards', 'Live executive KPI dashboards', 'Customer delivery heatmaps'],
    link: '/overview',
    linkLabel: 'Open Command Center',
  },
  corrective_action: {
    id: 'corrective_action',
    title: 'Alerts (Surveillance & Exception Remediation)',
    subtitle: 'Verified Shop-Floor Remediation & Resolution Tracking in My Work',
    badge: 'STAGE 5 · ALERTS & ACTION',
    color: '#dc2626',
    bg: '#fef2f2',
    icon: AlertTriangle,
    image: closedloopAlertsImg,
    role: 'Closes the loop between automated surveillance detection and human shop-floor execution by tracking verified operator resolutions.',
    protocols: 'REST Webhooks · Neon PostgreSQL 16 ACID Transactions · My Work Execution Bus',
    tables: ['risk_alerts', 'order_monitoring_records', 'audit_logs'],
    executionSteps: [
      'Presents verified shop-floor remediation options (Expedite Work Order, Reassign Work Center, Buffer Stock).',
      'Operators record verified resolution notes and release quarantine holds directly in My Work.',
      'Updates Neon PostgreSQL 16 risk status from ACTIVE to RESOLVED with operator identity.',
      'Triggers automated follow-up notification confirming blocker removal.',
    ],
    inputs: ['Operator verified corrective action notes', 'Shop-floor resolution tickets'],
    outputs: ['Verified delivery confirmation', 'Updated milestone schedules', 'Resolved risk alerts'],
    link: '/my-work',
    linkLabel: 'Open My Work Queue',
  },
  // -----------------------------------------------------------------------------
  // PROBLEM STATEMENT SPECS (CLICKABLE CARDS FOR QUADRANT 2 -> DETAILS IN QUADRANT 3)
  // -----------------------------------------------------------------------------
  problem_delays: {
    id: 'problem_delays',
    isProblem: true,
    num: '01',
    keyword: 'DELAYS',
    title: '01. Operational & Delivery Lead-Time Delays',
    subtitle: 'Cross-Department Feasibility Lag & Production Milestone Slippages',
    badge: 'CRITICAL RISK · SOLVED BY AGENT 2 & 3',
    color: '#dc2626',
    bg: '#fee2e2',
    icon: Clock,
    summary: 'Manual cross-departmental feasibility assessments take 3 to 5 business days across emails and spreadsheets. Unforeseen material stockouts and machine queue backlogs cascade into missed customer delivery dates.',
    problemPoints: [
      {
        title: 'Sluggish Manual Feasibility Lag',
        desc: 'Commercial teams wait 3–5 days across emails before confirming order delivery dates.',
      },
      {
        title: 'Unvetted BOM Component Shortages',
        desc: 'Production scheduled without checking inventory across Chennai & Bengaluru warehouses.',
      },
      {
        title: 'Machine Work-Center Queue Overload',
        desc: 'Orders assigned to bottleneck SMT & testing lines running at 95%+ capacity (48–72h delays).',
      },
      {
        title: 'Quality Quarantine Hold Delays',
        desc: 'Batches with >3.5% defect rates held in QMS quarantine without automated notification.',
      },
      {
        title: 'Freight Carrier Transit Slippage',
        desc: 'Unmonitored carrier transit milestone delays (EDI 214) push deliveries past SLA windows.',
      },
    ],
    resolutionPoints: [
      'Agent 2 audits 7 departments sequentially in under 0.4 seconds to synthesize a guaranteed feasible delivery date.',
      'Agent 3 surveillance scans confirmed orders 24/7, catching delivery variance 14 to 50 days before contractual breach.',
      'Automated dispatch alerts route priority rerouting buffers to plant managers within 6 minutes of risk detection.',
    ],
    silos: ['SAP S/4HANA (ERP)', 'Siemens MES', 'MMS Materials', 'Carrier TMS'],
    link: '/monitoring',
    linkLabel: 'Inspect Active Delay Risks in Monitoring',
  },
  problem_blindspots: {
    id: 'problem_blindspots',
    isProblem: true,
    num: '02',
    keyword: 'BLINDSPOTS',
    title: '02. Commercial & Operational Information Blindspots',
    subtitle: 'Siloed Department Realities & Unvetted Sales Commitments',
    badge: 'HIGH RISK · SOLVED BY AGENT 1 & 2',
    color: '#d97706',
    bg: '#fef3c7',
    icon: AlertTriangle,
    summary: 'Commercial sales managers commit binding order delivery dates to enterprise clients without visibility into machine work center queue depths, raw material buffers, or active quality quarantine holds.',
    problemPoints: [
      {
        title: 'Isolated Enterprise Black-Box Silos',
        desc: '7 fragmented departmental databases operate as isolated data islands without integrated schema.',
      },
      {
        title: 'Phantom Inventory Allocations',
        desc: 'Sales orders promised against stock already soft-reserved for other high-priority contracts.',
      },
      {
        title: 'Zero Shop-Floor Telemetry for CS',
        desc: 'Customer Service blind to live machine WIP progress, forcing guessed delivery ETAs.',
      },
      {
        title: 'Hidden Supplier Receipt Delays',
        desc: 'Tier-2 component postponements remain hidden in MMS until scheduled production day.',
      },
      {
        title: 'Unsynchronized Part Master Data',
        desc: 'ERP billing codes diverge from shop-floor MES part numbers, causing picking & staging failures.',
      },
    ],
    resolutionPoints: [
      'Neon PostgreSQL 16 star schema unifies all 7 departmental silos into an immutable, single source of operational truth.',
      'Agent 1 provides an instant natural-language SQL assistant for Customer Service to query live order and machine statuses.',
      'Agent 2 evaluates commercial pricing, credit limits, and BOM availability before commitments can be signed.',
    ],
    silos: ['SAP ERP', 'Siemens MES', 'Manhattan WMS', 'Domo AI Analytics'],
    link: '/orders',
    linkLabel: 'Inspect Order Book Transparency',
  },
  problem_disruptions: {
    id: 'problem_disruptions',
    isProblem: true,
    num: '03',
    keyword: 'DISRUPTIONS',
    title: '03. Shop-Floor & Supply Chain Disruptions',
    subtitle: 'Machine Outages, Component Scarcity & Quality Failures',
    badge: 'CRITICAL RISK · SOLVED BY AGENT 3 & OPS BUS',
    color: '#7c3aed',
    bg: '#ede9fe',
    icon: Flame,
    summary: 'Unplanned machine breakdowns, sudden semiconductor component shortages, and batch quality quarantine holds abruptly halt production lines, multiplying operational overhead.',
    problemPoints: [
      {
        title: 'Unplanned Assembly Machine Breakdowns',
        desc: 'SMT-01 & CNC-02 experience unexpected downtime without automated line rebalancing.',
      },
      {
        title: 'Critical Raw Material Stockouts',
        desc: 'Microchips, displays, and battery lots reach zero on-hand buffer during active shift execution.',
      },
      {
        title: 'Inspection Failure Spikes',
        desc: 'Solder bridging defects trigger lot rejections, locking entire finished batches in quarantine.',
      },
      {
        title: 'Carrier Logistics Bottlenecks',
        desc: 'Transit shipments halted mid-route at carrier hubs without proactive alternate carrier rerouting.',
      },
      {
        title: 'Cascading Idle Labor Costs',
        desc: 'Surface-mount line halts leave downstream testing and packaging crews idle across shifts.',
      },
    ],
    resolutionPoints: [
      'Agent 3 continuous radar monitors machine health telemetry and inventory buffers every 60 seconds.',
      'Instant dual-channel email alerts notify plant managers with technical diagnostic data and CS with customer impact.',
      'Suggests automated dynamic stock transfers between Chennai and Bengaluru facilities to circumvent local outages.',
    ],
    silos: ['Siemens Opcenter MES', 'Manhattan WMS', 'Veeva QMS', 'Carrier GPS'],
    link: '/monitoring',
    linkLabel: 'View Live Disruption Radar',
  },
  problem_bottlenecks: {
    id: 'problem_bottlenecks',
    isProblem: true,
    num: '04',
    keyword: 'BOTTLENECKS',
    title: '04. Work Center & Multi-Department Bottlenecks',
    subtitle: 'Capacity Imbalances, Shift Scheduling Clashes & Approval Latency',
    badge: 'HIGH RISK · SOLVED BY FASTAPI & AGENT 2',
    color: '#0284c7',
    bg: '#e0f2fe',
    icon: Layers,
    summary: 'Severe capacity imbalances between assembly facilities and slow multi-department manual approval handoffs create friction, stalling order fulfillment velocity.',
    problemPoints: [
      {
        title: 'Plant Capacity Imbalance',
        desc: 'Chennai facility runs at 98% machine overload while Bengaluru sits underutilized at 65%.',
      },
      {
        title: 'Multi-Department Approval Deadlocks',
        desc: 'Feasibility proposals sit unapproved in departmental inboxes for days without ownership.',
      },
      {
        title: 'Synchronous System Throttling',
        desc: 'Legacy database batch syncs lock order tables during peak hours, freezing dashboards.',
      },
      {
        title: 'Packaging & QC Release Congestion',
        desc: 'Finished units pile up at packing bays awaiting manual signed inspection paperwork.',
      },
      {
        title: 'Peak Intake Order Flooding',
        desc: 'Sudden surges in retail promotion orders overwhelm intake workflows, causing FIFO inversions.',
      },
    ],
    resolutionPoints: [
      'FastAPI asynchronous gateway handles concurrent webhook ingestion with sub-25ms latency and zero database locking.',
      'Agent 2 automatically load-balances production work orders across Chennai and Bengaluru facilities based on live machine run-rates.',
      'Centralized My Work queue provides single-click human governance sign-off with enforced segregation of duties in under 6 minutes.',
    ],
    silos: ['FastAPI Engine', 'Siemens MES', 'Neon PG 16 Pool', 'My Work Queue'],
    link: '/my-work',
    linkLabel: 'Triage Bottlenecks in My Work Queue',
  },
  problem_sla_breaches: {
    id: 'problem_sla_breaches',
    isProblem: true,
    num: '05',
    keyword: 'SLA-BREACHES',
    title: '05. Contractual Delivery SLA Breaches & Penalties',
    subtitle: 'Overdue Commitments, Penalty Clauses & Missed OTIF Targets',
    badge: 'CRITICAL RISK · SOLVED BY 3-DAY ESCALATION',
    color: '#b91c1c',
    bg: '#fef2f2',
    icon: ShieldAlert,
    summary: 'Unresolved operational risks linger without follow-up, causing customer orders to breach contractual On-Time In-Full (OTIF) deadlines and triggering severe commercial financial penalties.',
    problemPoints: [
      {
        title: 'Lingering Unresolved Risk Alerts',
        desc: 'Disruption warnings acknowledged on shop floor remain unresolved 3+ days without action.',
      },
      {
        title: 'Heavy Contractual Financial Penalties',
        desc: 'Enterprise accounts enforce strict penalty clauses (up to 2% contract value per delayed day).',
      },
      {
        title: 'Plummeting OTIF Realization',
        desc: 'Cumulative fulfillment delays drag OTIF metrics well below contractual 95.0% SLA benchmark.',
      },
      {
        title: 'Customer Churn & Trust Erosion',
        desc: 'Tier-1 enterprise accounts lose confidence after repeated uncommunicated delivery slips.',
      },
      {
        title: 'Costly Reactive Air Freight Charters',
        desc: 'Emergency air freight charters to salvage overdue orders wipe out commercial margins.',
      },
    ],
    resolutionPoints: [
      'Automated 3-Day Follow-Up Engine triggers high-priority escalation reminders if an alert remains active for more than 72 hours.',
      'Deterministic feasibility synthesis ensures delivery commitments have mathematically validated capacity and lead time buffers.',
      'Closed-loop corrective actions have recovered ₹24 Cr in commitments and maintained an 81.6% OTIF recovery velocity.',
    ],
    silos: ['Neon PostgreSQL 16', 'Email Outbox Bus', 'Executive Reports Engine'],
    link: '/reports',
    linkLabel: 'View Enterprise OTIF Performance & Reports',
  },

}

// PROBLEM SPEC ALIASES
CARD_SPECS.delays = CARD_SPECS.problem_delays
CARD_SPECS.blindspots = CARD_SPECS.problem_blindspots
CARD_SPECS.disruptions = CARD_SPECS.problem_disruptions
CARD_SPECS.bottlenecks = CARD_SPECS.problem_bottlenecks
CARD_SPECS.sla_breaches = CARD_SPECS.problem_sla_breaches
CARD_SPECS['01'] = CARD_SPECS.problem_delays
CARD_SPECS['02'] = CARD_SPECS.problem_blindspots
CARD_SPECS['03'] = CARD_SPECS.problem_disruptions
CARD_SPECS['04'] = CARD_SPECS.problem_bottlenecks
CARD_SPECS['05'] = CARD_SPECS.problem_sla_breaches

// BACKWARD-COMPATIBILITY ALIASES
CARD_SPECS.dispatch = CARD_SPECS.dual_email
CARD_SPECS.actions = CARD_SPECS.corrective_action
CARD_SPECS.portals = CARD_SPECS.command_portals
CARD_SPECS.erp_mes = CARD_SPECS.erp_mms
CARD_SPECS.excel_files = CARD_SPECS.mes_wms
CARD_SPECS.apis_etl = CARD_SPECS.qms_tms
CARD_SPECS.cleaned_data = CARD_SPECS.agent1
CARD_SPECS.semantic_model = CARD_SPECS.agent2
CARD_SPECS.aggregated_data = CARD_SPECS.agent3
CARD_SPECS.consumption = CARD_SPECS.governance
CARD_SPECS.datadriven_decisions = CARD_SPECS.dual_email
CARD_SPECS.alerts_early_actions = CARD_SPECS.corrective_action
CARD_SPECS.business_impact = CARD_SPECS.command_portals

// -----------------------------------------------------------------------------
// PROBLEM STATEMENTS WITH SINGLE-WORD KEYWORDS (TOP-RIGHT SECTION)
// -----------------------------------------------------------------------------
const PROBLEM_STATEMENTS = [
  {
    keyword: 'FRAGMENTATION',
    severity: 'CRITICAL',
    title: 'Isolated Enterprise Data Silos',
    desc: '7 disconnected legacy operational systems (ERP, MMS, MES, WMS, QMS, TMS, PLM) operate as black-box data islands without a unified analytical schema.',
    impact: 'Zero cross-department visibility into active shop-floor reality.',
  },
  {
    keyword: 'BLINDSPOTS',
    severity: 'HIGH',
    title: 'Unvetted Sales Commitments',
    desc: 'Sales and account managers commit commercial order delivery dates to enterprise customers without real-time validation of component inventory, machine queue depth, or quality release lead times.',
    impact: 'High initial schedule variance and unmet customer commitments.',
  },
  {
    keyword: 'DELAYS',
    severity: 'CRITICAL',
    title: 'Sluggish Manual Feasibility Audits',
    desc: 'Manual cross-departmental feasibility assessments take 3 to 5 business days across emails and spreadsheets, stalling commercial order confirmation and increasing customer backlog.',
    impact: 'Average 3-5 days lost before production lines are scheduled.',
  },
  {
    keyword: 'BOTTLENECKS',
    severity: 'HIGH',
    title: 'Unanticipated Operational Disruptions',
    desc: 'Unforeseen raw material stockouts, unexpected machine maintenance downtime, and quality quarantine holds halt assembly lines without proactive alerts.',
    impact: 'Assembly milestone slips and costly expedited freight fees.',
  },
  {
    keyword: 'DISCONNECTION',
    severity: 'MEDIUM',
    title: 'CS Separated from Shop Floor',
    desc: 'Customer Service representatives lack real-time visibility into shop-floor assembly progress, forcing them to communicate unverified status updates to clients.',
    impact: 'Customer dissatisfaction and reputational brand damage.',
  },
  {
    keyword: 'SLA-BREACHES',
    severity: 'CRITICAL',
    title: 'Unresolved Operational Risks',
    desc: 'Shop-floor risk alerts linger acknowledged or open for days without resolution tracking, lacking an automated 3-day escalation mechanism to enforce department closure.',
    impact: 'Accumulation of overdue orders and delivery penalty clauses.',
  },
  {
    keyword: 'HALLUCINATIONS',
    severity: 'HIGH',
    title: 'Ungrounded Generative AI Decisions',
    desc: 'Conventional generative AI models invent dates and hallucinate inventory quantities. Autonomous agents must be strictly grounded in verified database facts with mandatory human sign-off.',
    impact: 'Risk of binding legal liabilities from ungrounded AI promises.',
  },
]

// CUSTOMER BRAND METADATA & HELPER FUNCTIONS
const CUSTOMER_META = {
  'Retailer North': {
    color: '#6f3dba',
    bg: '#f5f3ff',
    badgeBg: '#ede9fe',
    border: '#c084fc',
    initials: 'RN',
  },
  'MobileMart': {
    color: '#0284c7',
    bg: '#f0f9ff',
    badgeBg: '#e0f2fe',
    border: '#7dd3fc',
    initials: 'MM',
  },
  'Global Devices': {
    color: '#059669',
    bg: '#f0fdf4',
    badgeBg: '#d1fae5',
    border: '#6ee7b7',
    initials: 'GD',
  },
  'Digital Bazaar': {
    color: '#d97706',
    bg: '#fffbeb',
    badgeBg: '#fef3c7',
    border: '#fcd34d',
    initials: 'DB',
  },
}

function formatDeliveryDate(val) {
  if (!val) return 'TBD'
  try {
    const parts = String(val).split('-')
    if (parts.length === 3) {
      const y = parseInt(parts[0], 10)
      const m = parseInt(parts[1], 10) - 1
      const d = parseInt(parts[2], 10)
      const dateObj = new Date(y, m, d)
      return dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    }
    return String(val)
  } catch {
    return String(val)
  }
}

// -----------------------------------------------------------------------------
// LIVE FASTAPI GATEWAY ENDPOINTS SPECIFICATION DIRECTORY
// -----------------------------------------------------------------------------
const API_ENDPOINTS = [
  {
    id: 'dash-summary',
    category: 'CORE',
    method: 'GET',
    path: '/api/dashboard/summary',
    name: 'Executive KPIs & Pipeline Funnel',
    desc: 'Aggregates commercial order inflow, WIP counts, delay risk alerts, autonomous approvals, and OTIF rates computed live from Neon PostgreSQL 16.',
    auth: 'JWT Bearer',
    latency: '45ms',
    params: 'Query: from_date, to_date, department, customer, plant',
    responseSample: '{\n  "total_orders": 1619,\n  "total_value": 212587260121,\n  "active_wip": 1304,\n  "at_risk": 1228,\n  "otif_rate": 81.6\n}',
  },
  {
    id: 'orders-list',
    category: 'CORE',
    method: 'GET',
    path: '/api/orders',
    name: 'Enterprise Order Book Slicing',
    desc: 'Paginated query engine filtering 1,619 customer orders across 4 Tier-1 accounts, 2 manufacturing facilities, delivery dates, and status.',
    auth: 'JWT Bearer',
    latency: '65ms',
    params: 'Query: page=1, limit=50, customer, status, risk_level',
    responseSample: '{\n  "orders": [...],\n  "total": 1619,\n  "page": 1,\n  "pages": 33\n}',
  },
  {
    id: 'orders-intake',
    category: 'CORE',
    method: 'POST',
    path: '/api/orders/intake',
    name: 'Commercial Order Intake',
    desc: 'Ingests new customer purchase orders, validates configuration via Pydantic v2 schemas, and automatically enqueues for Agent 2 feasibility auditing.',
    auth: 'JWT Bearer',
    latency: '110ms',
    params: 'Body: { customer_id, product_sku, units, requested_date }',
    responseSample: '{\n  "order_id": "PRE-ASM-20261119-9941",\n  "status": "OPEN",\n  "queued_for_agent2": true\n}',
  },
  {
    id: 'feasibility-assess',
    category: 'AGENTS',
    method: 'POST',
    path: '/api/feasibility/assess/{order_id}',
    name: 'Agent 2: 7-Dept Feasibility Engine',
    desc: 'Triggers autonomous sequential audit across ERP → MMS → MES → WMS → QMS → TMS → PLM to calculate realistic achievable delivery dates.',
    auth: 'JWT Bearer',
    latency: '420ms',
    params: 'Path: order_id (e.g. PRE-ASM-20261119-8012CB)',
    responseSample: '{\n  "achievable_date": "2026-11-27",\n  "variance_days": 3,\n  "confidence": "HIGH",\n  "status": "PENDING"\n}',
  },
  {
    id: 'proposals-approve',
    category: 'AGENTS',
    method: 'POST',
    path: '/api/feasibility/proposals/{id}/approve',
    name: 'Human CS Commercial Sign-Off',
    desc: 'Enforces Segregation of Duties (SoD). Authorized Customer Service Leads approve commercial commitments to release orders to production lines.',
    auth: 'Role: CS_LEAD / ADMIN',
    latency: '85ms',
    params: 'Path: proposal_id, Body: { decision_notes, confirmed_date }',
    responseSample: '{\n  "status": "CONFIRMED",\n  "approved_by": "admin@manufacturing.com",\n  "audit_logged": true\n}',
  },
  {
    id: 'agent-chat',
    category: 'AGENTS',
    method: 'POST',
    path: '/api/agent/chat',
    name: 'Agent 1: Conversational Assistant (SSE)',
    desc: 'Server-Sent Events (SSE) streaming endpoint. Runs ReAct multi-step reasoning cycles with read-only SQL tools to answer operator queries without hallucinations.',
    auth: 'JWT Bearer',
    latency: 'Real-Time Stream',
    params: 'Body: { message: "What is the bottleneck for Retailer North order 8012CB?" }',
    responseSample: 'event: token\ndata: {"thought": "Querying MMS inventory...", "answer": "Shortage in Display Assemblies"}',
  },
  {
    id: 'monitoring-records',
    category: 'SURVEILLANCE',
    method: 'GET',
    path: '/api/monitoring/records',
    name: 'Agent 3: 24/7 Delivery Surveillance Radar',
    desc: 'Retrieves all active orders under background surveillance, tracking milestone elapsed ratios, delay risk scores, and department health scores.',
    auth: 'JWT Bearer',
    latency: '55ms',
    params: 'Query: status=ACTIVE, department, risk_level',
    responseSample: '{\n  "records": [...],\n  "at_risk_count": 1228,\n  "on_track_count": 76\n}',
  },
  {
    id: 'monitoring-cycle',
    category: 'SURVEILLANCE',
    method: 'POST',
    path: '/api/monitoring/run-cycle',
    name: 'Trigger Surveillance Audit Cycle',
    desc: 'Runs an on-demand audit scanning all confirmed orders against factory, QA hold, and carrier GPS milestones; dispatches dual-channel HTML emails.',
    auth: 'JWT Bearer',
    latency: '380ms',
    params: 'None (Optional: force_refresh=true)',
    responseSample: '{\n  "scanned_orders": 1304,\n  "alerts_created": 3,\n  "emails_dispatched": 2\n}',
  },
  {
    id: 'alerts-feed',
    category: 'SURVEILLANCE',
    method: 'GET',
    path: '/api/alerts',
    name: 'Operational Risk Alerts Feed',
    desc: 'Lists active operational alerts filtered by department (ERP, MMS, MES, WMS, QMS, TMS, PLM) with SHA-256 fingerprint deduplication.',
    auth: 'JWT Bearer',
    latency: '40ms',
    params: 'Query: severity=CRITICAL, status=ACTIVE, department',
    responseSample: '[\n  {\n    "alert_id": "ALT-1092",\n    "severity": "CRITICAL",\n    "title": "MMS Component Shortage"\n  }\n]',
  },
  {
    id: 'action-exec',
    category: 'SURVEILLANCE',
    method: 'POST',
    path: '/api/actions/{id}/execute',
    name: 'Mitigation Action Dispatch',
    desc: 'Executes verified mitigations: REQUEST_EXPEDITE, NOTIFY_CUSTOMER_REVISED_DATE, REQUEST_CARRIER_UPGRADE, or REQUEST_REASSESSMENT.',
    auth: 'Role: OPERATOR / ADMIN',
    latency: '95ms',
    params: 'Path: action_id, Body: { action_type, execution_payload }',
    responseSample: '{\n  "status": "EXECUTED",\n  "dispatched_at": "2026-11-19T17:30:00Z"\n}',
  },
  {
    id: 'sys-health',
    category: 'SYSTEM',
    method: 'GET',
    path: '/api/health',
    name: 'Gateway Health & Database Telemetry',
    desc: 'Verifies FastAPI gateway execution, Uvicorn process uptime, and Neon PostgreSQL 16 connection pool readiness.',
    auth: 'Public',
    latency: '12ms',
    params: 'None',
    responseSample: '{\n  "status": "online",\n  "database": "connected",\n  "engine": "FastAPI 0.111 (Python 3.12)"\n}',
  },
  {
    id: 'auth-login',
    category: 'SYSTEM',
    method: 'POST',
    path: '/api/auth/login',
    name: 'JWT Bearer Session Authentication',
    desc: 'Authenticates operators, Customer Service leads, and admins with bcrypt password hashing; returns RS256/HS256 signed JWT Bearer tokens.',
    auth: 'Public',
    latency: '50ms',
    params: 'Body: { email, password }',
    responseSample: '{\n  "access_token": "eyJhbGciOi...",\n  "token_type": "bearer",\n  "role": "ADMIN"\n}',
  },
  {
    id: 'connectors-status',
    category: 'SYSTEM',
    method: 'GET',
    path: '/api/connectors/status',
    name: '7 Enterprise Conduits Health',
    desc: 'Monitors real-time connectivity status and synchronization latencies for all 7 enterprise silos (ERP, MMS, MES, WMS, QMS, TMS, PLM).',
    auth: 'JWT Bearer',
    latency: '35ms',
    params: 'None',
    responseSample: '{\n  "conduits": {\n    "ERP": "CONNECTED",\n    "MMS": "CONNECTED",\n    "MES": "CONNECTED"\n  }\n}',
  },
  {
    id: 'sys-docs',
    category: 'SYSTEM',
    method: 'GET',
    path: '/api/docs',
    name: 'Interactive Swagger UI Documentation',
    desc: 'Live OpenAPI 3.1.0 Swagger interactive interface enabling browser-based payload testing, schema inspection, and curl reproduction.',
    auth: 'Public',
    latency: '18ms',
    params: 'Browser HTTP GET',
    responseSample: 'HTML / Swagger UI 5.x interface mounted on FastAPI',
  },
]

// -----------------------------------------------------------------------------
// 16 REALISTIC, COLORFUL 3D-STYLED VECTOR ARCHITECTURE ICONS
// -----------------------------------------------------------------------------

// 1. Column 1 Header: Industrial Factory
function FactoryRefIcon({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <defs>
        <linearGradient id="hdrFactRoof" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#e2e8f0" />
        </linearGradient>
        <linearGradient id="hdrFactChim" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#fca5a5" />
          <stop offset="100%" stopColor="#ef4444" />
        </linearGradient>
      </defs>
      <rect x="20" y="5" width="4" height="13" rx="1" fill="url(#hdrFactChim)" />
      <rect x="19" y="4" width="6" height="2" rx="0.5" fill="#b91c1c" />
      <circle cx="22" cy="2" r="1.5" fill="#ffffff" opacity="0.8" />
      <circle cx="24" cy="0.5" r="1.2" fill="#ffffff" opacity="0.5" />
      <path d="M3 27V15L9 11V15L15 11V15L21 11V18H28V27H3Z" fill="url(#hdrFactRoof)" />
      <rect x="2" y="26" width="28" height="3" rx="1" fill="#cbd5e1" />
      <rect x="6" y="19" width="3" height="4" rx="0.5" fill="#0284c7" />
      <rect x="12" y="19" width="3" height="4" rx="0.5" fill="#0284c7" />
      <rect x="18" y="19" width="3" height="4" rx="0.5" fill="#0284c7" />
      <rect x="24" y="21" width="3" height="5" rx="0.5" fill="#475569" />
    </svg>
  )
}

// 2. Column 1 - Item 1: Database Cylinder with Green Gear (ERP & MMS)
function DatabaseGearRefIcon({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <defs>
        <linearGradient id="dbCylTop1" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#0284c7" />
        </linearGradient>
        <linearGradient id="dbCylBody1" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#0284c7" />
          <stop offset="35%" stopColor="#38bdf8" />
          <stop offset="70%" stopColor="#0369a1" />
          <stop offset="100%" stopColor="#075985" />
        </linearGradient>
        <linearGradient id="dbGearGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#4ade80" />
          <stop offset="50%" stopColor="#16a34a" />
          <stop offset="100%" stopColor="#15803d" />
        </linearGradient>
        <linearGradient id="goldCapGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fef08a" />
          <stop offset="100%" stopColor="#eab308" />
        </linearGradient>
      </defs>

      {/* Database Bottom Tier */}
      <path d="M6 24V32C6 35.5 12.5 38 20 38C27.5 38 34 35.5 34 32V24" fill="url(#dbCylBody1)" />
      <ellipse cx="20" cy="24" rx="14" ry="5" fill="#0284c7" />
      <ellipse cx="20" cy="24" rx="13.5" ry="4.5" fill="#7dd3fc" opacity="0.6" />

      {/* Middle Tier */}
      <path d="M6 16V24C6 27.5 12.5 30 20 30C27.5 30 34 27.5 34 24V16" fill="url(#dbCylBody1)" />
      <ellipse cx="20" cy="16" rx="14" ry="5" fill="#0284c7" />
      <ellipse cx="20" cy="16" rx="13.5" ry="4.5" fill="#bae6fd" opacity="0.6" />

      {/* Top Tier */}
      <path d="M6 8V16C6 19.5 12.5 22 20 22C27.5 22 34 19.5 34 16V8" fill="url(#dbCylBody1)" />
      <ellipse cx="20" cy="8" rx="14" ry="5" fill="url(#dbCylTop1)" />
      <ellipse cx="18" cy="7.5" rx="11" ry="3.5" fill="#ffffff" opacity="0.4" />

      {/* LED status lights */}
      <circle cx="10" cy="12" r="1.5" fill="#22c55e" />
      <circle cx="14" cy="13" r="1.2" fill="#38bdf8" />
      <circle cx="10" cy="20" r="1.5" fill="#22c55e" />
      <circle cx="14" cy="21" r="1.2" fill="#38bdf8" />
      <circle cx="10" cy="28" r="1.5" fill="#eab308" />

      {/* 3D Precision Gear */}
      <g transform="translate(24, 22)">
        <circle cx="11" cy="12" r="9" fill="#0f172a" opacity="0.25" />
        <path
          d="M11 1L13.2 3.2L16.2 2.3L17.5 5.2L20.5 6.1L20.5 9.1L23 11.4L20.5 13.7L20.5 16.7L17.5 17.6L16.2 20.5L13.2 19.6L11 21.8L8.8 19.6L5.8 20.5L4.5 17.6L1.5 16.7L1.5 13.7L-1 11.4L1.5 9.1L1.5 6.1L4.5 5.2L5.8 2.3L8.8 3.2Z"
          fill="url(#dbGearGrad)"
          stroke="#14532d"
          strokeWidth="0.8"
        />
        <circle cx="11" cy="11.4" r="5" fill="#15803d" />
        <circle cx="11" cy="11.4" r="4" fill="url(#goldCapGrad)" />
        <circle cx="11" cy="11.4" r="2" fill="#ffffff" />
      </g>
    </svg>
  )
}

// 3. Column 1 - Item 2: Factory & Warehouse Pallet (MES & WMS)
function MesWmsRefIcon({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <defs>
        <linearGradient id="mesPlantGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#10b981" />
          <stop offset="100%" stopColor="#047857" />
        </linearGradient>
        <linearGradient id="mesRoofGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#34d399" />
          <stop offset="100%" stopColor="#059669" />
        </linearGradient>
        <linearGradient id="crateGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fbbf24" />
          <stop offset="100%" stopColor="#d97706" />
        </linearGradient>
        <linearGradient id="crate2Grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#0284c7" />
        </linearGradient>
      </defs>

      {/* Main Factory Facility */}
      <path
        d="M4 38V18L12 12V18L20 12V18L26 14V38H4Z"
        fill="url(#mesPlantGrad)"
      />
      <path d="M4 18L12 12L12 14L4 20Z" fill="url(#mesRoofGrad)" />
      <path d="M12 18L20 12L20 14L12 20Z" fill="url(#mesRoofGrad)" />
      <path d="M20 18L26 14L26 16L20 20Z" fill="url(#mesRoofGrad)" />

      {/* Windows with warm glow */}
      <rect x="7" y="22" width="3" height="4" rx="0.5" fill="#fef08a" />
      <rect x="13" y="22" width="3" height="4" rx="0.5" fill="#fef08a" />
      <rect x="7" y="28" width="3" height="4" rx="0.5" fill="#fef08a" />
      <rect x="13" y="28" width="3" height="4" rx="0.5" fill="#fef08a" />

      {/* Roll-up bay door */}
      <rect x="19" y="27" width="6" height="11" rx="0.8" fill="#334155" />
      <line x1="19" y1="30" x2="25" y2="30" stroke="#64748b" strokeWidth="0.8" />
      <line x1="19" y1="33" x2="25" y2="33" stroke="#64748b" strokeWidth="0.8" />
      <line x1="19" y1="36" x2="25" y2="36" stroke="#64748b" strokeWidth="0.8" />

      {/* Foreground Warehouse Logistics Pallet */}
      <g transform="translate(24, 18)">
        <rect x="2" y="22" width="20" height="3" rx="1" fill="#78350f" />
        <rect x="4" y="20" width="16" height="2.5" rx="0.5" fill="#b45309" />
        <line x1="8" y1="22" x2="8" y2="25" stroke="#451a03" strokeWidth="1" />
        <line x1="16" y1="22" x2="16" y2="25" stroke="#451a03" strokeWidth="1" />

        {/* Lower Wooden Cargo Crate */}
        <rect x="3" y="10" width="10" height="10" rx="1.5" fill="url(#crateGrad)" stroke="#b45309" strokeWidth="0.8" />
        <path d="M3 10L13 20M13 10L3 20" stroke="#d97706" strokeWidth="0.7" opacity="0.6" />
        <rect x="5" y="14" width="6" height="3" rx="0.5" fill="#ffffff" />
        <line x1="6" y1="15.5" x2="10" y2="15.5" stroke="#000000" strokeWidth="0.8" strokeDasharray="1 0.6" />

        {/* Right Cargo Crate (Blue) */}
        <rect x="12" y="12" width="9" height="8" rx="1.5" fill="url(#crate2Grad)" stroke="#0369a1" strokeWidth="0.8" />
        <rect x="14" y="14" width="5" height="2" rx="0.4" fill="#ffffff" opacity="0.8" />

        {/* Top Priority Crate */}
        <rect x="6" y="3" width="8" height="7" rx="1.2" fill="#ef4444" stroke="#b91c1c" strokeWidth="0.8" />
        <circle cx="10" cy="6.5" r="1.5" fill="#fef08a" />
      </g>
    </svg>
  )
}

// 4. Column 1 - Item 3: QA Certificate Badge & Transit Truck (QMS & TMS)
function QmsTmsRefIcon({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <defs>
        <linearGradient id="qmsBadgeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#a855f7" />
          <stop offset="100%" stopColor="#6d28d9" />
        </linearGradient>
        <linearGradient id="qmsGoldRim" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fde047" />
          <stop offset="100%" stopColor="#ca8a04" />
        </linearGradient>
        <linearGradient id="tmsCabGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#60a5fa" />
          <stop offset="100%" stopColor="#1d4ed8" />
        </linearGradient>
        <linearGradient id="tmsTrailGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#93c5fd" />
          <stop offset="100%" stopColor="#3b82f6" />
        </linearGradient>
      </defs>

      {/* QMS Quality Shield Badge */}
      <path
        d="M14 4L24 8V19C24 26 19.5 32 14 35C8.5 32 4 26 4 19V8L14 4Z"
        fill="url(#qmsBadgeGrad)"
        stroke="url(#qmsGoldRim)"
        strokeWidth="1.8"
      />
      <path
        d="M14 7L21 10.5V18C21 23.5 17.5 28.5 14 31C10.5 28.5 7 23.5 7 18V10.5L14 7Z"
        fill="#7c3aed"
        opacity="0.4"
      />
      <circle cx="14" cy="18" r="6" fill="#10b981" />
      <path d="M10.5 18L13 20.5L17.5 15.5" stroke="#ffffff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />

      {/* TMS Freight Transport Truck */}
      <g transform="translate(18, 18)">
        <rect x="0" y="5" width="18" height="15" rx="1.5" fill="url(#tmsTrailGrad)" stroke="#1e40af" strokeWidth="1" />
        <line x1="4" y1="7" x2="4" y2="18" stroke="#1d4ed8" strokeWidth="0.9" />
        <line x1="8" y1="7" x2="8" y2="18" stroke="#1d4ed8" strokeWidth="0.9" />
        <line x1="12" y1="7" x2="12" y2="18" stroke="#1d4ed8" strokeWidth="0.9" />

        <path
          d="M18 10H23.5L27 14.5V20H18V10Z"
          fill="url(#tmsCabGrad)"
          stroke="#1e40af"
          strokeWidth="1"
        />
        <path d="M22 11H23.2L25.8 14.5H22V11Z" fill="#e0f2fe" />
        <rect x="25.5" y="17" width="2.5" height="3" rx="0.5" fill="#94a3b8" />
        <circle cx="26.5" cy="18.5" r="1" fill="#fef08a" />

        <circle cx="6" cy="21" r="3.2" fill="#1e293b" />
        <circle cx="6" cy="21" r="1.5" fill="#94a3b8" />
        <circle cx="14" cy="21" r="3.2" fill="#1e293b" />
        <circle cx="14" cy="21" r="1.5" fill="#94a3b8" />
        <circle cx="22" cy="21" r="3.2" fill="#1e293b" />
        <circle cx="22" cy="21" r="1.5" fill="#94a3b8" />
      </g>
    </svg>
  )
}

// 5. Header Cylinder Icon (Column 2)
function CylinderRefIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="cylHdrGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#bae6fd" />
        </linearGradient>
      </defs>
      <ellipse cx="12" cy="5.5" rx="8" ry="3" fill="url(#cylHdrGrad)" />
      <path d="M4 5.5V11C4 12.66 7.58 14 12 14C16.42 14 20 12.66 20 11V5.5" fill="#38bdf8" stroke="#ffffff" strokeWidth="1.2" />
      <path d="M4 11V16.5C4 18.16 7.58 19.5 12 19.5C16.42 19.5 20 18.16 20 16.5V11" fill="#0284c7" stroke="#ffffff" strokeWidth="1.2" />
      <ellipse cx="12" cy="11" rx="8" ry="2.8" fill="#e0f2fe" opacity="0.6" />
    </svg>
  )
}

// 6. Column 2 Center Graphic: Database with Interlocking Gears (FastAPI Engine)
function DataPrepDatabaseGearsRefIcon({ size = 52 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none">
      <defs>
        <linearGradient id="gwCylTop" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#60a5fa" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>
        <linearGradient id="gwCylBody" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#1e40af" />
          <stop offset="35%" stopColor="#60a5fa" />
          <stop offset="70%" stopColor="#2563eb" />
          <stop offset="100%" stopColor="#1e3a8a" />
        </linearGradient>
        <linearGradient id="gwGearOrange" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fb923c" />
          <stop offset="50%" stopColor="#ea580c" />
          <stop offset="100%" stopColor="#9a3412" />
        </linearGradient>
        <linearGradient id="gwGearGreen" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#34d399" />
          <stop offset="50%" stopColor="#059669" />
          <stop offset="100%" stopColor="#065f46" />
        </linearGradient>
        <linearGradient id="gwBoltGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fef08a" />
          <stop offset="100%" stopColor="#f59e0b" />
        </linearGradient>
      </defs>

      {/* Main Server Database Stack */}
      <path d="M8 32V42C8 46.5 17 50 28 50C39 50 48 46.5 48 42V32" fill="url(#gwCylBody)" />
      <ellipse cx="28" cy="32" rx="20" ry="7" fill="#1d4ed8" />
      <ellipse cx="28" cy="32" rx="19.2" ry="6.2" fill="#93c5fd" opacity="0.4" />

      <path d="M8 22V32C8 36.5 17 40 28 40C39 40 48 36.5 48 32V22" fill="url(#gwCylBody)" />
      <ellipse cx="28" cy="22" rx="20" ry="7" fill="#2563eb" />
      <ellipse cx="28" cy="22" rx="19.2" ry="6.2" fill="#bfdbfe" opacity="0.5" />

      <path d="M8 12V22C8 26.5 17 30 28 30C39 30 48 26.5 48 22V12" fill="url(#gwCylBody)" />
      <ellipse cx="28" cy="12" rx="20" ry="7" fill="url(#gwCylTop)" />
      <ellipse cx="25" cy="11" rx="15" ry="4.5" fill="#ffffff" opacity="0.4" />

      {/* Server LEDs */}
      <circle cx="14" cy="17" r="2" fill="#22c55e" />
      <circle cx="20" cy="18" r="1.6" fill="#38bdf8" />
      <circle cx="14" cy="27" r="2" fill="#22c55e" />
      <circle cx="20" cy="28" r="1.6" fill="#38bdf8" />
      <circle cx="14" cy="37" r="2" fill="#eab308" />

      {/* 3D Interlocking Dual Precision Gears */}
      <g transform="translate(34, 20)">
        <circle cx="14" cy="14" r="13" fill="url(#gwGearOrange)" stroke="#7c2d12" strokeWidth="1" />
        <path d="M14 0V4M14 24V28M0 14H4M24 14H28M4 4L7 7M21 21L24 24M4 24L7 21M21 7L24 4" stroke="#fed7aa" strokeWidth="2.4" strokeLinecap="round" />
        <circle cx="14" cy="14" r="7" fill="#9a3412" />
        <circle cx="14" cy="14" r="4.5" fill="#ffffff" />
      </g>

      <g transform="translate(24, 34)">
        <circle cx="10" cy="10" r="9.5" fill="url(#gwGearGreen)" stroke="#064e3b" strokeWidth="0.9" />
        <path d="M10 0V3M10 17V20M0 10H3M17 10H20M3 3L5.5 5.5M14.5 14.5L17 17M3 17L5.5 14.5M14.5 5.5L17 3" stroke="#a7f3d0" strokeWidth="2" strokeLinecap="round" />
        <circle cx="10" cy="10" r="5" fill="#065f46" />
        <circle cx="10" cy="10" r="3" fill="#ffffff" />
      </g>

      {/* API Lightning Connector */}
      <path
        d="M32 4L27 15H33L29 24L38 12H32L36 4H32Z"
        fill="url(#gwBoltGrad)"
        stroke="#d97706"
        strokeWidth="0.8"
      />
    </svg>
  )
}

// 7. Column 3 Header: AI Multi-Agent Cognitive Icon
function MultiAgentHeaderRefIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="aiHdrGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#e9d5ff" />
        </linearGradient>
      </defs>
      <rect x="3" y="6" width="18" height="14" rx="4" fill="url(#aiHdrGrad)" />
      <rect x="6" y="9" width="12" height="5" rx="2" fill="#581c87" />
      <circle cx="9.5" cy="11.5" r="1.3" fill="#38bdf8" />
      <circle cx="14.5" cy="11.5" r="1.3" fill="#38bdf8" />
      <path d="M12 2V6M9 2H15" stroke="#ffffff" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="12" cy="1.5" r="1.2" fill="#facc15" />
    </svg>
  )
}

// 8. Column 3 - Item 1: Intelligent Assistant Bot (Agent 1: Assistant)
function Agent1BotRefIcon({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <defs>
        <linearGradient id="botHeadGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ede9fe" />
          <stop offset="50%" stopColor="#c4b5fd" />
          <stop offset="100%" stopColor="#8b5cf6" />
        </linearGradient>
        <linearGradient id="botVisorGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#0f172a" />
          <stop offset="100%" stopColor="#312e81" />
        </linearGradient>
        <linearGradient id="bubbleGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fef08a" />
          <stop offset="100%" stopColor="#f59e0b" />
        </linearGradient>
        <linearGradient id="botEarGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fde047" />
          <stop offset="100%" stopColor="#d97706" />
        </linearGradient>
      </defs>

      {/* Floating 3D Speech Bubble with AI Sparkle */}
      <g transform="translate(24, 2)">
        <path
          d="M2 13C2 7 7 2 13 2C19 2 24 7 24 13C24 18 20 22 15 22.8L12 26V22.6C6.5 22 2 18 2 13Z"
          fill="url(#bubbleGrad)"
          stroke="#b45309"
          strokeWidth="1.2"
        />
        <path
          d="M13 6L14.2 10.5L18.5 11.5L14.2 12.5L13 17L11.8 12.5L7.5 11.5L11.8 10.5Z"
          fill="#ffffff"
        />
        <circle cx="19" cy="6" r="1.2" fill="#ffffff" />
      </g>

      {/* Bot Antenna with Glowing Ruby Beacon */}
      <rect x="18" y="7" width="3" height="7" rx="1.5" fill="#7c3aed" />
      <circle cx="19.5" cy="5.5" r="3" fill="#ef4444" />
      <circle cx="18.5" cy="4.5" r="1" fill="#ffffff" />

      {/* Ear Muff Pods */}
      <rect x="3" y="21" width="4" height="12" rx="2" fill="url(#botEarGrad)" />
      <rect x="32" y="21" width="4" height="12" rx="2" fill="url(#botEarGrad)" />

      {/* Robot Head Body */}
      <rect x="5" y="14" width="29" height="26" rx="9" fill="url(#botHeadGrad)" stroke="#6d28d9" strokeWidth="1.6" />
      <path d="M10 16C10 16 16 15 24 15C27 15 29 16 29 16" stroke="#ffffff" strokeWidth="1.5" strokeLinecap="round" opacity="0.6" />

      {/* Digital Curved Visor */}
      <rect x="8" y="20" width="23" height="13" rx="5" fill="url(#botVisorGrad)" stroke="#1e1b4b" strokeWidth="1" />
      <path d="M9 22L16 22L13 31H9V22Z" fill="#ffffff" opacity="0.15" />

      {/* Glowing Cyan Eyes */}
      <ellipse cx="14" cy="26" rx="2.5" ry="3" fill="#38bdf8" />
      <ellipse cx="14" cy="26" rx="1.2" ry="1.8" fill="#ffffff" />
      <ellipse cx="25" cy="26" rx="2.5" ry="3" fill="#38bdf8" />
      <ellipse cx="25" cy="26" rx="1.2" ry="1.8" fill="#ffffff" />

      {/* Friendly Speaker Grille */}
      <rect x="16" y="34" width="7" height="2" rx="1" fill="#5b21b6" />
    </svg>
  )
}

// 9. Column 3 - Item 2: Cognitive Processor CPU Neural Chip (Agent 2: Feasibility)
function Agent2CpuRefIcon({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <defs>
        <linearGradient id="cpuGoldPin" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fef08a" />
          <stop offset="100%" stopColor="#eab308" />
        </linearGradient>
        <linearGradient id="cpuDieGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#0284c7" />
          <stop offset="50%" stopColor="#0369a1" />
          <stop offset="100%" stopColor="#082f49" />
        </linearGradient>
        <linearGradient id="cpuHeatGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f8fafc" />
          <stop offset="50%" stopColor="#e2e8f0" />
          <stop offset="100%" stopColor="#94a3b8" />
        </linearGradient>
      </defs>

      {/* Gold Connective Bus Pins */}
      <rect x="13" y="2" width="2" height="6" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="18" y="2" width="2" height="6" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="23" y="2" width="2" height="6" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="28" y="2" width="2" height="6" rx="0.5" fill="url(#cpuGoldPin)" />

      <rect x="13" y="40" width="2" height="6" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="18" y="40" width="2" height="6" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="23" y="40" width="2" height="6" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="28" y="40" width="2" height="6" rx="0.5" fill="url(#cpuGoldPin)" />

      <rect x="2" y="13" width="6" height="2" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="2" y="18" width="6" height="2" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="2" y="23" width="6" height="2" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="2" y="28" width="6" height="2" rx="0.5" fill="url(#cpuGoldPin)" />

      <rect x="40" y="13" width="6" height="2" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="40" y="18" width="6" height="2" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="40" y="23" width="6" height="2" rx="0.5" fill="url(#cpuGoldPin)" />
      <rect x="40" y="28" width="6" height="2" rx="0.5" fill="url(#cpuGoldPin)" />

      {/* Main Semiconductor Die */}
      <rect x="7" y="7" width="34" height="34" rx="5" fill="url(#cpuDieGrad)" stroke="#0c4a6e" strokeWidth="1.5" />

      {/* Glowing Circuit Traces */}
      <path d="M10 14H16V10M10 34H16V38M38 14H32V10M38 34H32V38" stroke="#38bdf8" strokeWidth="1.2" strokeLinecap="round" />
      <circle cx="16" cy="10" r="1.2" fill="#38bdf8" />
      <circle cx="32" cy="10" r="1.2" fill="#38bdf8" />
      <circle cx="16" cy="38" r="1.2" fill="#38bdf8" />
      <circle cx="32" cy="38" r="1.2" fill="#38bdf8" />

      {/* Heat Spreader */}
      <rect x="14" y="14" width="20" height="20" rx="3.5" fill="url(#cpuHeatGrad)" stroke="#64748b" strokeWidth="1" />
      <path d="M15 15L25 15L15 25Z" fill="#ffffff" opacity="0.6" />

      {/* Core Neural Icon */}
      <rect x="18" y="18" width="12" height="12" rx="2" fill="#0284c7" />
      <path d="M21 24H27M24 21V27" stroke="#ffffff" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="24" cy="24" r="2.2" fill="#38bdf8" />

      {/* 7-Dept Audit Mini Calendar Badge */}
      <g transform="translate(28, 26)">
        <rect x="0" y="0" width="16" height="16" rx="3" fill="#ffffff" stroke="#0284c7" strokeWidth="1.2" />
        <rect x="0" y="0" width="16" height="4.5" rx="2" fill="#0284c7" />
        <circle cx="4" cy="2" r="1" fill="#ffffff" />
        <circle cx="12" cy="2" r="1" fill="#ffffff" />
        <path d="M4 10L7 13L12 7" stroke="#16a34a" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  )
}

// 10. Column 3 - Item 3: 24/7 Radar Surveillance (Agent 3: Surveillance)
function Agent3RadarRefIcon({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <defs>
        <linearGradient id="radarBezel" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#334155" />
          <stop offset="100%" stopColor="#0f172a" />
        </linearGradient>
        <radialGradient id="radarScreen" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#065f46" />
          <stop offset="70%" stopColor="#064e3b" />
          <stop offset="100%" stopColor="#022c22" />
        </radialGradient>
        <linearGradient id="radarSweep" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#34d399" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#059669" stopOpacity="0.0" />
        </linearGradient>
      </defs>

      {/* Outer Tactical Bezel */}
      <circle cx="24" cy="24" r="22" fill="url(#radarBezel)" stroke="#10b981" strokeWidth="1.5" />
      <circle cx="6" cy="24" r="1" fill="#94a3b8" />
      <circle cx="42" cy="24" r="1" fill="#94a3b8" />
      <circle cx="24" cy="6" r="1" fill="#94a3b8" />
      <circle cx="24" cy="42" r="1" fill="#94a3b8" />

      {/* Radar Screen Display */}
      <circle cx="24" cy="24" r="18" fill="url(#radarScreen)" />

      {/* Concentric Rings */}
      <circle cx="24" cy="24" r="14" stroke="#10b981" strokeWidth="1" strokeDasharray="3 3" opacity="0.6" fill="none" />
      <circle cx="24" cy="24" r="9" stroke="#10b981" strokeWidth="1" strokeDasharray="2 2" opacity="0.7" fill="none" />
      <circle cx="24" cy="24" r="4" stroke="#34d399" strokeWidth="1" fill="none" />

      {/* Crosshair Grids */}
      <line x1="24" y1="6" x2="24" y2="42" stroke="#10b981" strokeWidth="1" opacity="0.4" />
      <line x1="6" y1="24" x2="42" y2="24" stroke="#10b981" strokeWidth="1" opacity="0.4" />

      {/* Sweep Beam Cone */}
      <path d="M24 24L37 11A18 18 0 0 1 42 24Z" fill="url(#radarSweep)" />
      <line x1="24" y1="24" x2="37" y2="11" stroke="#6ee7b7" strokeWidth="1.8" strokeLinecap="round" />

      {/* Threat Ping */}
      <circle cx="34" cy="16" r="3.2" fill="#ef4444" />
      <circle cx="34" cy="16" r="5" stroke="#f87171" strokeWidth="1" opacity="0.8" fill="none" />
      <circle cx="34" cy="16" r="1.3" fill="#ffffff" />
      <circle cx="16" cy="30" r="2" fill="#facc15" />
      <circle cx="24" cy="24" r="2.5" fill="#34d399" />
    </svg>
  )
}

// 11. Column 4 Header: White Shield Check
function ShieldCheckRefIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="shldHdrGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#bfdbfe" />
        </linearGradient>
      </defs>
      <path
        d="M12 2L20 5.5V12C20 17 16 21 12 22C8 21 4 17 4 12V5.5L12 2Z"
        fill="url(#shldHdrGrad)"
      />
      <path d="M8.5 12L11 14.5L15.5 9.5" stroke="#1d4ed8" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// 12. Column 4 Center Graphic: Heraldic Governance Shield Gate (Human Approval Gate)
function GovernanceShieldGateCenterSvg({ size = 52 }) {
  return (
    <svg width={size} height={size * 1.05} viewBox="0 0 54 58" fill="none">
      <defs>
        <linearGradient id="govGoldBevel" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fef08a" />
          <stop offset="40%" stopColor="#f59e0b" />
          <stop offset="80%" stopColor="#b45309" />
          <stop offset="100%" stopColor="#78350f" />
        </linearGradient>
        <linearGradient id="govShieldInner" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#2563eb" />
          <stop offset="50%" stopColor="#1d4ed8" />
          <stop offset="100%" stopColor="#1e3a8a" />
        </linearGradient>
        <linearGradient id="govGreenEmblem" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#4ade80" />
          <stop offset="50%" stopColor="#16a34a" />
          <stop offset="100%" stopColor="#14532d" />
        </linearGradient>
      </defs>

      {/* Main Heraldic Outer Gold Shield */}
      <path
        d="M27 3L49 11V27C49 40 39.5 50.5 27 55C14.5 50.5 5 40 5 27V11L27 3Z"
        fill="url(#govGoldBevel)"
      />

      {/* Inner Inset Enamel Royal Cobalt Shield */}
      <path
        d="M27 7L45 14V26C45 37 37 46.5 27 50.5C17 46.5 9 37 9 26V14L27 7Z"
        fill="url(#govShieldInner)"
      />
      <path
        d="M27 7L13 14.5V26C13 35 19 43 27 47V7Z"
        fill="#ffffff"
        opacity="0.12"
      />

      {/* Security Gateway Arch & Brass Padlock */}
      <rect x="22" y="36" width="10" height="8" rx="2" fill="url(#govGoldBevel)" stroke="#78350f" strokeWidth="0.8" />
      <path d="M24.5 36V32.5C24.5 30.5 29.5 30.5 29.5 32.5V36" stroke="#fbbf24" strokeWidth="2" strokeLinecap="round" />
      <circle cx="27" cy="39.5" r="1.2" fill="#78350f" />

      {/* 3D Centerpiece: 100% Sign-Off Verified Emerald Medallion */}
      <circle cx="27" cy="23" r="11" fill="url(#govGreenEmblem)" stroke="#ffffff" strokeWidth="1.8" />
      <path
        d="M21 23L25.5 27.5L33.5 19"
        stroke="#ffffff"
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// 13. Column 5 Header: 3-Person Team Avatar (Closed-Loop)
function TeamClosedLoopHeaderRefIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="teamHdrGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#fecaca" />
        </linearGradient>
      </defs>
      <circle cx="12" cy="7" r="3.5" fill="url(#teamHdrGrad)" />
      <path d="M6 18C6 14.7 8.7 12 12 12C15.3 12 18 14.7 18 18V19H6V18Z" fill="url(#teamHdrGrad)" />
      <circle cx="5" cy="8.5" r="2.5" fill="#fca5a5" />
      <path d="M1 18C1 15.5 3 13.5 5.5 13.5C6.3 13.5 7 13.7 7.6 14.1C6.6 15.2 6 16.5 6 18H1Z" fill="#fca5a5" />
      <circle cx="19" cy="8.5" r="2.5" fill="#fca5a5" />
      <path d="M23 18C23 15.5 21 13.5 18.5 13.5C17.7 13.5 17 13.7 16.4 14.1C17.4 15.2 18 16.5 18 18H23Z" fill="#fca5a5" />
    </svg>
  )
}

// 14. Column 5 - Item 1: Dual Email Routing (CS & Operational Leads)
function DualEmailRefIcon({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <defs>
        <linearGradient id="mailEnvGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#fef3c7" />
        </linearGradient>
        <linearGradient id="mailFlapGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#fef08a" />
          <stop offset="100%" stopColor="#f59e0b" />
        </linearGradient>
        <linearGradient id="opsArrowGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#0284c7" />
        </linearGradient>
        <linearGradient id="csArrowGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#c084fc" />
          <stop offset="100%" stopColor="#7c3aed" />
        </linearGradient>
      </defs>

      {/* Main 3D Envelope Body */}
      <rect x="5" y="14" width="28" height="22" rx="3.5" fill="url(#mailEnvGrad)" stroke="#d97706" strokeWidth="1.5" />
      <path d="M5 36L16 26M33 36L22 26" stroke="#f59e0b" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M5 16L19 27L33 16" fill="url(#mailFlapGrad)" stroke="#d97706" strokeWidth="1.4" strokeLinejoin="round" />
      <circle cx="19" cy="26" r="3.5" fill="#d97706" />
      <circle cx="19" cy="26" r="2.2" fill="#fef08a" />

      {/* Dual Outbound Routing Swooshes */}
      <path d="M26 14C32 10 38 7 43 7" stroke="url(#opsArrowGrad)" strokeWidth="2.8" strokeLinecap="round" fill="none" />
      <path d="M38 4L44 7L39 11" fill="url(#opsArrowGrad)" />

      <path d="M26 22C32 24 38 31 43 37" stroke="url(#csArrowGrad)" strokeWidth="2.8" strokeLinecap="round" fill="none" />
      <path d="M38 39L44 38L42 32" fill="url(#csArrowGrad)" />

      {/* Unread Counter Badge */}
      <circle cx="8" cy="11" r="5" fill="#ef4444" stroke="#ffffff" strokeWidth="1.5" />
      <text x="8" y="13.5" fontSize="7" fontWeight="900" fill="#ffffff" textAnchor="middle">2</text>
    </svg>
  )
}

// 15. Column 5 - Item 2: Corrective Action Gear with Wrench
function CorrectiveActionRefIcon({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <defs>
        <linearGradient id="actGearGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#4ade80" />
          <stop offset="50%" stopColor="#16a34a" />
          <stop offset="100%" stopColor="#14532d" />
        </linearGradient>
        <linearGradient id="toolChrome" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f8fafc" />
          <stop offset="40%" stopColor="#cbd5e1" />
          <stop offset="80%" stopColor="#64748b" />
          <stop offset="100%" stopColor="#334155" />
        </linearGradient>
        <linearGradient id="actionWrenchGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="50%" stopColor="#94a3b8" />
          <stop offset="100%" stopColor="#475569" />
        </linearGradient>
      </defs>

      {/* Emerald Heavy Duty Gear Base */}
      <circle cx="22" cy="24" r="16" fill="url(#actGearGrad)" stroke="#14532d" strokeWidth="1.2" />
      <path
        d="M22 4V8M22 40V44M4 24H8M40 24H44M9 11L12 14M32 34L35 37M9 37L12 34M32 14L35 11"
        stroke="#86efac"
        strokeWidth="3.2"
        strokeLinecap="round"
      />
      <circle cx="22" cy="24" r="9" fill="#14532d" />

      {/* 3D Crossed Precision Chrome Wrench */}
      <path
        d="M10 36L28 14M28 14C27 12 28 9 30 8C32 7 35 8 36 10C37 12 36 15 34 16C33 17 30 17 28 14Z"
        stroke="url(#toolChrome)"
        strokeWidth="3.2"
        strokeLinecap="round"
      />
      {/* Crossed Chrome Screwdriver */}
      <path
        d="M34 36L16 14M16 14L13 11M34 36L37 39"
        stroke="url(#actionWrenchGrad)"
        strokeWidth="2.8"
        strokeLinecap="round"
      />

      {/* Verified Green Resolution Badge */}
      <g transform="translate(26, 26)">
        <circle cx="9" cy="9" r="8.5" fill="#10b981" stroke="#ffffff" strokeWidth="1.8" />
        <path d="M5.5 9L8 11.5L12.5 6.5" stroke="#ffffff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </svg>
  )
}

// 16. Column 5 - Item 3: Command Portals Monitor & Bullseye Target
function CommandPortalRefIcon({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
      <defs>
        <linearGradient id="monFrameGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#475569" />
          <stop offset="100%" stopColor="#0f172a" />
        </linearGradient>
        <linearGradient id="monScreenGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#0f172a" />
          <stop offset="100%" stopColor="#1e293b" />
        </linearGradient>
        <linearGradient id="monStandGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#e2e8f0" />
          <stop offset="100%" stopColor="#94a3b8" />
        </linearGradient>
        <linearGradient id="targetRedGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ef4444" />
          <stop offset="100%" stopColor="#b91c1c" />
        </linearGradient>
      </defs>

      {/* Monitor Stand */}
      <rect x="18" y="32" width="6" height="7" fill="url(#monStandGrad)" />
      <path d="M12 39H30L32 42H10L12 39Z" fill="url(#monStandGrad)" stroke="#64748b" strokeWidth="0.8" />

      {/* Monitor Outer Chassis */}
      <rect x="3" y="6" width="36" height="27" rx="3.5" fill="url(#monFrameGrad)" stroke="#334155" strokeWidth="1.2" />

      {/* Dark Screen Display */}
      <rect x="5.5" y="8.5" width="31" height="22" rx="2" fill="url(#monScreenGrad)" />

      {/* Colorful 3D KPI Bars */}
      <rect x="8" y="19" width="3.5" height="9" rx="1" fill="#38bdf8" />
      <rect x="13.5" y="14" width="3.5" height="14" rx="1" fill="#a855f7" />
      <rect x="19" y="11" width="3.5" height="17" rx="1" fill="#22c55e" />

      {/* OTIF Trajectory Trend Line */}
      <path d="M9 18L15 13L20 10L26 15" stroke="#f59e0b" strokeWidth="1.6" strokeLinecap="round" fill="none" />
      <circle cx="15" cy="13" r="1.5" fill="#fef08a" />
      <circle cx="20" cy="10" r="1.5" fill="#fef08a" />

      {/* Specular Glare */}
      <path d="M6 9L18 9L8 28H6V9Z" fill="#ffffff" opacity="0.1" />

      {/* 3D Delivery Bullseye Target */}
      <g transform="translate(26, 22)">
        <circle cx="11" cy="11" r="10.5" fill="url(#targetRedGrad)" stroke="#7f1d1d" strokeWidth="1" />
        <circle cx="11" cy="11" r="7.5" fill="#ffffff" />
        <circle cx="11" cy="11" r="5" fill="#ef4444" />
        <circle cx="11" cy="11" r="2.5" fill="#facc15" />
        <line x1="18" y1="4" x2="11" y2="11" stroke="#f59e0b" strokeWidth="1.8" strokeLinecap="round" />
        <polygon points="18,4 20,2 17,1" fill="#f59e0b" />
      </g>
    </svg>
  )
}

export default function ArchitectureDiagram() {
  const navigate = useNavigate()
  const [selectedCardId, setSelectedCardId] = useState('agent2')
  const [ordersProgressData, setOrdersProgressData] = useState({ customers: [], orders: [] })
  const [loadingOrders, setLoadingOrders] = useState(true)
  const [selectedCustomerFilter, setSelectedCustomerFilter] = useState('ALL')
  const [apiCategory, setApiCategory] = useState('ALL')
  const [expandedApiId, setExpandedApiId] = useState('feasibility-assess')
  const [showProblemSolution, setShowProblemSolution] = useState(false)

  // Fetch real customer orders progress from backend
  useEffect(() => {
    let isMounted = true
    async function fetchProgress() {
      try {
        setLoadingOrders(true)
        const res = await dashboardApi.getOrdersProgress()
        if (isMounted && res) {
          setOrdersProgressData(res)
        }
      } catch (err) {
        console.error('Failed to load orders progress data:', err)
      } finally {
        if (isMounted) setLoadingOrders(false)
      }
    }
    fetchProgress()
    return () => {
      isMounted = false
    }
  }, [])

  const activeCard = CARD_SPECS[selectedCardId] || CARD_SPECS.agent2

  // Filter orders by selected customer
  const filteredOrders =
    selectedCustomerFilter === 'ALL'
      ? ordersProgressData.orders
      : ordersProgressData.orders.filter(
          (o) => o.customer_name?.toLowerCase() === selectedCustomerFilter.toLowerCase()
        )

  return (
    <div className="page-stack" style={{ gap: 16, paddingBottom: 32 }}>
      {/* =========================================================================
          FOUR QUADRANT DIVISIONS (2x2 GRID)
          ========================================================================= */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.25fr) minmax(0, 0.95fr)',
          gap: 16,
          alignItems: 'stretch',
        }}
      >
        {/* =======================================================================
            QUADRANT 1: TOP-LEFT — ARCHITECTURE DIAGRAM (COMPACT, NO EXTRA SPACE)
            ======================================================================= */}
        <div
          className="card"
          style={{
            background: 'var(--surface-hi)',
            border: '1px solid var(--line)',
            borderRadius: 10,
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          {/* Card Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 10,
              paddingBottom: 8,
              borderBottom: '1px solid var(--line)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: 6,
                  background: 'linear-gradient(135deg, #6f3dba 0%, #1f2f59 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#ffffff',
                }}
              >
                <Factory size={14} />
              </div>
              <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                System Architecture Pipeline
              </strong>
            </div>
          </div>

          {/* 5-STAGE COMPACT ARCHITECTURE PIPELINE (MATCHING MANUFACTURING CARDS WITH VIBRANT VECTOR ICONS) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'stretch',
              gap: 5,
              flex: 1,
            }}
          >
            {/* COLUMN 1: SOURCE SYSTEM */}
            <div
              onClick={() => setSelectedCardId('erp_mms')}
              style={{
                flex: '1.05 1 0',
                borderRadius: 7,
                border: '1px solid',
                borderColor: ['erp_mms', 'mes_wms', 'qms_tms', 'sources'].includes(selectedCardId) ? '#b91c1c' : '#fca5a5',
                background: 'var(--kg-bg-2)',
                display: 'flex',
                flexDirection: 'column',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                boxShadow: ['erp_mms', 'mes_wms', 'qms_tms', 'sources'].includes(selectedCardId) ? '0 0 0 2px #b91c1c, 0 4px 12px rgba(185, 28, 28, 0.15)' : 'none',
              }}
              title="Click to view Stage 1: Source System (7 Enterprise Silos) specifications"
            >
              <div
                style={{
                  background: '#991b1b',
                  color: '#ffffff',
                  padding: '5px 6px',
                  borderRadius: '6px 6px 0 0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                  textAlign: 'center',
                  lineHeight: 1.15,
                }}
              >
                <FactoryRefIcon size={18} />
                <div>
                  <div style={{ fontSize: 9, fontWeight: 900, textTransform: 'uppercase' }}>
                    1. SOURCE SYSTEM
                  </div>
                  <div style={{ fontSize: 7, opacity: 0.9 }}>7 Enterprise Silos</div>
                </div>
              </div>

              <div style={{ padding: 4, display: 'flex', flexDirection: 'column', gap: 4, flex: 1, justifyContent: 'center' }}>
                {/* ERP & MMS */}
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedCardId('erp_mms')
                  }}
                  style={{
                    background: selectedCardId === 'erp_mms' || selectedCardId === 'erp_mes' ? '#e0f2fe' : '#f0f9ff',
                    border: '1px solid',
                    borderColor: selectedCardId === 'erp_mms' || selectedCardId === 'erp_mes' ? '#0284c7' : '#bae6fd',
                    borderRadius: 5,
                    padding: '4px 6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    cursor: 'pointer',
                    boxShadow: selectedCardId === 'erp_mms' || selectedCardId === 'erp_mes' ? '0 0 0 2px #0284c7' : 'none',
                  }}
                  title="Click to view ERP & MMS specifications"
                >
                  <img src={erpMmsImg} alt="ERP & MMS" style={{ width: 30, height: 30, objectFit: 'contain', flexShrink: 0 }} />
                  <div style={{ minWidth: 0, lineHeight: 1.15 }}>
                    <div style={{ fontSize: 9, fontWeight: 800, color: '#0369a1' }}>ERP &amp; MMS</div>
                    <div style={{ fontSize: 7.5, color: '#0284c7' }}>SAP / OData / BOM</div>
                  </div>
                </div>

                {/* MES & WMS */}
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedCardId('mes_wms')
                  }}
                  style={{
                    background: selectedCardId === 'mes_wms' || selectedCardId === 'excel_files' ? '#dcfce7' : '#f0fdf4',
                    border: '1px solid',
                    borderColor: selectedCardId === 'mes_wms' || selectedCardId === 'excel_files' ? '#10b981' : '#bbf7d0',
                    borderRadius: 5,
                    padding: '4px 6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    cursor: 'pointer',
                    boxShadow: selectedCardId === 'mes_wms' || selectedCardId === 'excel_files' ? '0 0 0 2px #10b981' : 'none',
                  }}
                  title="Click to view MES & WMS specifications"
                >
                  <img src={mesWmsImg} alt="MES & WMS" style={{ width: 30, height: 30, objectFit: 'contain', flexShrink: 0 }} />
                  <div style={{ minWidth: 0, lineHeight: 1.15 }}>
                    <div style={{ fontSize: 9, fontWeight: 800, color: '#15803d' }}>MES &amp; WMS</div>
                    <div style={{ fontSize: 7.5, color: '#16a34a' }}>Siemens / Inventory</div>
                  </div>
                </div>

                {/* QMS & TMS */}
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedCardId('qms_tms')
                  }}
                  style={{
                    background: selectedCardId === 'qms_tms' || selectedCardId === 'apis_etl' ? '#ede9fe' : '#faf5ff',
                    border: '1px solid',
                    borderColor: selectedCardId === 'qms_tms' || selectedCardId === 'apis_etl' ? '#8b5cf6' : '#ddd6fe',
                    borderRadius: 5,
                    padding: '4px 6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    cursor: 'pointer',
                    boxShadow: selectedCardId === 'qms_tms' || selectedCardId === 'apis_etl' ? '0 0 0 2px #8b5cf6' : 'none',
                  }}
                  title="Click to view QMS & TMS specifications"
                >
                  <img src={qmsTmsImg} alt="QMS & TMS" style={{ width: 30, height: 30, objectFit: 'contain', flexShrink: 0 }} />
                  <div style={{ minWidth: 0, lineHeight: 1.15 }}>
                    <div style={{ fontSize: 9, fontWeight: 800, color: '#6d28d9' }}>QMS &amp; TMS</div>
                    <div style={{ fontSize: 7.5, color: '#7c3aed' }}>QA Holds / Logistics</div>
                  </div>
                </div>
              </div>
            </div>

            {/* FLOW ARROW */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
              <ArrowRight size={13} />
            </div>

            {/* COLUMN 2: API GATEWAY */}
            <div
              onClick={() => setSelectedCardId('gateway')}
              style={{
                flex: '0.92 1 0',
                borderRadius: 7,
                border: '1px solid',
                borderColor: selectedCardId === 'gateway' ? '#1e40af' : '#bfdbfe',
                background: 'var(--kg-bg-2)',
                display: 'flex',
                flexDirection: 'column',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                boxShadow: selectedCardId === 'gateway' ? '0 0 0 2px #1e40af, 0 4px 12px rgba(30, 64, 175, 0.15)' : 'none',
              }}
              title="Click to view Stage 2: API Gateway (FastAPI Engine) specifications & interactive endpoints"
            >
              <div
                style={{
                  background: '#1e40af',
                  color: '#ffffff',
                  padding: '5px 6px',
                  borderRadius: '6px 6px 0 0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 5,
                  textAlign: 'center',
                  lineHeight: 1.15,
                }}
              >
                <CylinderRefIcon size={16} />
                <div>
                  <div style={{ fontSize: 9, fontWeight: 900, textTransform: 'uppercase' }}>
                    2. API GATEWAY
                  </div>
                  <div style={{ fontSize: 7, opacity: 0.9 }}>FastAPI Engine</div>
                </div>
              </div>

              <div
                style={{
                  padding: 6,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flex: 1,
                  gap: 4,
                  textAlign: 'center',
                  background: 'var(--kg-bg-3)',
                }}
              >
                <img src={fastapiGatewayImg} alt="FastAPI Engine" style={{ width: 48, height: 48, objectFit: 'contain', margin: '2px 0' }} />
                <div style={{ fontSize: 9.5, fontWeight: 800, color: '#1e3a8a', lineHeight: 1.2 }}>
                  FastAPI Engine
                </div>
                <div style={{ display: 'flex', gap: 3, justifyContent: 'center' }}>
                  <span style={{ fontSize: 7, fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: 'var(--surface-hi)', color: '#0369a1', border: '1px solid #bae6fd' }}>Port 8000 · SSE</span>
                </div>
                <div style={{ fontSize: 7, color: 'var(--text-muted)', fontWeight: 600 }}>
                  Async Normalizer
                </div>
              </div>
            </div>

            {/* FLOW ARROW */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
              <ArrowRight size={13} />
            </div>

            {/* COLUMN 3: MULTI-AGENT CORE */}
            <div
              onClick={() => setSelectedCardId('agent2')}
              style={{
                flex: '1.45 1 0',
                borderRadius: 7,
                border: '1px solid',
                borderColor: ['agent1', 'agent2', 'agent3', 'cleaned_data', 'semantic_model', 'aggregated_data'].includes(selectedCardId) ? '#581c87' : '#c084fc',
                background: 'var(--kg-bg-2)',
                display: 'flex',
                flexDirection: 'column',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                boxShadow: ['agent1', 'agent2', 'agent3', 'cleaned_data', 'semantic_model', 'aggregated_data'].includes(selectedCardId) ? '0 0 0 2px #581c87, 0 4px 12px rgba(88, 28, 135, 0.12)' : 'none',
              }}
              title="Click to view Stage 3: Multi-Agent Core (3 Autonomous Cognitive Engines)"
            >
              <div
                style={{
                  background: '#581c87',
                  color: '#ffffff',
                  padding: '5px 6px',
                  borderRadius: '6px 6px 0 0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 5,
                  textAlign: 'center',
                  lineHeight: 1.15,
                }}
              >
                <MultiAgentHeaderRefIcon size={16} />
                <div>
                  <div style={{ fontSize: 9, fontWeight: 900, textTransform: 'uppercase' }}>
                    3. MULTI-AGENT CORE
                  </div>
                  <div style={{ fontSize: 7, opacity: 0.9 }}>3 Autonomous Cognitive Engines</div>
                </div>
              </div>

              <div
                style={{
                  padding: 4,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 3.5,
                  flex: 1,
                  justifyContent: 'center',
                  background: 'var(--kg-bg-3)',
                }}
              >
                {/* Agent 1: Assistant */}
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedCardId('agent1')
                  }}
                  style={{
                    border: '1px solid',
                    borderColor: selectedCardId === 'agent1' || selectedCardId === 'cleaned_data' ? '#6f3dba' : '#e9d5ff',
                    background: selectedCardId === 'agent1' || selectedCardId === 'cleaned_data' ? '#ede9fe' : 'var(--surface-hi)',
                    borderRadius: 5,
                    padding: '4px 6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    cursor: 'pointer',
                    boxShadow: selectedCardId === 'agent1' || selectedCardId === 'cleaned_data' ? '0 0 0 2px #6f3dba' : 'none',
                  }}
                  title="Click to view Agent 1: Assistant specifications"
                >
                  <img src={agent1AssistantImg} alt="Agent 1: Assistant" style={{ width: 30, height: 30, objectFit: 'contain', flexShrink: 0 }} />
                  <div style={{ minWidth: 0, lineHeight: 1.15 }}>
                    <div style={{ fontSize: 9, fontWeight: 800, color: '#581c87' }}>
                      Agent 1: Assistant
                    </div>
                    <div style={{ fontSize: 7.5, color: '#7e22ce' }}>Natural Language Q&amp;A - SQL</div>
                  </div>
                </div>

                {/* Agent 2: Feasibility */}
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedCardId('agent2')
                  }}
                  style={{
                    border: '1px solid',
                    borderColor: selectedCardId === 'agent2' || selectedCardId === 'semantic_model' ? '#0284c7' : '#bae6fd',
                    background: selectedCardId === 'agent2' || selectedCardId === 'semantic_model' ? '#e0f2fe' : 'var(--surface-hi)',
                    borderRadius: 5,
                    padding: '4px 6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    cursor: 'pointer',
                    boxShadow: selectedCardId === 'agent2' || selectedCardId === 'semantic_model' ? '0 0 0 2px #0284c7' : 'none',
                  }}
                  title="Click to view Agent 2: Feasibility Engine specifications"
                >
                  <img src={agent2FeasibilityImg} alt="Agent 2: Feasibility" style={{ width: 30, height: 30, objectFit: 'contain', flexShrink: 0 }} />
                  <div style={{ minWidth: 0, lineHeight: 1.15 }}>
                    <div style={{ fontSize: 9, fontWeight: 800, color: '#0369a1' }}>
                      Agent 2: Feasibility
                    </div>
                    <div style={{ fontSize: 7.5, color: '#0284c7' }}>7-Dept Audit - Delivery Date</div>
                  </div>
                </div>

                {/* Agent 3: Surveillance */}
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedCardId('agent3')
                  }}
                  style={{
                    border: '1px solid',
                    borderColor: selectedCardId === 'agent3' || selectedCardId === 'aggregated_data' ? '#10b981' : '#a7f3d0',
                    background: selectedCardId === 'agent3' || selectedCardId === 'aggregated_data' ? '#dcfce7' : 'var(--surface-hi)',
                    borderRadius: 5,
                    padding: '4px 6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    cursor: 'pointer',
                    boxShadow: selectedCardId === 'agent3' || selectedCardId === 'aggregated_data' ? '0 0 0 2px #10b981' : 'none',
                  }}
                  title="Click to view Agent 3: Surveillance Radar specifications"
                >
                  <img src={agent3SurveillanceImg} alt="Agent 3: Surveillance" style={{ width: 30, height: 30, objectFit: 'contain', flexShrink: 0 }} />
                  <div style={{ minWidth: 0, lineHeight: 1.15 }}>
                    <div style={{ fontSize: 9, fontWeight: 800, color: '#15803d' }}>
                      Agent 3: Surveillance
                    </div>
                    <div style={{ fontSize: 7.5, color: '#16a34a' }}>24/7 Monitor - 3 Day SLA</div>
                  </div>
                </div>
              </div>
            </div>

            {/* FLOW ARROW */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
              <ArrowRight size={13} />
            </div>

            {/* COLUMN 4: GOVERNANCE */}
            <div
              onClick={() => setSelectedCardId('governance')}
              style={{
                flex: '0.95 1 0',
                borderRadius: 7,
                border: '1px solid',
                borderColor: selectedCardId === 'governance' || selectedCardId === 'consumption' ? '#1d4ed8' : '#93c5fd',
                background: 'var(--kg-bg-2)',
                display: 'flex',
                flexDirection: 'column',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                boxShadow: selectedCardId === 'governance' || selectedCardId === 'consumption' ? '0 0 0 2px #1d4ed8, 0 4px 12px rgba(29, 78, 216, 0.15)' : 'none',
              }}
              title="Click to view Stage 4: Governance (Human CS Sign-Off) specifications"
            >
              <div
                style={{
                  background: '#1d4ed8',
                  color: '#ffffff',
                  padding: '5px 6px',
                  borderRadius: '6px 6px 0 0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 5,
                  textAlign: 'center',
                  lineHeight: 1.15,
                }}
              >
                <ShieldCheckRefIcon size={16} />
                <div>
                  <div style={{ fontSize: 9, fontWeight: 900, textTransform: 'uppercase' }}>
                    4. GOVERNANCE
                  </div>
                  <div style={{ fontSize: 7, opacity: 0.9 }}>Human CS Sign-Off</div>
                </div>
              </div>

              <div
                style={{
                  padding: 6,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flex: 1,
                  gap: 3,
                  textAlign: 'center',
                  background: 'var(--kg-bg-3)',
                }}
              >
                <img src={governanceApprovalImg} alt="Human Approval Gate" style={{ width: 48, height: 48, objectFit: 'contain', margin: '2px 0' }} />
                <div style={{ fontSize: 9.5, fontWeight: 800, color: '#1e3a8a', lineHeight: 1.2 }}>
                  Human Approval Gate
                </div>
                <div style={{ display: 'flex', gap: 3, justifyContent: 'center' }}>
                  <span style={{ fontSize: 7, fontWeight: 700, padding: '1px 5px', borderRadius: 3, background: 'var(--surface-hi)', color: '#1d4ed8', border: '1px solid #bfdbfe' }}>100% Sign-Off Gate</span>
                </div>
                <div style={{ fontSize: 6.8, color: 'var(--text-muted)', fontWeight: 600 }}>
                  Segregation of Duties
                </div>
              </div>
            </div>

            {/* FLOW ARROW */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
              <ArrowRight size={13} />
            </div>

            {/* COLUMN 5: CLOSED-LOOP */}
            <div
              onClick={() => setSelectedCardId('dual_email')}
              style={{
                flex: '1.1 1 0',
                borderRadius: 7,
                border: '1px solid',
                borderColor: ['dual_email', 'corrective_action', 'command_portals', 'dispatch'].includes(selectedCardId) ? '#991b1b' : '#fca5a5',
                background: 'var(--kg-bg-2)',
                display: 'flex',
                flexDirection: 'column',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                boxShadow: ['dual_email', 'corrective_action', 'command_portals', 'dispatch'].includes(selectedCardId) ? '0 0 0 2px #991b1b, 0 4px 12px rgba(153, 27, 27, 0.15)' : 'none',
              }}
              title="Click to view Stage 5: Closed-Loop (Email, Visualization, Alerts) specifications"
            >
              <div
                style={{
                  background: '#991b1b',
                  color: '#ffffff',
                  padding: '5px 6px',
                  borderRadius: '6px 6px 0 0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 5,
                  textAlign: 'center',
                  lineHeight: 1.15,
                }}
              >
                <TeamClosedLoopHeaderRefIcon size={18} />
                <div>
                  <div style={{ fontSize: 9, fontWeight: 900, textTransform: 'uppercase' }}>
                    5. CLOSED-LOOP
                  </div>
                  <div style={{ fontSize: 7, opacity: 0.9 }}>Actions &amp; Dispatch</div>
                </div>
              </div>

              <div style={{ padding: 4, display: 'flex', flexDirection: 'column', gap: 4, flex: 1, justifyContent: 'center' }}>
                {/* Email */}
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedCardId('dual_email')
                  }}
                  style={{
                    background: selectedCardId === 'dual_email' || selectedCardId === 'dispatch' ? '#fef3c7' : 'var(--surface-hi)',
                    border: '1px solid',
                    borderColor: selectedCardId === 'dual_email' || selectedCardId === 'dispatch' ? '#d97706' : 'var(--line)',
                    borderRadius: 5,
                    padding: '4px 6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    cursor: 'pointer',
                    boxShadow: selectedCardId === 'dual_email' || selectedCardId === 'dispatch' ? '0 0 0 2px #d97706' : 'none',
                  }}
                  title="Click to view Email Routing specifications"
                >
                  <img src={closedloopEmailImg} alt="Email" style={{ width: 30, height: 30, objectFit: 'contain', flexShrink: 0 }} />
                  <div style={{ minWidth: 0, lineHeight: 1.15 }}>
                    <div style={{ fontSize: 9, fontWeight: 800, color: '#92400e' }}>Email</div>
                    <div style={{ fontSize: 7.5, color: '#b45309' }}>CS &amp; Operational Leads</div>
                  </div>
                </div>

                {/* Visualization */}
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedCardId('command_portals')
                  }}
                  style={{
                    background: selectedCardId === 'command_portals' ? '#e0f2fe' : 'var(--surface-hi)',
                    border: '1px solid',
                    borderColor: selectedCardId === 'command_portals' ? '#0284c7' : 'var(--line)',
                    borderRadius: 5,
                    padding: '4px 6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    cursor: 'pointer',
                    boxShadow: selectedCardId === 'command_portals' ? '0 0 0 2px #0284c7' : 'none',
                  }}
                  title="Click to view Visualization & Command Portals specifications"
                >
                  <img src={closedloopVisualizationImg} alt="Visualization" style={{ width: 30, height: 30, objectFit: 'contain', flexShrink: 0 }} />
                  <div style={{ minWidth: 0, lineHeight: 1.15 }}>
                    <div style={{ fontSize: 9, fontWeight: 800, color: '#0369a1' }}>Visualization</div>
                    <div style={{ fontSize: 7.5, color: '#0284c7' }}>Command Portals &amp; Heatmaps</div>
                  </div>
                </div>

                {/* Alerts */}
                <div
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedCardId('corrective_action')
                  }}
                  style={{
                    background: selectedCardId === 'corrective_action' ? '#fee2e2' : 'var(--surface-hi)',
                    border: '1px solid',
                    borderColor: selectedCardId === 'corrective_action' ? '#dc2626' : 'var(--line)',
                    borderRadius: 5,
                    padding: '4px 6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    cursor: 'pointer',
                    boxShadow: selectedCardId === 'corrective_action' ? '0 0 0 2px #dc2626' : 'none',
                  }}
                  title="Click to view Alerts & Exception Remediation specifications"
                >
                  <img src={closedloopAlertsImg} alt="Alerts" style={{ width: 30, height: 30, objectFit: 'contain', flexShrink: 0 }} />
                  <div style={{ minWidth: 0, lineHeight: 1.15 }}>
                    <div style={{ fontSize: 9, fontWeight: 800, color: '#b91c1c' }}>Alerts</div>
                    <div style={{ fontSize: 7.5, color: '#dc2626' }}>Real-Time Exception Dispatch</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* =======================================================================
            QUADRANT 2: TOP-RIGHT — 5 ONE-WORD PROBLEMS SOLVED (ZERO DESCRIPTION)
            ======================================================================= */}
        <div
          className="card"
          style={{
            background: 'var(--surface-hi)',
            border: '1px solid var(--line)',
            borderRadius: 10,
            padding: '12px 16px',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          {/* Section Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 8,
              paddingBottom: 6,
              borderBottom: '1px solid var(--line)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <div
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: 5,
                  background: '#fee2e2',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#dc2626',
                }}
              >
                <Flame size={13} />
              </div>
              <strong style={{ fontSize: 12.5, color: 'var(--text-primary)' }}>
                Problems Solved by Agents
              </strong>
            </div>
            <span style={{ fontSize: 9.5, color: '#dc2626', fontWeight: 800, background: '#fee2e2', padding: '2px 7px', borderRadius: 4 }}>
              5 CORE PROBLEMS
            </span>
          </div>

          {/* 5 One-Word Problem Points (Clickable Cards with Active Ring) */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 5,
              flex: 1,
              justifyContent: 'center',
            }}
          >
            {[
              { id: 'problem_delays', num: '01', word: 'DELAYS', color: '#dc2626', bg: '#fee2e2', border: '#fca5a5', icon: Clock },
              { id: 'problem_blindspots', num: '02', word: 'BLINDSPOTS', color: '#d97706', bg: '#fef3c7', border: '#fde68a', icon: AlertTriangle },
              { id: 'problem_disruptions', num: '03', word: 'DISRUPTIONS', color: '#7c3aed', bg: '#ede9fe', border: '#ddd6fe', icon: Flame },
              { id: 'problem_bottlenecks', num: '04', word: 'BOTTLENECKS', color: '#0284c7', bg: '#e0f2fe', border: '#bae6fd', icon: Layers },
              { id: 'problem_sla_breaches', num: '05', word: 'SLA-BREACHES', color: '#b91c1c', bg: '#fef2f2', border: '#fecaca', icon: ShieldAlert },
            ].map((p) => {
              const isSelected = selectedCardId === p.id || selectedCardId === p.word.toLowerCase() || selectedCardId === p.num
              const Icon = p.icon
              return (
                <div
                  key={p.id}
                  onClick={() => setSelectedCardId(p.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 12px',
                    borderRadius: 6,
                    background: isSelected ? p.bg : 'var(--kg-bg-2)',
                    border: `1.5px solid ${isSelected ? p.color : 'var(--line)'}`,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    boxShadow: isSelected ? `0 0 0 2px ${p.color}, 0 4px 10px rgba(0,0,0,0.08)` : '0 1px 3px rgba(0,0,0,0.02)',
                    transform: isSelected ? 'translateX(3px)' : 'none',
                  }}
                  title={`Click to inspect details and points for ${p.word}`}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                    <span
                      style={{
                        fontFamily: 'monospace',
                        fontSize: 10,
                        fontWeight: 900,
                        color: p.color,
                        opacity: isSelected ? 1 : 0.85,
                      }}
                    >
                      {p.num}
                    </span>
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 900,
                        letterSpacing: '0.06em',
                        color: p.color,
                      }}
                    >
                      {p.word}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {isSelected && (
                      <span
                        style={{
                          fontSize: 8.5,
                          fontWeight: 800,
                          color: p.color,
                          background: 'var(--surface-hi)',
                          padding: '1px 5px',
                          borderRadius: 3,
                          border: `1px solid ${p.color}`,
                        }}
                      >
                        VIEWING ↙
                      </span>
                    )}
                    <Icon size={14} style={{ color: p.color, opacity: 0.9 }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* =======================================================================
            QUADRANT 3: BOTTOM-LEFT — DYNAMIC CARD INFORMATION / API DETAILS
            ======================================================================= */}
        <div
          className="card"
          style={{
            background: 'var(--surface-hi)',
            border: '1px solid var(--line)',
            borderRadius: 10,
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            boxShadow: 'var(--shadow-card)',
            minHeight: 380,
          }}
        >
          {/* SPECIALIZED VIEW WHEN API GATEWAY CARD IS SELECTED */}
          {activeCard.isProblem ? (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 8 }}>
              {/* Problem Header */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingBottom: 8,
                  borderBottom: '1px solid var(--line)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div
                    style={{
                      width: 26,
                      height: 26,
                      borderRadius: 6,
                      background: activeCard.bg,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: activeCard.color,
                      border: `1px solid ${activeCard.color}40`,
                    }}
                  >
                    <activeCard.icon size={15} />
                  </div>
                  <div>
                    <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                      {activeCard.title}
                    </strong>
                    <div style={{ fontSize: 9.5, color: 'var(--text-muted)' }}>
                      {activeCard.subtitle}
                    </div>
                  </div>
                </div>

                <span
                  style={{
                    fontSize: 9.5,
                    fontWeight: 800,
                    color: activeCard.color,
                    background: activeCard.bg,
                    padding: '2px 8px',
                    borderRadius: 4,
                    border: `1px solid ${activeCard.color}60`,
                  }}
                >
                  {activeCard.badge}
                </span>
              </div>

              {/* Problem Statements Section (Strictly 5 Lines) */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6, margin: '2px 0' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 11, fontWeight: 900, color: activeCard.color, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Problem Statements:
                  </span>
                  <span style={{ fontSize: 9.5, fontWeight: 700, color: 'var(--text-muted)' }}>
                    5 Failure Points
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {activeCard.problemPoints.map((pt, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 7,
                        background: 'var(--kg-bg-2)',
                        border: '1px solid var(--line)',
                        borderRadius: 6,
                        padding: '5px 8px',
                        fontSize: 10.5,
                        lineHeight: 1.3,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        minWidth: 0,
                      }}
                      title={`${pt.title}: ${pt.desc}`}
                    >
                      <span
                        style={{
                          width: 17,
                          height: 17,
                          borderRadius: '50%',
                          background: activeCard.bg,
                          color: activeCard.color,
                          fontSize: 9.5,
                          fontWeight: 900,
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        {idx + 1}
                      </span>
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0, flex: 1 }}>
                        <strong style={{ color: 'var(--text-primary)' }}>{pt.title}: </strong>
                        <span style={{ color: 'var(--text-secondary)' }}>{pt.desc}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Optional Multi-Agent Resolution (Toggled) */}
              {showProblemSolution && (
                <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 6, padding: '6px 10px', marginTop: 4 }}>
                  <span style={{ fontSize: 9.5, fontWeight: 900, color: '#15803d', textTransform: 'uppercase', display: 'block', marginBottom: 3 }}>
                    Autonomous Multi-Agent Solution:
                  </span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                    {activeCard.resolutionPoints.map((res, rIdx) => (
                      <div key={rIdx} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: '#166534' }}>
                        <span style={{ color: '#16a34a', fontWeight: 900 }}>✓</span>
                        <span>{res}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Footer with Impacted Silos, Solution Toggle and Jump Link */}
              <div
                style={{
                  marginTop: 'auto',
                  paddingTop: 8,
                  borderTop: '1px solid var(--line)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 6,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 10, color: 'var(--text-muted)' }}>
                  <div>
                    <span style={{ fontWeight: 700 }}>Impacted Silos: </span>
                    <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{activeCard.silos.join(' · ')}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowProblemSolution(!showProblemSolution)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#16a34a',
                      fontSize: 10,
                      fontWeight: 700,
                      cursor: 'pointer',
                      padding: 0,
                    }}
                  >
                    {showProblemSolution ? 'Hide Solution ▴' : 'Agent Solution ▾'}
                  </button>
                </div>
                <Link
                  to={activeCard.link}
                  style={{
                    fontSize: 10.5,
                    fontWeight: 800,
                    color: activeCard.color,
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <span>{activeCard.linkLabel}</span>
                  <ChevronRight size={12} />
                </Link>
              </div>
            </div>
          ) : selectedCardId === 'gateway' ? (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 8 }}>
              {/* API Gateway Header */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingBottom: 8,
                  borderBottom: '1px solid var(--line)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div
                    style={{
                      width: 26,
                      height: 26,
                      borderRadius: 6,
                      background: '#eff6ff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#1e40af',
                    }}
                  >
                    <Server size={15} />
                  </div>
                  <div>
                    <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                      2. API Gateway – FastAPI Engine &amp; REST Endpoints
                    </strong>
                    <div style={{ fontSize: 9.5, color: 'var(--text-muted)' }}>
                      High-throughput ASGI router, strict Pydantic v2 validation &amp; SSE streaming
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span
                    style={{
                      fontSize: 9.5,
                      fontWeight: 800,
                      color: '#1e40af',
                      background: '#dbeafe',
                      padding: '2px 8px',
                      borderRadius: 4,
                      border: '1px solid #bfdbfe',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }} />
                    PORT 8000 · ONLINE
                  </span>
                  <a
                    href={SWAGGER_DOCS_URL}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontSize: 10,
                      fontWeight: 800,
                      color: '#ffffff',
                      background: '#1e40af',
                      padding: '3px 8px',
                      borderRadius: 5,
                      textDecoration: 'none',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                    title="Open live interactive Swagger UI in a new tab"
                  >
                    <span>Swagger Docs</span>
                    <ExternalLink size={10} />
                  </a>
                </div>
              </div>

              {/* Gateway Architectural Ribbon */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: 6,
                  background: 'var(--kg-bg-2)',
                  border: '1px solid var(--line)',
                  borderRadius: 6,
                  padding: '6px 8px',
                  fontSize: 10,
                }}
              >
                <div>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 700, display: 'block', fontSize: 8.5 }}>ENGINE</span>
                  <strong style={{ color: '#1e40af' }}>FastAPI 0.111 (Py 3.12)</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 700, display: 'block', fontSize: 8.5 }}>ROUTING</span>
                  <strong style={{ color: 'var(--text-primary)' }}>16 Routers · HTTP/2 REST</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 700, display: 'block', fontSize: 8.5 }}>SECURITY</span>
                  <strong style={{ color: '#6f3dba' }}>JWT Bearer + RBAC</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 700, display: 'block', fontSize: 8.5 }}>DATA &amp; STREAM</span>
                  <strong style={{ color: '#10b981' }}>Neon PG 16 · SSE Stream</strong>
                </div>
              </div>

              {/* Category Filter Pills */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 9.5, fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Filter API Domain:
                </span>
                {['ALL', 'CORE', 'AGENTS', 'SURVEILLANCE', 'SYSTEM'].map((cat) => {
                  const count = cat === 'ALL' ? API_ENDPOINTS.length : API_ENDPOINTS.filter((e) => e.category === cat).length
                  const isActive = apiCategory === cat
                  return (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setApiCategory(cat)}
                      style={{
                        fontSize: 9.5,
                        fontWeight: 800,
                        padding: '2px 8px',
                        borderRadius: 4,
                        border: isActive ? '1px solid #1e40af' : '1px solid var(--line)',
                        background: isActive ? '#eff6ff' : 'var(--kg-bg-2)',
                        color: isActive ? '#1e40af' : 'var(--text-secondary)',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {cat} ({count})
                    </button>
                  )
                })}
              </div>

              {/* Scrollable Endpoints Directory */}
              <div
                style={{
                  maxHeight: 185,
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 5,
                  paddingRight: 2,
                }}
              >
                {API_ENDPOINTS.filter((ep) => (apiCategory === 'ALL' ? true : ep.category === apiCategory)).map((ep) => {
                  const isExpanded = expandedApiId === ep.id
                  const isGet = ep.method === 'GET'
                  const isPost = ep.method === 'POST'
                  const badgeColor = isGet ? '#0284c7' : isPost ? '#6f3dba' : '#8b5cf6'
                  const badgeBg = isGet ? '#e0f2fe' : isPost ? '#f5f3ff' : '#ede9fe'
                  const badgeBorder = isGet ? '#bae6fd' : isPost ? '#d8b4fe' : '#ddd6fe'

                  return (
                    <div
                      key={ep.id}
                      onClick={() => setExpandedApiId(isExpanded ? null : ep.id)}
                      style={{
                        border: '1px solid',
                        borderColor: isExpanded ? '#93c5fd' : 'var(--line)',
                        borderRadius: 6,
                        background: isExpanded ? 'var(--kg-bg-3)' : 'var(--kg-bg-2)',
                        padding: '6px 9px',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                          <span
                            style={{
                              fontSize: 8.5,
                              fontWeight: 900,
                              fontFamily: 'monospace',
                              padding: '1px 5px',
                              borderRadius: 3,
                              color: badgeColor,
                              background: badgeBg,
                              border: `1px solid ${badgeBorder}`,
                            }}
                          >
                            {ep.method}
                          </span>
                          <span
                            style={{
                              fontSize: 10.5,
                              fontFamily: 'monospace',
                              fontWeight: 700,
                              color: 'var(--text-primary)',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {ep.path}
                          </span>
                          <span
                            style={{
                              fontSize: 10,
                              color: 'var(--text-muted)',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            · {ep.name}
                          </span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}>
                          <span
                            style={{
                              fontSize: 8.5,
                              fontWeight: 700,
                              padding: '1px 5px',
                              borderRadius: 3,
                              background: ep.auth === 'Public' ? '#dcfce7' : 'var(--kg-bg-3)',
                              color: ep.auth === 'Public' ? '#15803d' : 'var(--text-secondary)',
                            }}
                          >
                            {ep.auth}
                          </span>
                          <span style={{ fontSize: 8.5, color: '#94a3b8', fontFamily: 'monospace' }}>
                            {ep.latency}
                          </span>
                          <span style={{ fontSize: 9, color: '#1e40af', fontWeight: 800 }}>
                            {isExpanded ? '▲' : '▼'}
                          </span>
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {isExpanded && (
                        <div
                          style={{
                            marginTop: 6,
                            paddingTop: 6,
                            borderTop: '1px solid var(--line)',
                            fontSize: 10,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 5,
                          }}
                        >
                          <div style={{ color: 'var(--text-secondary)', lineHeight: 1.4 }}>{ep.desc}</div>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                            <div style={{ background: 'var(--kg-bg-3)', padding: '5px 7px', borderRadius: 4, border: '1px solid var(--line)' }}>
                              <span style={{ fontSize: 8.5, fontWeight: 800, color: 'var(--text-muted)', display: 'block', marginBottom: 2 }}>
                                REQUEST SPECIFICATION:
                              </span>
                              <code style={{ fontSize: 9.5, color: 'var(--text-primary)' }}>{ep.params}</code>
                            </div>
                            <div style={{ background: '#0f172a', color: '#f8fafc', padding: '5px 7px', borderRadius: 4 }}>
                              <span style={{ fontSize: 8.5, fontWeight: 800, color: '#94a3b8', display: 'block', marginBottom: 2 }}>
                                RESPONSE JSON SCHEMA:
                              </span>
                              <pre style={{ margin: 0, fontSize: 8.5, fontFamily: 'monospace', overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                                {ep.responseSample}
                              </pre>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Direct Workspace Link */}
              <div
                style={{
                  marginTop: 'auto',
                  paddingTop: 8,
                  borderTop: '1px solid var(--line)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>
                  Interactive Component Telemetry: <strong style={{ color: '#10b981' }}>FastAPI 0.111 · Port 8000 Active</strong>
                </span>
                <a
                  href={SWAGGER_DOCS_URL}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: '#1e40af',
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <span>Launch Live Swagger Interactive Docs</span>
                  <ExternalLink size={12} />
                </a>
              </div>
            </div>
          ) : (
            <>
              {/* Header for Other Cards */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: 10,
                  paddingBottom: 8,
                  borderBottom: '1px solid var(--line)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div
                    style={{
                      width: 26,
                      height: 26,
                      borderRadius: 6,
                      background: activeCard.bg,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: activeCard.color,
                      overflow: 'hidden',
                      flexShrink: 0,
                    }}
                  >
                    {activeCard.image ? (
                      <img
                        src={activeCard.image}
                        alt={activeCard.title}
                        style={{ width: 20, height: 20, objectFit: 'contain' }}
                      />
                    ) : (
                      <activeCard.icon size={14} />
                    )}
                  </div>
                  <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                    {activeCard.title}
                  </strong>
                </div>

                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 800,
                    color: activeCard.color,
                    background: activeCard.bg,
                    padding: '2px 8px',
                    borderRadius: 4,
                    border: `1px solid ${activeCard.color}40`,
                  }}
                >
                  {activeCard.badge}
                </span>
              </div>

              {/* Role & Overview */}
              <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.45, marginBottom: 10 }}>
                {activeCard.role}
              </div>

              {/* Protocols & Tables Strip */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: 8,
                  background: 'var(--kg-bg-2)',
                  border: '1px solid var(--line)',
                  borderRadius: 6,
                  padding: '6px 10px',
                  fontSize: 10.5,
                  marginBottom: 10,
                }}
              >
                <div>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 700 }}>PROTOCOLS: </span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{activeCard.protocols}</span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 700 }}>DATABASE TABLES: </span>
                  <span style={{ color: '#6f3dba', fontFamily: 'monospace', fontWeight: 600 }}>
                    {activeCard.tables.join(', ')}
                  </span>
                </div>
              </div>

              {/* Step-by-Step Execution */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
                  Execution Logic &amp; Operational Flow:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {activeCard.executionSteps.map((step, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 6,
                        fontSize: 11,
                        color: 'var(--text-secondary)',
                        lineHeight: 1.35,
                      }}
                    >
                      <span
                        style={{
                          width: 15,
                          height: 15,
                          borderRadius: '50%',
                          background: activeCard.bg,
                          color: activeCard.color,
                          fontSize: 9,
                          fontWeight: 800,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                          marginTop: 1,
                        }}
                      >
                        {idx + 1}
                      </span>
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Direct Workspace Link */}
              <div
                style={{
                  marginTop: 'auto',
                  paddingTop: 8,
                  borderTop: '1px solid var(--line)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span style={{ fontSize: 10.5, color: 'var(--text-muted)' }}>
                  Interactive Component Telemetry: <strong style={{ color: '#10b981' }}>Active &amp; Online</strong>
                </span>
                <Link
                  to={activeCard.link}
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: activeCard.color,
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <span>{activeCard.linkLabel}</span>
                  <ExternalLink size={12} />
                </Link>
              </div>
            </>
          )}
        </div>

        {/* =======================================================================
            QUADRANT 4: BOTTOM-RIGHT — CUSTOMER DELIVERY DATE & PROGRESS HEATMAP
            ======================================================================= */}
        <div
          className="card"
          style={{
            background: 'var(--surface-hi)',
            border: '1px solid var(--line)',
            borderRadius: 10,
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 10,
              paddingBottom: 8,
              borderBottom: '1px solid var(--line)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: 6,
                  background: '#fee2e2',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#dc2626',
                }}
              >
                <Flame size={14} />
              </div>
              <div>
                <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                  Customer Delivery Date &amp; Progress Heatmap
                </strong>
              </div>
            </div>
          </div>

          {/* HEATMAP MATRIX */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, justifyContent: 'center' }}>
            {/* Column Headers (Committed Delivery Dates) */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '120px repeat(5, 1fr)',
                gap: 5,
                paddingBottom: 2,
              }}
            >
              <div style={{ fontSize: 9, fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', paddingLeft: 4 }}>
                Account
              </div>
              {[
                { title: 'Nov 17', sub: 'Overdue', color: '#dc2626', bg: '#fee2e2' },
                { title: 'Nov 24', sub: 'Next SLA', color: '#4338ca', bg: '#e0e7ff' },
                { title: 'Nov 27', sub: 'W-48', color: '#0369a1', bg: '#e0f2fe' },
                { title: 'Dec 05', sub: 'W-49', color: '#15803d', bg: '#dcfce7' },
                { title: 'Dec 15+', sub: 'Q4 Close', color: '#7c3aed', bg: '#ede9fe' },
              ].map((col, idx) => (
                <div
                  key={idx}
                  style={{
                    textAlign: 'center',
                    background: col.bg,
                    border: `1px solid ${col.color}25`,
                    padding: '2px 3px',
                    borderRadius: 4,
                  }}
                >
                  <div style={{ fontSize: 9.5, fontWeight: 900, color: col.color, lineHeight: 1.15 }}>
                    {col.title}
                  </div>
                  <div style={{ fontSize: 7.5, color: col.color, opacity: 0.85, fontWeight: 700 }}>
                    {col.sub}
                  </div>
                </div>
              ))}
            </div>

            {/* Heatmap Rows (The 4 Enterprise Accounts) */}
            {[
              {
                customerId: 'CUS-001',
                customer: 'Retailer North',
                color: '#6f3dba',
                totalOrders: 506,
                cells: [
                  { orders: 0, progress: 0, date: 'Nov 17' },
                  { orders: 120, progress: 60, date: 'Nov 24', isNext: true },
                  { orders: 105, progress: 60, date: 'Nov 27' },
                  { orders: 140, progress: 85, date: 'Dec 05' },
                  { orders: 141, progress: 35, date: 'Dec 15+' },
                ],
              },
              {
                customerId: 'CUS-002',
                customer: 'MobileMart',
                color: '#0284c7',
                totalOrders: 408,
                cells: [
                  { orders: 65, progress: 20, date: 'Nov 17', isOverdue: true },
                  { orders: 95, progress: 65, date: 'Nov 24', isNext: true },
                  { orders: 80, progress: 70, date: 'Nov 27' },
                  { orders: 88, progress: 90, date: 'Dec 05' },
                  { orders: 80, progress: 40, date: 'Dec 15+' },
                ],
              },
              {
                customerId: 'CUS-004',
                customer: 'Global Devices',
                color: '#059669',
                totalOrders: 358,
                cells: [
                  { orders: 0, progress: 0, date: 'Nov 17' },
                  { orders: 90, progress: 62, date: 'Nov 24', isNext: true },
                  { orders: 78, progress: 65, date: 'Nov 27' },
                  { orders: 110, progress: 88, date: 'Dec 05' },
                  { orders: 80, progress: 35, date: 'Dec 15+' },
                ],
              },
              {
                customerId: 'CUS-003',
                customer: 'Digital Bazaar',
                color: '#d97706',
                totalOrders: 350,
                cells: [
                  { orders: 42, progress: 15, date: 'Nov 17', isOverdue: true },
                  { orders: 85, progress: 58, date: 'Nov 24', isNext: true },
                  { orders: 75, progress: 60, date: 'Nov 27' },
                  { orders: 78, progress: 85, date: 'Dec 05' },
                  { orders: 70, progress: 40, date: 'Dec 15+' },
                ],
              },
            ].map((row) => (
              <div
                key={row.customer}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '120px repeat(5, 1fr)',
                  gap: 5,
                  alignItems: 'stretch',
                }}
              >
                {/* Account Label (Clickable -> Customer Details Page) */}
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate(`/customers/${row.customerId}`)}
                  onKeyDown={(e) => e.key === 'Enter' && navigate(`/customers/${row.customerId}`)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '3px 6px',
                    background: 'var(--kg-bg-2)',
                    borderRadius: 5,
                    border: '1px solid var(--line)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = row.color
                    e.currentTarget.style.background = 'var(--kg-bg-3)'
                    e.currentTarget.style.transform = 'translateX(2px)'
                    e.currentTarget.style.boxShadow = `0 2px 8px ${row.color}25`
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--line)'
                    e.currentTarget.style.background = 'var(--kg-bg-2)'
                    e.currentTarget.style.transform = 'none'
                    e.currentTarget.style.boxShadow = 'none'
                  }}
                  title={`Click to open full Customer Details & Orders for ${row.customer} (${row.totalOrders} database orders)`}
                >
                  <div
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: '50%',
                      background: row.color,
                      flexShrink: 0,
                      boxShadow: `0 0 0 2px ${row.color}30`,
                    }}
                  />
                  <div style={{ lineHeight: 1.15, overflow: 'hidden', flex: 1 }}>
                    <div style={{ fontSize: 9.5, fontWeight: 800, color: 'var(--text-primary)', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                      {row.customer}
                    </div>
                    <div style={{ fontSize: 8, color: 'var(--text-muted)' }}>
                      {row.totalOrders} total ord
                    </div>
                  </div>
                  <ArrowUpRight size={11} style={{ color: row.color, opacity: 0.8, flexShrink: 0 }} />
                </div>

                {/* 5 Delivery Cells */}
                {row.cells.map((cell, cIdx) => {
                  if (cell.orders === 0) {
                    return (
                      <div
                        key={cIdx}
                        style={{
                          background: 'var(--kg-bg-2)',
                          border: '1px dashed var(--line)',
                          borderRadius: 5,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'var(--text-muted)',
                          fontSize: 10,
                          minHeight: 38,
                        }}
                      >
                        —
                      </div>
                    )
                  }

                  // Determine cell color by progress & risk
                  let bg = '#dcfce7'
                  let border = '#86efac'
                  let text = '#15803d'

                  if (cell.isOverdue) {
                    bg = '#fee2e2'
                    border = '#fca5a5'
                    text = '#b91c1c'
                  } else if (cell.progress < 50) {
                    bg = '#fef3c7'
                    border = '#fde68a'
                    text = '#b45309'
                  } else if (cell.progress < 80) {
                    bg = '#e0f2fe'
                    border = '#7dd3fc'
                    text = '#0369a1'
                  }

                  const isSelected = selectedCustomerFilter === `${row.customer}-${cell.date}`

                  return (
                    <div
                      key={cIdx}
                      onClick={() =>
                        setSelectedCustomerFilter(
                          selectedCustomerFilter === `${row.customer}-${cell.date}`
                            ? 'ALL'
                            : `${row.customer}-${cell.date}`
                        )
                      }
                      onDoubleClick={() => navigate(`/customers/${row.customerId}`)}
                      style={{
                        background: bg,
                        border: `1px solid ${border}`,
                        borderRadius: 5,
                        padding: '3px 4px',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                        boxShadow: isSelected ? `0 0 0 2px ${text}, 0 2px 8px rgba(0,0,0,0.12)` : 'none',
                        transform: isSelected ? 'scale(1.04)' : 'none',
                        minHeight: 38,
                      }}
                      title={`${row.customer} · Delivery: ${cell.date} | ${cell.orders} orders (${cell.progress}% average progress) · Double-click to view all customer orders`}
                    >
                      <div style={{ fontSize: 11.5, fontWeight: 900, color: text, lineHeight: 1 }}>
                        {cell.progress}%
                      </div>
                      <div style={{ fontSize: 7.5, fontWeight: 700, color: text, opacity: 0.9, marginTop: 2 }}>
                        {cell.orders} ord
                      </div>
                    </div>
                  )
                })}
              </div>
            ))}
          </div>

          {/* Interactive Inspection Strip / Selection Detail */}
          <div
            style={{
              marginTop: 8,
              padding: '6px 10px',
              borderRadius: 6,
              background: 'var(--kg-bg-2)',
              border: '1px solid var(--line)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 10,
            }}
          >
            {selectedCustomerFilter !== 'ALL' && selectedCustomerFilter.includes('-') ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4338ca' }} />
                  <span>
                    Inspecting cluster: <strong style={{ color: 'var(--text-primary)' }}>{selectedCustomerFilter.replace('-', ' · Delivery ')}</strong>
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelectedCustomerFilter('ALL')}
                    style={{
                      fontSize: 8.5,
                      color: '#6f3dba',
                      fontWeight: 700,
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      textDecoration: 'underline',
                      marginLeft: 4,
                    }}
                  >
                    Reset
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    const custName = selectedCustomerFilter.split('-')[0]
                    const map = {
                      'Retailer North': 'CUS-001',
                      'MobileMart': 'CUS-002',
                      'Global Devices': 'CUS-004',
                      'Digital Bazaar': 'CUS-003',
                    }
                    const targetId = map[custName] || 'CUS-001'
                    navigate(`/customers/${targetId}`)
                  }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    background: '#4338ca',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: 4,
                    padding: '3px 8px',
                    fontSize: 8.5,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Open Customer Dossier &amp; Orders <ArrowUpRight size={10} />
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)' }}>
                <Calendar size={11} style={{ color: '#4338ca' }} />
                <span>
                  Next Imminent Delivery Target: <strong style={{ color: 'var(--text-primary)' }}>Nov 24, 2026</strong> across 3 accounts
                </span>
              </div>
            )}
            {selectedCustomerFilter === 'ALL' && (
              <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>
                Click account name to open full details · Click cell to highlight
              </span>
            )}
          </div>

          {/* Color Scale Legend */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginTop: 6,
              paddingTop: 6,
              borderTop: '1px solid var(--line)',
              fontSize: 8.5,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>PROGRESS:</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: '#b91c1c' }}>
                <span style={{ width: 7, height: 7, borderRadius: 2, background: '#fee2e2', border: '1px solid #fca5a5' }} />
                &lt;30% Overdue
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: '#b45309' }}>
                <span style={{ width: 7, height: 7, borderRadius: 2, background: '#fef3c7', border: '1px solid #fde68a' }} />
                30-49% Pending
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: '#0369a1' }}>
                <span style={{ width: 7, height: 7, borderRadius: 2, background: '#e0f2fe', border: '1px solid #7dd3fc' }} />
                50-79% In Prod
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, color: '#15803d' }}>
                <span style={{ width: 7, height: 7, borderRadius: 2, background: '#dcfce7', border: '1px solid #86efac' }} />
                80-100% Done
              </span>
            </div>

            <span style={{ color: '#10b981', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <CheckCircle2 size={10} />
              1,619 Orders Grounded
            </span>
          </div>

          {/* Footer Telemetry */}
          <div
            style={{
              marginTop: 6,
              paddingTop: 6,
              borderTop: '1px solid var(--line)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ fontSize: 9.5, color: 'var(--text-muted)' }}>
              Portfolio Fulfillment Velocity: <strong style={{ color: '#4338ca' }}>58.3% Weighted Avg</strong>
            </span>
            <span style={{ fontSize: 9.5, color: 'var(--text-muted)' }}>
              Database: <strong style={{ color: 'var(--text-primary)' }}>Neon PostgreSQL 16</strong>
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
