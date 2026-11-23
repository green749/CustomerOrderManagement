import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Workflow,
  Database,
  Layers,
  Bot,
  ShieldCheck,
  Zap,
  ArrowRight,
  ArrowDown,
  Building2,
  Factory,
  ShieldAlert,
  Warehouse,
  Truck,
  Cpu,
  CheckCircle2,
  Clock,
  ExternalLink,
  ChevronRight,
  FileCode,
  Server,
  Sparkles,
  Play,
  RotateCcw,
  CheckSquare,
  Activity,
  Send,
  Mail,
  Table,
  Filter,
  FileSpreadsheet,
  AlertTriangle,
  Lock,
  GitBranch,
  Terminal,
  HelpCircle,
  Eye,
  Info,
} from 'lucide-react'

// Architecture Stages Definition
const STAGES = [
  {
    id: 'sources',
    stepNumber: '01',
    name: 'Data Sources & Ingestion',
    category: 'Enterprise Silos',
    icon: Database,
    accentColor: '#3b82f6',
    softBg: 'rgba(59, 130, 246, 0.08)',
    borderHover: 'rgba(59, 130, 246, 0.4)',
    summary: 'Continuous ingestion across 7 enterprise operational systems via REST, CDC, and automated intake pollers.',
    badges: ['ERP · SAP', 'MMS', 'MES', 'QMS', 'WMS', 'TMS', 'PLM'],
    arrowLabel: 'Ingest & Standardize',
  },
  {
    id: 'storage',
    stepNumber: '02',
    name: 'Unified Analytical Store',
    category: 'Relational Warehouse',
    icon: Layers,
    accentColor: '#0ea5e9',
    softBg: 'rgba(14, 165, 233, 0.08)',
    borderHover: 'rgba(14, 165, 233, 0.4)',
    summary: 'PostgreSQL 16 Star Schema with indexed dimensions, transaction facts, and sub-millisecond query caches.',
    badges: ['PostgreSQL 16', 'Neon DB Pool', 'Star Schema', '120s Cache'],
    arrowLabel: 'Query & Trigger',
  },
  {
    id: 'agents',
    stepNumber: '03',
    name: 'Autonomous AI Agents',
    category: 'Cognitive Intelligence',
    icon: Bot,
    accentColor: '#8b5cf6',
    softBg: 'rgba(139, 92, 246, 0.08)',
    borderHover: 'rgba(139, 92, 246, 0.4)',
    summary: '3 specialized agents running ReAct reasoning loops, multi-dept critical path synthesis, and 24/7 risk surveillance.',
    badges: ['Agent 1 Assistant', 'Agent 2 Feasibility', 'Agent 3 Surveillance'],
    arrowLabel: 'Evaluate & Propose',
  },
  {
    id: 'governance',
    stepNumber: '04',
    name: 'Policy & Safety Gate',
    category: 'Governance & SoD',
    icon: ShieldCheck,
    accentColor: '#f59e0b',
    softBg: 'rgba(245, 158, 11, 0.08)',
    borderHover: 'rgba(245, 158, 11, 0.4)',
    summary: 'Segregation of duties, mandatory human commercial approval for all orders, LLM rate limits, and human-in-the-loop escalation queues.',
    badges: ['Mandatory Human Approval', 'SoD Isolation', '100% Human Sign-Off', 'NEEDS_HUMAN'],
    arrowLabel: 'Validate & Authorize',
  },
  {
    id: 'execution',
    stepNumber: '05',
    name: 'Closed-Loop Execution',
    category: 'Actions & Dispatch',
    icon: Zap,
    accentColor: '#10b981',
    softBg: 'rgba(16, 185, 129, 0.08)',
    borderHover: 'rgba(16, 185, 129, 0.4)',
    summary: 'Automated email dispatch via Ethereal SMTP, corrective action execution, and on-time outcome KPI tracking.',
    badges: ['Ethereal SMTP', 'Dual-Channel Alert', 'Action Executors', 'Outcome KPIs'],
    arrowLabel: 'Commitment Met',
  },
]

// Detailed Content for Each Stage
const STAGE_DETAILS = {
  sources: {
    title: 'Stage 1: Multi-Source Enterprise Ingestion',
    tagline: '7 Department Operational Data Ingestion & Intake Watcher',
    overview:
      'Manufacturing 360 acts as a central neural network bridging fragmented enterprise operational silos. Data is ingested from ERP, MMS, MES, QMS, WMS, TMS, and PLM via dedicated connector adapters, webhook relays, and background intake watchers without impacting legacy production databases.',
    liveLink: { to: '/connectors', label: 'Inspect Live Connectors' },
    steps: [
      {
        step: '1. Connector Adapters Sync',
        desc: 'Connector modules interface with external protocols (SAP OData v4, RFC Gateway, Siemens OPC UA, Manhattan WMS REST, and Veeva QMS API). A 120s cached poll heartbeat validates sync status and operational latency.',
        tech: 'backend/app/routes/connectors.py · ConnectorService',
      },
      {
        step: '2. Automated Order Intake Watcher',
        desc: 'Background intake daemon (services/intake_service.py) periodically scans for incoming customer purchase orders created via EDI, customer portals, or sales feeds with status NEW/OPEN lacking feasibility assessments.',
        tech: 'backend/app/services/intake_service.py · IntakeWatcher',
      },
      {
        step: '3. Data Validation & Canonical Normalization',
        desc: 'Raw heterogeneous payloads are parsed and validated against strict Pydantic schemas (OrderAssessmentCreate, CustomerOrderCreate), ensuring product SKU formatting, currency precision, and requested dates conform to standard formats.',
        tech: 'backend/app/schemas/order_assessment.py',
      },
    ],
    components: [
      { name: 'ERP (SAP S/4HANA)', role: 'Commercial validation, customer accounts (CUS-001..004), payment terms, credit limits, pricing contracts.', icon: Building2 },
      { name: 'MMS (Material Planning)', role: 'Bill of Materials (BOM) explosion, raw component stock, supplier lead times, critical shortage flags.', icon: Layers },
      { name: 'MES (Plant Production)', role: 'Work orders (FactProductionOrder), machine work centers, shop floor bottlenecks, line cycle throughput (713 units/day).', icon: Factory },
      { name: 'QMS (Quality Release)', role: 'Quality inspections (FactQualityInspection), lot quarantine holds, scrap rates, disposition history (RELEASE/HOLD/SCRAP).', icon: ShieldAlert },
      { name: 'WMS (Warehouse & Staging)', role: 'Finished goods inventory (FactInventoryLevel), warehouse dispatch bays, pick/pack packaging readiness.', icon: Warehouse },
      { name: 'TMS (Logistics & Transit)', role: 'Shipment tracking (FactShipmentMilestone), carrier transit times, dispatch dates, carrier performance SLAs.', icon: Truck },
      { name: 'PLM (Product Lifecycle)', role: 'Engineering change orders, BOM revisions, product specifications (Aster 15 128GB, 256GB, Pro 256GB), colorways.', icon: Cpu },
    ],
    inputs: ['EDI 850 Purchase Orders', 'SAP Sales Order OData', 'Shopfloor PLC signals', 'Veeva QA hold alerts', 'Carrier tracking webhooks'],
    outputs: ['Validated transactional event records ready for Star Schema persistence', 'Automatic Agent 2 Feasibility assessment triggers'],
    tables: ['dim_customer', 'dim_product', 'fact_customer_order (raw status NEW)'],
  },
  storage: {
    title: 'Stage 2: Unified Analytical Data Store',
    tagline: 'PostgreSQL 16 Star Schema & Analytical Query Optimization',
    overview:
      'All enterprise manufacturing transactions are consolidated into an optimized PostgreSQL 16 relational warehouse hosted on high-concurrency Neon DB connection pools. The Star Schema decouples operational writes from complex analytical agent queries, providing sub-millisecond data retrieval.',
    liveLink: { to: '/orders', label: 'Explore Canonical Orders Book' },
    steps: [
      {
        step: '1. Star Schema Relational Modeling',
        desc: 'Organized into core dimension tables (dim_customer, dim_product, dim_facility, users) and high-volume transactional fact tables (fact_customer_order, fact_production_order, fact_inventory_level, fact_quality_inspection, fact_shipment_milestone).',
        tech: 'backend/app/models/*.py · SQLAlchemy ORM',
      },
      {
        step: '2. Low-Latency Indexed Query Optimization',
        desc: 'B-tree composite indexing on customer_order_id, product_id, department, and disposition enables AI agents to query 16,000+ QA records and 6,600+ inventory bins in under 4 milliseconds.',
        tech: 'Alembic Schema Migrations · PostgreSQL 16 Indexing',
      },
      {
        step: '3. In-Memory Factory Context Cache',
        desc: 'A thread-safe 120-second TTL cache (_BENCHMARK_CACHE) caches factory queue volume, competing active orders, and product QA hold distributions, eliminating repetitive database roundtrips during intense feasibility spikes.',
        tech: 'FeasibilityService._BENCHMARK_CACHE (120s TTL)',
      },
    ],
    components: [
      { name: 'dim_customer', role: 'Customer accounts, tier, credit limit, preferred carrier (DHL/FedEx/BlueDart), SLA service level, manual review flag.', icon: Building2 },
      { name: 'dim_product', role: 'Catalog models (SPH-A15-128, SPH-A15-256, SPH-PRO-256), standard BOM lead time, list prices, retail master packaging.', icon: Cpu },
      { name: 'fact_customer_order', role: '1,500+ commercial commitments, requested vs confirmed dates, order status (NEW, HUMAN_APPROVAL, OPEN, IN_PROGRESS, DELIVERED).', icon: FileSpreadsheet },
      { name: 'fact_production_order', role: 'Shopfloor work orders, assigned production lines, machine cycle times, target completion timestamps.', icon: Factory },
      { name: 'fact_inventory_level', role: 'Real-time bin warehouse stock, raw material components, safety stock buffers, shortage replenishment days.', icon: Warehouse },
      { name: 'fact_quality_inspection', role: '16,000+ inspection test records, sample sizes, defect logs, disposition classifications.', icon: ShieldAlert },
      { name: 'fact_shipment_milestone', role: 'In-transit tracking, carrier lane checkpoints, dispatch dates, actual delivery timestamps.', icon: Truck },
    ],
    inputs: ['Normalized data events from Stage 1 ingestion connectors', 'Feasibility assessments & proposal records'],
    outputs: ['Instantaneous SQL query results for Agent 1 ReAct tools, Agent 2 checks, and Agent 3 surveillance audits'],
    tables: ['dim_customer', 'dim_product', 'fact_customer_order', 'fact_production_order', 'fact_inventory_level', 'fact_quality_inspection', 'fact_shipment_milestone', 'audit_log'],
  },
  agents: {
    title: 'Stage 3: Autonomous AI Agent Intelligence Core',
    tagline: '3 Specialized Cognitive Engines (Agent 1, Agent 2, Agent 3)',
    overview:
      'The core intelligence layer consists of three autonomous AI agents powered by the Domo Text LLM and deterministic rule engines. Each agent has a distinct operational scope, custom system prompts, scoped toolsets, and safety schemas.',
    liveLink: { to: '/assessments', label: 'Launch Agent 2 Assessment' },
    subAgents: [
      {
        id: 'agent1',
        name: 'Agent 1: Conversational Order Management Assistant',
        badge: 'ReAct Chatbot',
        role: 'Natural language order investigation, ATP inventory queries, delivery delay triage, and customer fulfillment synthesis.',
        mechanism: 'Parameterized ReAct cognitive loop (run_agent_loop). Domo Text LLM executes Thought -> Action -> Observation cycles using 6 scoped domain tools. Scratchpad reasoning is strictly filtered before rendering final markdown answers.',
        file: 'backend/app/agent/agent_loop.py · backend/app/routes/agent.py',
        tools: ['get_order_details', 'get_customer_history', 'check_inventory_levels', 'list_at_risk_orders', 'get_production_progress', 'get_shipment_status'],
        fallback: 'Deterministic rule-based SQL response engine when Domo LLM is offline or unconfigured.',
        inputLayer: {
          title: 'Input Layer · Enterprise Data Pipeline',
          requiredData: 'Customer commercial terms, order status, shopfloor work order execution, warehouse stock bins, and carrier tracking milestones.',
          sourceApps: [
            { name: 'CRM / ERP Master', role: 'Customer master accounts (CUS-001..004), credit limits, contacts, pricing tiers' },
            { name: 'ERP Sales Orders', role: '1,500+ commercial order records (fact_customer_order), requested & confirmed dates' },
            { name: 'MES Shop Floor', role: 'Work orders (fact_production_order), produced vs target units, active assembly lines' },
            { name: 'WMS / MMS Warehouse', role: 'Real-time bin inventory (fact_inventory_daily_snapshot), allocated & safety stocks' },
            { name: 'TMS Carrier Logistics', role: 'Carrier tracking milestones (fact_shipment_milestone), scan locations, transit delays' },
          ],
          tablesAndColumns: [
            { table: 'dim_customer', cols: 'customer_id, customer_name, tier, credit_limit_inr, contact_email, preferred_carrier, sla_service_level' },
            { table: 'dim_product', cols: 'product_id, model_name, storage_gb, ram_gb, color_variant, base_price_inr' },
            { table: 'fact_customer_order', cols: 'order_id, customer_order_id, customer_id, product_id, order_qty, order_date, requested_delivery_date, confirmed_delivery_date, status, delivery_risk_level, total_amount_inr, shipment_status' },
            { table: 'fact_production_order', cols: 'production_order_id, customer_order_id, plant_id, line_id, status, target_qty, produced_qty, actual_start_date, actual_completion_date' },
            { table: 'fact_inventory_daily_snapshot', cols: 'snapshot_date, product_id, material_id, plant_id, on_hand_qty, allocated_qty, available_qty, safety_stock_qty' },
            { table: 'fact_shipment_milestone', cols: 'shipment_id, customer_order_id, carrier_name, tracking_number, status, current_location, estimated_delivery_at, actual_delivery_at, delay_hours' },
            { table: 'conversations & chat_messages', cols: 'conversation_id, title, user_id, role, content, tokens_used, tool_calls, created_at' },
          ],
          apis: [
            'POST /api/conversations (Thread creation & session management)',
            'POST /api/conversations/{id}/messages (ReAct conversational loop & tool execution)',
            'GET /api/agent/orders/{id} (Single order context fetch)',
            'GET /api/agent/inventory (Real-time warehouse stock query)',
          ],
        },
        processingLayer: {
          title: 'Processing Layer · Business Intelligence & Rules',
          transformations: 'Intent classification (ORDER_STATUS, INVENTORY_LOOKUP, AT_RISK_ORDERS, PRODUCTION_PROGRESS, SHIPPING_TRACKING, CUSTOMER_HISTORY), heterogeneous PO string normalization (e.g. CO-000003, #3, 3), and markdown response synthesis.',
          calculations: [
            { name: 'Schedule Delay Variance', formula: 'Days Overdue = Current Date - Confirmed Delivery Date' },
            { name: 'Production Progress Rate', formula: 'Progress % = (Produced Qty / Target Qty) * 100' },
            { name: 'Available-to-Promise (ATP)', formula: 'ATP = On-Hand Stock - Allocated Qty - Safety Stock' },
            { name: 'Customer Fulfillment Reliability', formula: 'OTIF % = (On-Time Delivered Orders / Total Orders) * 100' },
          ],
          businessRules: [
            'Commercial margin & cost scrubbing: Internal assembly costs and unit profit margins are masked from chat responses.',
            'RBAC Security Check: Operator permissions restrict viewing customer credit limit overrides or global contract terms.',
            'Rate Limiting & Cost Caps: Enforces max 100 LLM calls/hr token budget with automatic fallback to deterministic SQL queries.',
            'Context Token Budgeting: Limits conversational history context to the last 10 turns to avoid LLM context saturation.',
          ],
          dataModels: 'SQLAlchemy ORM (FactCustomerOrder, FactProductionOrder, FactInventoryDailySnapshot, Conversation, ChatMessage) & Pydantic Schemas (ChatMessageCreate, ChatMessageResponse, AgentContextResponse).',
        },
        presentationLayer: {
          title: 'Presentation Layer · Dashboards & Operational Surfaces',
          dashboards: 'Slide-over Global Assistant Drawer accessible from anywhere in the application (/assistant), order detail inspection tabs, and customer history drawers.',
          kpis: ['Conversation tokens consumed', 'LLM turn latency (ms)', 'Context tools invoked count', 'Inline order progress % and days variance'],
          reports: 'Conversational order audit transcripts, structured tool execution logs, and customer order history summaries.',
          alerts: 'Inline delay warning badges, critical risk callouts with deep-links to /monitoring and /orders.',
          userInterfaces: 'Interactive markdown chat with streaming-feel badges, clickable Order Snapshot Cards, deep-links to /assessments and /monitoring, and suggested follow-up prompt chips.',
        },
        aiLayer: {
          title: 'AI Intelligence Layer · Cognitive Core & Automation',
          analyses: 'Natural language queries, operational dependencies across order fulfillment silos, and correlation between manufacturing progress and transit checkpoints.',
          predicts: 'Estimated delivery feasibility based on real-time carrier velocity and work order completion trajectory.',
          detects: 'Hidden operational bottlenecks, order discrepancies, duplicate purchase order attempts, and delivery schedule slips.',
          recommends: 'Proactive troubleshooting steps (e.g. "Order CO-000003 is overdue by 33 days; would you like me to trigger Agent 3 risk triage or open the escalation queue?").',
          automates: 'Multi-table SQL queries, tool orchestration via ReAct loops (run_agent_loop), and structured JSON synthesis without manual navigation.',
        },
      },
      {
        id: 'agent2',
        name: 'Agent 2: Feasibility & Commitment Engine',
        badge: '7-Dept Pre-Confirmation',
        role: 'Evaluates new customer order intake across 7 manufacturing conduits (ERP, MMS, MES, WMS, QMS, TMS, PLM), calculates achievable commitment dates using CTP/ATP, and creates commitment proposals.',
        mechanism: 'Multi-department conduit evaluation. Assesses ERP, MMS, MES, WMS, QMS, TMS, and PLM readiness. In agentic mode, runs ReAct feasibility agent and cross-validates against deterministic critical path. If date variance > 2 days or any dept is BLOCKED, forces fallback to deterministic safety baseline.',
        file: 'backend/app/services/feasibility_service.py · backend/app/agent/feasibility_agent.py',
        tools: ['check_atp', 'check_ctp', 'recommend_promise_date', 'propose_allocation', 'get_competing_orders', '7 department readiness checks'],
        fallback: 'Fast deterministic synthesis (0ms, zero external LLM roundtrips) guarantees instantaneous response.',
        inputLayer: {
          title: 'Input Layer · Enterprise Data Pipeline',
          requiredData: 'Order specs, customer master credit, dynamic BOM explosion, assembly line queues, quality disposition history, carrier transit windows, and engineering revisions.',
          sourceApps: [
            { name: '1. ERP (Commercial SD)', role: 'Customer active status, credit rating, commercial contract pricing, duplicate purchase order check' },
            { name: '2. MMS (Material Planning)', role: 'Bill of Materials (BOM) explosion, on-hand component stock, ATP material shortage calculation' },
            { name: '3. MES (Plant Production)', role: 'Line capacity availability, active work order queues (206 competing orders), daily throughput (713 u/d)' },
            { name: '4. WMS (Warehouse Staging)', role: 'Finished goods storage staging, packaging specification readiness, dispatch bay slots' },
            { name: '5. QMS (Quality Assurance)', role: 'Historical scrap rates, quarantine audit logs, lot release requirements (FactQualityInspection)' },
            { name: '6. TMS (Transportation)', role: 'Shipping lane transit lead times by region (1-4d), freight carrier booking buffer' },
            { name: '7. PLM (Engineering)', role: 'Engineering revision match, engineering freeze audit, hardware BOM configuration compatibility' },
          ],
          tablesAndColumns: [
            { table: 'dim_customer', cols: 'customer_id, customer_name, credit_limit_inr, status, payment_terms, sla_service_level' },
            { table: 'dim_product', cols: 'product_id, model_name, bom_version, base_price_inr, is_active' },
            { table: 'fact_customer_order', cols: 'Historical order book, duplicate PO check on customer_order_id, po_number' },
            { table: 'fact_production_order', cols: 'plant_id, status = IN_PROGRESS, order_qty (280,945 competing queue units across 206 orders)' },
            { table: 'fact_inventory_daily_snapshot', cols: 'material_id, on_hand_qty, allocated_qty, safety_stock_qty, snapshot_date' },
            { table: 'fact_quality_inspection', cols: 'product_id, disposition (RELEASE/HOLD/SCRAP), defect_type, inspection_date' },
            { table: 'order_assessments', cols: 'assessment_id, customer_order_id, customer_id, product_id, order_qty, requested_delivery_date, unit_price_inr, overall_status, estimated_delivery_date, days_variance, confidence_level, blockers_summary, corrective_actions_summary, created_at' },
            { table: 'department_readiness', cols: 'id, assessment_id, department (ERP/MMS/MES/WMS/QMS/TMS/PLM), readiness_status (READY/AT_RISK/BLOCKED/PARTIAL), available_evidence, identified_issue, reason_for_issue, required_action, responsible_role, estimated_delay_days, data_source' },
            { table: 'commitment_proposals', cols: 'proposal_id, assessment_id, proposed_date, status (PENDING/APPROVED/REJECTED), approved_by, approved_at, rejection_reason' },
          ],
          apis: [
            'POST /api/assessments (Execute Agent 2 evaluation across 7 depts & generate proposal)',
            'GET /api/assessments (List recent feasibility assessments with multi-filters)',
            'GET /api/assessments/{id} (Retrieve assessment detail with all 7 department records)',
            'GET /api/assessments/{id}/departments (Raw department readiness breakdown)',
          ],
        },
        processingLayer: {
          title: 'Processing Layer · Business Intelligence & Rules',
          transformations: 'Canonical intake normalization, multi-department BOM explosion (PRODUCT_BOM_MAP), thread-safe in-memory context caching (_BENCHMARK_CACHE with 120s TTL), and critical-path assembly scheduling.',
          calculations: [
            { name: 'Capacity-to-Promise (CTP)', formula: 'Assembly Days = ceil(Order Qty / Daily Throughput 713 u/d) + Setup Buffer (1d)' },
            { name: 'Material Lead Time Constraint', formula: 'Component Ready Date = Order Date + max_{m in BOM}(Shortage Lead Time_m)' },
            { name: 'Critical Path Method (CPM)', formula: 'Achievable Date = Order Date + max(Material Days, Setup Days) + Assembly Days + QA (1-2d) + Transit (1-4d)' },
            { name: 'Delivery Commitment Variance', formula: 'Days Variance = Achievable Delivery Date - Customer Requested Date' },
          ],
          businessRules: [
            'Feasibility Decision Matrix: FEASIBLE if variance <= 0 and 0 blocked depts; AT_RISK if variance <= 3; BLOCKED if variance > 3 or any dept BLOCKED.',
            '100% Mandatory Human Approval: Automated self-approval is permanently disabled; all commitment proposals strictly generate in PENDING state requiring human commercial review.',
            'Strict Segregation of Duties (SoD): Proposals generated by Agent 2 can only be approved by authorized human Customer Service or Plant Leadership.',
            'Deterministic Safety Override: If LLM proposed date deviates > 2 days from the CPM calculation or any dept is BLOCKED, LLM output is discarded in favor of deterministic calculation.',
          ],
          dataModels: 'SQLAlchemy ORM (OrderAssessment, DepartmentReadiness, CommitmentProposal) & Pydantic Schemas (OrderAssessmentCreate, OrderAssessmentResponse, DepartmentReadinessResponse).',
        },
        presentationLayer: {
          title: 'Presentation Layer · Dashboards & Operational Surfaces',
          dashboards: 'Agent 2 Interactive Feasibility Workspace (/assessments?id=...), Comprehensive Assessments Table, and Customer Order Intake Modal.',
          kpis: ['Overall Feasibility (FEASIBLE / AT RISK / BLOCKED)', '7-Department Tally (X Ready · Y At Risk/Partial · Z Blocked)', 'Confidence Level (HIGH / MEDIUM / LOW)', 'Days Variance (+X days / On Schedule)'],
          reports: 'Seven-Department Technical Audit logs, Critical Path Breakdown report, and Formal Commercial Commitment Proposals.',
          alerts: 'Visual pulsing scan indicators (.scanning-pulse), laser traveling connectors, blocked department error banners, and proposal status chips.',
          userInterfaces: 'Connected 7-card conduit pipeline (ERP -> MMS -> MES -> WMS -> QMS -> TMS -> PLM), expanding technical audit cards, timeline comparison charts, and Customer Service approval buttons.',
        },
        aiLayer: {
          title: 'AI Intelligence Layer · Cognitive Core & Automation',
          analyses: 'Multi-department operational constraints, cross-conduit dependency bottlenecks (e.g. MMS component shortage causing MES idle line delays), and competing plant queue capacity.',
          predicts: 'Realistic factory delivery completion date, component arrival dates, and probability of production schedule slips.',
          detects: 'Capacity shortages, raw material lead time bottlenecks, active quality quarantine flags, and freight carrier transit window violations.',
          recommends: 'Compensatory mitigation actions: plant work order slot reallocation, component supplier expedites, alternate factory line assignment, or carrier air upgrades.',
          automates: 'Autonomous 7-department telemetry audit executed in under 1 second without human data gathering.',
        },
      },
      {
        id: 'agent3',
        name: 'Agent 3: 24/7 Autonomous Surveillance & Risk Monitor',
        badge: 'Continuous 24/7 Risk Radar',
        role: 'Continuously monitors all active confirmed customer orders across 7 conduits, detects emerging operational variances and delivery risks, computes readiness scores, and proposes actionable corrective actions.',
        mechanism: 'Dual-trigger architecture: 1) Automated background scheduler running every 1,800 seconds (or 24h cycle) with distributed DB lease locking. 2) Real-time event-driven checks (run_event_check) triggered on work order or shipment milestone updates.',
        file: 'backend/app/services/monitoring_service.py · backend/app/agent/monitoring_agent.py',
        tools: ['detect_risks', 'get_related_orders_by_material', 'get_alert_history', 'get_shipment_status', 'get_production_progress'],
        fallback: 'Deduplicated risk alerting using SHA-256 fingerprints prevents redundant alert fatigue.',
        inputLayer: {
          title: 'Input Layer · Enterprise Data Pipeline',
          requiredData: 'Confirmed delivery commitments, live plant work order completions, inventory drawdowns, lot quality inspection results, and carrier tracking GPS milestones.',
          sourceApps: [
            { name: '1. ERP Conduit', role: 'Commercial order confirmation dates, customer priority revisions, payment terms holds' },
            { name: '2. MMS Conduit', role: 'Component inventory draw-downs, raw material supplier replenishment slips, safety stock thresholds' },
            { name: '3. MES Conduit', role: 'Shop floor work orders, line downtime alarms, actual produced qty vs scheduled target' },
            { name: '4. WMS Conduit', role: 'Pick/pack staging verification timestamps, warehouse dispatch bay congestion' },
            { name: '5. QMS Conduit', role: 'Batch quality inspection test failures, quarantine lot holds, defect spike classifications' },
            { name: '6. TMS Conduit', role: 'Carrier transit milestone events, GPS vehicle tracking checkpoints, weather delay flags' },
            { name: '7. PLM Conduit', role: 'Late engineering change orders (ECO), revision freeze updates' },
          ],
          tablesAndColumns: [
            { table: 'fact_customer_order', cols: 'order_id, customer_order_id, customer_id, product_id, order_qty, confirmed_delivery_date, status, delivery_risk_level' },
            { table: 'fact_production_order', cols: 'production_order_id, customer_order_id, plant_id, status, target_qty, produced_qty, actual_start_date' },
            { table: 'fact_inventory_daily_snapshot', cols: 'material_id, on_hand_qty, allocated_qty, safety_stock_qty, snapshot_date' },
            { table: 'fact_quality_inspection', cols: 'product_id, disposition (RELEASE/HOLD/SCRAP), defect_type, inspection_date' },
            { table: 'fact_shipment_milestone', cols: 'tracking_number, carrier_name, status, delay_hours, estimated_delivery_at, current_location' },
            { table: 'order_monitoring_records', cols: 'id, customer_order_id, monitoring_status, risk_score, last_checked_at, health_status' },
            { table: 'risk_alerts', cols: 'alert_id, customer_order_id, department, risk_category, severity (CRITICAL/WARNING/INFO), title, description, recommended_action, status (ACTIVE/RESOLVED), fingerprint_sha, created_at' },
            { table: 'agent_actions', cols: 'action_id, alert_id, customer_order_id, action_type (REQUEST_EXPEDITE, NOTIFY_CUSTOMER_REVISED_DATE, REQUEST_CARRIER_UPGRADE, REQUEST_REASSESSMENT), status, action_payload' },
            { table: 'scheduler_leases', cols: 'job_name, leased_until, owner_id (distributed locking for cron jobs)' },
          ],
          apis: [
            'POST /api/monitoring/run-cycle (Trigger on-demand full surveillance audit across all 7 conduits)',
            'POST /api/monitoring/activate (Enroll newly approved order into continuous monitoring radar)',
            'GET /api/monitoring/records (Retrieve all active monitored order records)',
            'GET /api/monitoring/logs (Historical surveillance cycle logs)',
            'GET /api/alerts (List operational variances filtered by department or severity)',
          ],
        },
        processingLayer: {
          title: 'Processing Layer · Business Intelligence & Rules',
          transformations: 'Telemetry anomaly detection, continuous variance computation, SHA-256 alert deduplication, and department-level operational health scoring.',
          calculations: [
            { name: 'Delivery Commitment Breach', formula: 'Breach Days = Current Date - Confirmed Delivery Date (Critical if > 0)' },
            { name: 'Production Stagnation Risk', formula: 'Elapsed Ratio = (Current - Order Date)/(Confirmed - Order Date); Bottleneck if Elapsed > 0.60 and Produced < 0.25 Target' },
            { name: 'Department Readiness Health Score', formula: 'Readiness % = max(0, 100 - (Critical Risks * 15) - (Warning Risks * 5))' },
            { name: 'SHA-256 Alert Deduplication', formula: 'Fingerprint = SHA256(Order_ID + Dept + Category + Root_Cause) preventing repeat alert spam' },
          ],
          businessRules: [
            'Deduplication & Anti-Fatigue: Existing active alerts with matching SHA fingerprint are refreshed rather than duplicated.',
            'Distributed Lease Locking: Cron execution acquires a lease in scheduler_leases to prevent multi-container cluster concurrency collisions.',
            'Dual-Channel Notification Governance: High-severity variances trigger dual alerts to both Customer Service and designated Department Leads.',
            'Action Safety Boundaries: Autonomous actions require policy evaluation; automatic expedite/carrier actions obey daily limit caps (max 50/day).',
          ],
          dataModels: 'SQLAlchemy ORM (OrderMonitoringRecord, RiskAlert, AgentAction, SchedulerLease) & Pydantic Schemas (RiskAlertResponse, MonitoringRecordResponse, AgentActionCreate).',
        },
        presentationLayer: {
          title: 'Presentation Layer · Dashboards & Operational Surfaces',
          dashboards: 'Monitoring Command Center (/monitoring), Active Alerts Feed, and Notification Outbox (/monitoring/outbox).',
          kpis: ['Total Monitored Orders', 'At Risk Orders Count', 'On Track Count', 'Department Health Readiness % (ERP, MMS, MES, WMS, QMS, TMS, PLM)', 'Dispatched Notifications Count'],
          reports: 'Surveillance Cycle Summary Reports, Operational Variance Logs, and Carrier Milestone SLA Reports.',
          alerts: 'Real-time alert notifications, color-coded severity chips (Critical, Warning), and dual-channel SMTP email dispatches via Ethereal.',
          userInterfaces: 'Department Risk Overview with 7 circular gauge rings and SVG flow arrows, Active Operational Variances Table with root-cause cards, live surveillance activity stream, and "▶ Run Monitoring" trigger button.',
        },
        aiLayer: {
          title: 'AI Intelligence Layer · Cognitive Core & Automation',
          analyses: 'Cross-department risk propagation (e.g. calculating how an MMS component shortage cascades into MES plant line starvation, pushes WMS dispatch, and causes TMS carrier SLA breach).',
          predicts: 'Impending customer delivery breaches days before the confirmed date is missed.',
          detects: 'Silent operational variances: unacknowledged supplier delays, carrier checkpoint transit lags, and machine line slowdowns.',
          recommends: 'Specific, actionable corrective mitigations: REQUEST_EXPEDITE, NOTIFY_CUSTOMER_REVISED_DATE, REQUEST_CARRIER_UPGRADE, or REQUEST_REASSESSMENT.',
          automates: 'Continuous surveillance cycle execution, automated HTML email dispatch via Ethereal SMTP, and risk alert lifecycle updates.',
        },
      },
    ],
    steps: [
      {
        step: '1. ReAct Reasoning Loop (Reasoning + Acting)',
        desc: 'Agents employ ReAct loops where the LLM inspects input goals, reasons about intermediate state in a scratchpad, selects specialized tools with JSON arguments, and synthesizes final answers.',
        tech: 'backend/app/agent/agent_loop.py · DomoTextLLM',
      },
      {
        step: '2. Dynamic Lead Time & Critical Path Analysis',
        desc: 'Agent 2 calculates production critical path: WMS staging (1-2d) + MES line run days (order_qty / 713 daily throughput + queue setup) + QMS release (1-2d) + TMS transit (3-5d) = Achievable Delivery Date.',
        tech: 'FeasibilityService._calculate_achievable_delivery',
      },
      {
        step: '3. Risk Fingerprinting & Action Proposal',
        desc: 'Agent 3 monitors confirmed orders against live milestones. When a delay risk is detected (e.g. CARRIER_TRANSIT_DELAY, QUALITY_HOLD), it records an alert and proposes a matching corrective action.',
        tech: 'MonitoringService._evaluate_order_risks · AgentActionService',
      },
    ],
    inputs: ['Customer orders', 'Factory queue parameters', 'Shipment tracking milestones', 'Operator chat prompts'],
    outputs: ['OrderAssessments', 'CommitmentProposals', 'DepartmentReadiness snapshots', 'RiskAlerts', 'AgentActions'],
    tables: ['order_assessments', 'department_readiness', 'commitment_proposals', 'order_monitoring_records', 'risk_alerts', 'agent_actions'],
  },
  governance: {
    title: 'Stage 4: Mandatory Human Approval & Safety Governance Gate',
    tagline: 'Segregation of Duties, Mandatory Human Approval & Kill Switches',
    overview:
      'Autonomous AI operations are governed by strict guardrails. Agent 2 calculates achievable delivery commitments, but automatic approval is permanently disabled: all customer commitments strictly require human commercial approval by Customer Service or Plant Leadership before confirmation.',
    liveLink: { to: '/my-work', label: 'View Approvals Queue' },
    steps: [
      {
        step: '1. Mandatory Human Approval Requirement',
        desc: 'All feasibility proposals generated by Agent 2 are submitted strictly in PENDING state. Automated self-approval is prohibited; every commitment requires human commercial verification.',
        tech: 'backend/app/services/feasibility_service.py · WorkflowService',
      },
      {
        step: '2. Strict Segregation of Duties (SoD)',
        desc: 'Proposals generated by Agent 2 are routed to human operators. An autonomous agent can never approve its own proposals or commit customer delivery dates without human sign-off.',
        tech: 'WorkflowService.approve_proposal (SoD enforcement)',
      },
      {
        step: '3. Rate Limits, Cost Caps & Emergency Kill Switch',
        desc: 'Central settings enforce max 100 LLM calls/hour, max 50 auto-actions/day, and cost limits. Administrators can pause/resume Agent 1, 2, or 3 instantly from the Admin Agent Control page.',
        tech: 'backend/app/services/agent_controls_service.py · /admin/agents',
      },
      {
        step: '4. Automatic Human Escalation',
        desc: 'If agent confidence is LOW, or LLM output fails schema validation twice, the system marks the item NEEDS_HUMAN, creates an escalation log, and routes it to Customer Service.',
        tech: 'AgentControlsService.escalate_item · EmailService',
      },
    ],
    components: [
      { name: 'Rule 1: Overall Feasible & High Confidence', role: 'Status must be strictly FEASIBLE with confidence HIGH. Any CONDITIONAL or UNFEASIBLE status requires detailed human triage.', icon: CheckCircle2 },
      { name: 'Rule 2: Commercial Value & Pricing Verification', role: 'Order pricing, terms, and margin calculations are reviewed by human commercial managers.', icon: Lock },
      { name: 'Rule 3: Zero Blocked Departments', role: 'All 7 departments must be verified READY or CLEAR across ERP, MMS, MES, WMS, QMS, TMS, and PLM.', icon: ShieldAlert },
      { name: 'Rule 4: Customer Date Commitment Met', role: 'Human reviewer validates achievable delivery date vs customer requested date (variance <= 0 days).', icon: Clock },
      { name: 'Rule 5: Customer Account Review', role: 'Customer service verifies account status, credit terms, and relationship history.', icon: Building2 },
      { name: 'Rule 6: Mandatory Human Sign-Off (100% HITL)', role: 'Enforces 100% human-in-the-loop commercial approval before committing to production or dispatch.', icon: Zap },
    ],
    inputs: ['CommitmentProposals', 'OrderAssessments', 'Customer risk flags', 'Agent execution metrics'],
    outputs: ['Approved commitments triggering Agent 3 monitoring', 'Escalated items routed to My Work queue'],
    tables: ['commitment_proposals', 'agent_control_limits', 'agent_escalations', 'audit_log'],
  },
  execution: {
    title: 'Stage 5: Closed-Loop Execution & Outcomes',
    tagline: 'Outbox Dispatch, Action Executors & Delivery Outcome Tracking',
    overview:
      'The final stage closes the manufacturing loop. Approved commitments and risk mitigation actions are executed through dual-channel email notifications, automated order revisions, carrier lane upgrades, and on-time delivery KPI tracking.',
    liveLink: { to: '/monitoring/outbox', label: 'View Notification Outbox' },
    steps: [
      {
        step: '1. Dual-Channel Email Notification Dispatch',
        desc: 'When risks or order approvals occur, EmailService generates HTML notices and dispatches to Customer Service and responsible department owners (e.g. logistics@mfg360.internal, quality@mfg360.internal) via Ethereal SMTP with outbox logs.',
        tech: 'backend/app/services/email_service.py · NotificationOutbox',
      },
      {
        step: '2. Corrective Action Execution Engine',
        desc: 'Approved agent actions execute safely: REQUEST_EXPEDITE raises production priority; NOTIFY_CUSTOMER_REVISED_DATE dispatches customer delay notification; REQUEST_CARRIER_UPGRADE requests priority freight; REQUEST_REASSESSMENT triggers Agent 2 revision + 1.',
        tech: 'backend/app/services/agent_action_service.py · ActionExecutors',
      },
      {
        step: '3. Closed-Loop Outcome & KPI Tracking',
        desc: 'When an order is delivered, OutcomeService records promised vs actual delivery date into agent_outcomes. Calculates real-world commitment reliability for auto-approved vs human-approved orders.',
        tech: 'backend/app/services/outcome_service.py · agent_outcomes table',
      },
    ],
    components: [
      { name: 'Dual-Channel Email Dispatch', role: 'Dispatches HTML alerts to Customer Service + Department Leads via Ethereal SMTP with tracking links.', icon: Mail },
      { name: 'REQUEST_EXPEDITE Executor', role: 'Flags work order priority in MES and sends urgent staging requests to plant managers.', icon: Zap },
      { name: 'NOTIFY_CUSTOMER_REVISED_DATE', role: 'Generates formal delay notice with revised commitment date and root-cause explanation for the customer.', icon: Send },
      { name: 'REQUEST_CARRIER_UPGRADE', role: 'Requests TMS logistics upgrade from standard road freight to express air cargo to recover in-transit delay.', icon: Truck },
      { name: 'REQUEST_REASSESSMENT', role: 'Re-evaluates breached order via FeasibilityService and generates a revised PENDING proposal (revision + 1).', icon: RotateCcw },
      { name: 'On-Time Delivery KPI Tracking', role: 'Calculates delivery variance (actual - promised) and compares on-time rates between auto and human approved orders.', icon: Activity },
    ],
    inputs: ['Approved corrective actions', 'Risk alerts', 'Carrier delivery timestamps'],
    outputs: ['Dispatched customer communications', 'Revised order commitments', 'Delivery variance records in agent_outcomes'],
    tables: ['notification_outbox', 'agent_actions', 'agent_outcomes', 'audit_log'],
  },
}

export default function Architecture() {
  const [selectedStageId, setSelectedStageId] = useState('agents')
  const [activeAgentTab, setActiveAgentTab] = useState('agent2')
  const [detailTab, setDetailTab] = useState('steps') // 'steps' | 'components' | 'flow' | 'tables'

  const activeStage = useMemo(() => {
    return STAGES.find((s) => s.id === selectedStageId) || STAGES[2]
  }, [selectedStageId])

  const stageDetail = STAGE_DETAILS[selectedStageId] || STAGE_DETAILS.agents

  return (
    <div className="page-stack" style={{ gap: 24, paddingBottom: 40 }}>
      {/* 1. TOP NAVIGATION / VIEW TABS */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Link
            to="/architecture"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 18px',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 600,
              textDecoration: 'none',
              background: 'var(--surface-hi)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--line)',
              transition: 'all 0.15s ease',
            }}
          >
            <Layers size={16} />
            <span>System Architecture Diagram</span>
          </Link>

          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 18px',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 700,
              background: 'var(--brand-purple)',
              color: '#ffffff',
              boxShadow: '0 2px 8px rgba(111, 61, 186, 0.25)',
            }}
          >
            <Workflow size={16} />
            <span>Interactive Framework Flow Pipeline</span>
          </div>
        </div>

        <Link
          to="/architecture"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 7,
            padding: '8px 14px',
            borderRadius: 8,
            fontSize: 12,
            fontWeight: 600,
            background: 'var(--brand-purple-soft)',
            color: 'var(--brand-purple)',
            border: '1px solid rgba(111, 61, 186, 0.25)',
            textDecoration: 'none',
          }}
        >
          <Layers size={14} />
          <span>View Pipeline Architecture Diagram &rarr;</span>
        </Link>
      </div>

      {/* 2. APPLICATION FLOW IN CARDS & ARROW MARKS */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: 'var(--text-primary)' }}>
              Interactive Framework Flow Pipeline
            </h3>
            <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>
              Click any stage card to inspect its technical implementation, execution logic, and data flow below.
            </p>
          </div>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: 'var(--brand-purple)',
              background: 'var(--brand-purple-soft)',
              padding: '3px 10px',
              borderRadius: 20,
            }}
          >
            Active Stage: {activeStage.name}
          </span>
        </div>

        {/* FLOW CARDS CONTAINER WITH ARROWS */}
        <div
          style={{
            display: 'flex',
            alignItems: 'stretch',
            gap: 10,
            overflowX: 'auto',
            paddingBottom: 8,
          }}
        >
          {STAGES.map((stage, idx) => {
            const isSelected = selectedStageId === stage.id
            const StageIcon = stage.icon
            const isLast = idx === STAGES.length - 1

            return (
              <div
                key={stage.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  flex: '1 1 0',
                  minWidth: 200,
                }}
              >
                {/* STAGE CARD */}
                <div
                  onClick={() => setSelectedStageId(stage.id)}
                  className="card"
                  style={{
                    flex: 1,
                    padding: '16px 14px',
                    borderRadius: 12,
                    cursor: 'pointer',
                    transition: 'all 0.22s cubic-bezier(0.4, 0, 0.2, 1)',
                    background: isSelected
                      ? 'var(--surface-hi)'
                      : 'var(--surface-hi)',
                    border: isSelected
                      ? `2px solid ${stage.accentColor}`
                      : '1px solid var(--line)',
                    boxShadow: isSelected
                      ? `0 0 0 2px ${stage.accentColor}33, 0 8px 24px ${stage.accentColor}25`
                      : '0 1px 3px rgba(0,0,0,0.03)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minHeight: 165,
                    position: 'relative',
                    overflow: 'hidden',
                  }}
                >
                  {/* Selected Indicator Top Accent Bar */}
                  {isSelected && (
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        height: 4,
                        background: stage.accentColor,
                      }}
                    />
                  )}

                  <div>
                    {/* Top Row: Number & Icon */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 800,
                          color: isSelected ? stage.accentColor : 'var(--text-muted)',
                          letterSpacing: '0.06em',
                        }}
                      >
                        STAGE {stage.stepNumber}
                      </span>

                      <div
                        style={{
                          width: 30,
                          height: 30,
                          borderRadius: 8,
                          background: isSelected ? `${stage.accentColor}20` : 'var(--kg-bg-2)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: isSelected ? stage.accentColor : 'var(--text-secondary)',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <StageIcon size={16} />
                      </div>
                    </div>

                    {/* Card Title & Category */}
                    <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1.3 }}>
                      {stage.name}
                    </div>
                    <div style={{ fontSize: 11, color: stage.accentColor, fontWeight: 700, marginTop: 2 }}>
                      {stage.category}
                    </div>

                    {/* Short Description */}
                    <p
                      style={{
                        margin: '8px 0 0',
                        fontSize: 10.5,
                        color: 'var(--text-secondary)',
                        lineHeight: 1.45,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {stage.summary}
                    </p>
                  </div>

                  {/* Bottom: Status Pill */}
                  <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span
                      style={{
                        fontSize: 9.5,
                        fontWeight: 700,
                        color: isSelected ? stage.accentColor : 'var(--text-muted)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      {isSelected ? (
                        <>
                          <CheckCircle2 size={11} /> Active View
                        </>
                      ) : (
                        <>
                          <ChevronRight size={11} /> Click to inspect
                        </>
                      )}
                    </span>
                  </div>
                </div>

                {/* ARROW MARK CONNECTOR */}
                {!isLast && (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '0 4px',
                      flexShrink: 0,
                    }}
                  >
                    <div
                      style={{
                        width: 24,
                        height: 24,
                        borderRadius: '50%',
                        background: 'var(--surface-hi)',
                        border: '1px solid var(--line)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--brand-purple)',
                        boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
                      }}
                      title={stage.arrowLabel}
                    >
                      <ArrowRight size={13} />
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* 3. STAGE DEEP DIVE PANEL ("WHAT IS DONE IN THAT DOWN") */}
      <div
        className="card"
        style={{
          padding: 24,
          borderRadius: 14,
          background: 'var(--surface-hi)',
          border: `1.5px solid ${activeStage.accentColor}55`,
          boxShadow: `0 8px 30px ${activeStage.accentColor}12`,
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
        }}
      >
        {/* Panel Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: 14,
            paddingBottom: 16,
            borderBottom: '1px solid var(--line)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: `${activeStage.accentColor}18`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: activeStage.accentColor,
              }}
            >
              {(() => {
                const IconComponent = activeStage.icon
                return <IconComponent size={24} />
              })()}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 800,
                    color: activeStage.accentColor,
                    background: `${activeStage.accentColor}18`,
                    padding: '2px 8px',
                    borderRadius: 12,
                    textTransform: 'uppercase',
                  }}
                >
                  STAGE {activeStage.stepNumber}
                </span>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: 'var(--text-primary)' }}>
                  {stageDetail.title}
                </h2>
              </div>
              <p style={{ margin: '3px 0 0', fontSize: 12.5, color: 'var(--text-secondary)' }}>
                {stageDetail.tagline}
              </p>
            </div>
          </div>

          {/* Action Links */}
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            {stageDetail.liveLink && (
              <Link
                to={stageDetail.liveLink.to}
                className="button button-primary"
                style={{
                  fontSize: 12,
                  padding: '7px 14px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  fontWeight: 700,
                  background: activeStage.accentColor,
                  color: 'white',
                }}
              >
                <span>{stageDetail.liveLink.label}</span>
                <ExternalLink size={13} />
              </Link>
            )}
          </div>
        </div>

        {/* Detailed Description */}
        <div
          style={{
            padding: '14px 18px',
            borderRadius: 10,
            background: 'var(--kg-bg-2)',
            border: '1px solid var(--line)',
            fontSize: 13,
            lineHeight: 1.6,
            color: 'var(--text-primary)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <Info size={18} style={{ color: activeStage.accentColor, flexShrink: 0, marginTop: 2 }} />
            <div>{stageDetail.overview}</div>
          </div>
        </div>

        {/* SUB-TABS: WHAT IS DONE / COMPONENTS / DATA FLOW / TABLES */}
        <div style={{ display: 'flex', gap: 8, borderBottom: '1px solid var(--line)', paddingBottom: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setDetailTab('steps')}
            style={{
              padding: '6px 14px',
              fontSize: 12,
              fontWeight: 700,
              borderRadius: 8,
              border: 'none',
              cursor: 'pointer',
              background: detailTab === 'steps' ? `${activeStage.accentColor}20` : 'transparent',
              color: detailTab === 'steps' ? activeStage.accentColor : 'var(--text-secondary)',
            }}
          >
            ⚡ What Is Done (Execution Steps)
          </button>

          {stageDetail.subAgents && (
            <button
              type="button"
              onClick={() => setDetailTab('agents')}
              style={{
                padding: '6px 14px',
                fontSize: 12,
                fontWeight: 700,
                borderRadius: 8,
                border: 'none',
                cursor: 'pointer',
                background: detailTab === 'agents' ? `${activeStage.accentColor}20` : 'transparent',
                color: detailTab === 'agents' ? activeStage.accentColor : 'var(--text-secondary)',
              }}
            >
              🤖 The 3 AI Agents (Deep Dive)
            </button>
          )}

          {stageDetail.components && (
            <button
              type="button"
              onClick={() => setDetailTab('components')}
              style={{
                padding: '6px 14px',
                fontSize: 12,
                fontWeight: 700,
                borderRadius: 8,
                border: 'none',
                cursor: 'pointer',
                background: detailTab === 'components' ? `${activeStage.accentColor}20` : 'transparent',
                color: detailTab === 'components' ? activeStage.accentColor : 'var(--text-secondary)',
              }}
            >
              🧩 Architecture Components &amp; Roles
            </button>
          )}

          <button
            type="button"
            onClick={() => setDetailTab('flow')}
            style={{
              padding: '6px 14px',
              fontSize: 12,
              fontWeight: 700,
              borderRadius: 8,
              border: 'none',
              cursor: 'pointer',
              background: detailTab === 'flow' ? `${activeStage.accentColor}20` : 'transparent',
              color: detailTab === 'flow' ? activeStage.accentColor : 'var(--text-secondary)',
            }}
          >
            🔄 Inputs &amp; Outputs Flow
          </button>
        </div>

        {/* TAB 1: EXECUTION STEPS (WHAT IS DONE IN THAT STAGE) */}
        {detailTab === 'steps' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <h4 style={{ margin: 0, fontSize: 14, fontWeight: 800, color: 'var(--text-primary)' }}>
              Step-by-Step Execution Breakdown
            </h4>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 14 }}>
              {stageDetail.steps.map((st, i) => (
                <div
                  key={i}
                  style={{
                    padding: 16,
                    borderRadius: 10,
                    background: 'var(--kg-bg-2)',
                    border: '1px solid var(--line)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: 10,
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span
                        style={{
                          width: 22,
                          height: 22,
                          borderRadius: '50%',
                          background: `${activeStage.accentColor}25`,
                          color: activeStage.accentColor,
                          fontSize: 11,
                          fontWeight: 800,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {i + 1}
                      </span>
                      <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>{st.step}</strong>
                    </div>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      {st.desc}
                    </p>
                  </div>

                  <div
                    style={{
                      fontSize: 10.5,
                      fontFamily: 'monospace',
                      padding: '4px 8px',
                      background: 'rgba(0,0,0,0.04)',
                      borderRadius: 6,
                      color: 'var(--text-muted)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <FileCode size={12} style={{ color: activeStage.accentColor }} />
                    <span>{st.tech}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 2: THE 3 AI AGENTS DEEP DIVE (AVAILABLE ON STAGE 3) */}
        {detailTab === 'agents' && stageDetail.subAgents && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Agent Select Pills */}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {stageDetail.subAgents.map((ag) => {
                const isActive = activeAgentTab === ag.id
                return (
                  <button
                    key={ag.id}
                    type="button"
                    onClick={() => setActiveAgentTab(ag.id)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: 10,
                      border: isActive ? '2px solid var(--brand-purple)' : '1px solid var(--line)',
                      background: isActive ? 'var(--brand-purple-soft)' : 'var(--kg-bg-2)',
                      color: isActive ? 'var(--brand-purple)' : 'var(--text-primary)',
                      fontWeight: 800,
                      fontSize: 12,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                    }}
                  >
                    <Bot size={15} />
                    <span>{ag.name.split(':')[0]}</span>
                    <span
                      style={{
                        fontSize: 9.5,
                        fontWeight: 700,
                        padding: '1px 6px',
                        borderRadius: 8,
                        background: isActive ? 'white' : 'rgba(0,0,0,0.05)',
                      }}
                    >
                      {ag.badge}
                    </span>
                  </button>
                )
              })}
            </div>

            {/* Core Architectural Principle Banner */}
            <div
              style={{
                padding: '14px 18px',
                borderRadius: 12,
                background: 'linear-gradient(135deg, rgba(111, 61, 186, 0.08), rgba(59, 130, 246, 0.08))',
                border: '1.5px solid rgba(111, 61, 186, 0.25)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 14,
              }}
            >
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 8,
                  background: 'var(--brand-purple)',
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  marginTop: 2,
                }}
              >
                <Sparkles size={18} />
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.55 }}>
                <strong style={{ fontSize: 13, color: 'var(--brand-purple)', display: 'block', marginBottom: 2 }}>
                  Important Architectural Principle: Three-Tier Autonomous AI Standard
                </strong>
                An enterprise AI agent must never be a simple chatbot connected to a database. Each agent is engineered with a full three-tier stack:
                <span style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                  <span style={{ background: 'rgba(59, 130, 246, 0.12)', color: '#2563eb', padding: '2px 8px', borderRadius: 6, fontWeight: 700, fontSize: 11 }}>
                    1. Data Pipeline Layer (ETL, Tables &amp; APIs)
                  </span>
                  <span style={{ background: 'rgba(14, 165, 233, 0.12)', color: '#0284c7', padding: '2px 8px', borderRadius: 6, fontWeight: 700, fontSize: 11 }}>
                    2. Business Intelligence Layer (Math, Rules &amp; Models)
                  </span>
                  <span style={{ background: 'rgba(245, 158, 11, 0.12)', color: '#d97706', padding: '2px 8px', borderRadius: 6, fontWeight: 700, fontSize: 11 }}>
                    3. Presentation Layer (Dashboards, KPIs &amp; Alerts)
                  </span>
                  <span style={{ background: 'rgba(139, 92, 246, 0.12)', color: '#7c3aed', padding: '2px 8px', borderRadius: 6, fontWeight: 700, fontSize: 11 }}>
                    4. AI Intelligence Layer (ReAct, Predictions &amp; Actions)
                  </span>
                </span>
              </div>
            </div>

            {/* Active Sub-Agent Details */}
            {(() => {
              const currentAgent = stageDetail.subAgents.find((a) => a.id === activeAgentTab) || stageDetail.subAgents[1]

              return (
                <div
                  style={{
                    padding: 22,
                    borderRadius: 14,
                    background: 'var(--kg-bg-2)',
                    border: '1px solid var(--line)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 18,
                  }}
                >
                  {/* Header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 10 }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <h4 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: 'var(--text-primary)' }}>
                          {currentAgent.name}
                        </h4>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: 10,
                            background: 'var(--brand-purple-soft)',
                            color: 'var(--brand-purple)',
                            border: '1px solid rgba(111, 61, 186, 0.25)',
                          }}
                        >
                          {currentAgent.badge}
                        </span>
                      </div>
                      <p style={{ margin: '4px 0 0', fontSize: 12.5, color: 'var(--text-secondary)' }}>
                        {currentAgent.role}
                      </p>
                    </div>

                    <span
                      style={{
                        fontSize: 11,
                        fontFamily: 'monospace',
                        padding: '4px 8px',
                        background: 'var(--surface-hi)',
                        border: '1px solid var(--line)',
                        borderRadius: 6,
                        color: 'var(--brand-purple)',
                      }}
                    >
                      {currentAgent.file}
                    </span>
                  </div>

                  <div style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--text-primary)' }}>
                    <strong>Execution Mechanism:</strong> {currentAgent.mechanism}
                  </div>

                  {/* =========================================================
                      PILLAR 1: INPUT & ENTERPRISE DATA PIPELINE
                      ========================================================= */}
                  {currentAgent.inputLayer && (
                    <div
                      style={{
                        padding: 16,
                        borderRadius: 10,
                        background: 'var(--surface-hi)',
                        border: '1px solid rgba(59, 130, 246, 0.25)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, color: '#3b82f6', fontWeight: 800, fontSize: 13, textTransform: 'uppercase' }}>
                        <Database size={16} /> {currentAgent.inputLayer.title}
                      </div>
                      <p style={{ margin: '0 0 12px', fontSize: 12, color: 'var(--text-secondary)' }}>
                        <strong>Required Data Context:</strong> {currentAgent.inputLayer.requiredData}
                      </p>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 10, marginBottom: 12 }}>
                        {currentAgent.inputLayer.sourceApps.map((app, idx) => (
                          <div key={idx} style={{ padding: '8px 10px', background: 'var(--kg-bg-2)', borderRadius: 8, border: '1px solid var(--line)', fontSize: 11 }}>
                            <strong style={{ color: 'var(--text-primary)', display: 'block' }}>{app.name}</strong>
                            <span style={{ color: 'var(--text-muted)' }}>{app.role}</span>
                          </div>
                        ))}
                      </div>

                      <div style={{ marginBottom: 12 }}>
                        <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                          Database Tables &amp; Required Columns:
                        </span>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
                          {currentAgent.inputLayer.tablesAndColumns.map((tc, idx) => (
                            <div key={idx} style={{ fontSize: 11, background: 'var(--kg-bg-2)', padding: '5px 8px', borderRadius: 6, border: '1px solid var(--line)', display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
                              <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#2563eb' }}>{tc.table}</span>
                              <span style={{ color: 'var(--text-muted)' }}>→</span>
                              <span style={{ fontFamily: 'monospace', fontSize: 10.5, color: 'var(--text-secondary)' }}>{tc.cols}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                          Operational APIs &amp; Endpoints:
                        </span>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                          {currentAgent.inputLayer.apis.map((api, idx) => (
                            <span key={idx} style={{ fontSize: 11, fontFamily: 'monospace', padding: '3px 8px', borderRadius: 6, background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.25)', color: '#2563eb' }}>
                              {api}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* =========================================================
                      PILLAR 2: PROCESSING & BUSINESS INTELLIGENCE
                      ========================================================= */}
                  {currentAgent.processingLayer && (
                    <div
                      style={{
                        padding: 16,
                        borderRadius: 10,
                        background: 'var(--surface-hi)',
                        border: '1px solid rgba(14, 165, 233, 0.25)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, color: '#0ea5e9', fontWeight: 800, fontSize: 13, textTransform: 'uppercase' }}>
                        <Layers size={16} /> {currentAgent.processingLayer.title}
                      </div>

                      <p style={{ margin: '0 0 10px', fontSize: 12, color: 'var(--text-secondary)' }}>
                        <strong>Canonical Transformations:</strong> {currentAgent.processingLayer.transformations}
                      </p>

                      <div style={{ marginBottom: 12 }}>
                        <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                          Domain Calculations &amp; Mathematical Formulas:
                        </span>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 8, marginTop: 6 }}>
                          {currentAgent.processingLayer.calculations.map((calc, idx) => (
                            <div key={idx} style={{ padding: '8px 10px', background: 'var(--kg-bg-2)', borderRadius: 8, border: '1px solid var(--line)', fontSize: 11 }}>
                              <strong style={{ color: 'var(--text-primary)', display: 'block' }}>{calc.name}</strong>
                              <span style={{ fontFamily: 'monospace', fontSize: 10.5, color: '#0284c7' }}>{calc.formula}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div style={{ marginBottom: 10 }}>
                        <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                          Deterministic Business Rules &amp; Governance:
                        </span>
                        <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                          {currentAgent.processingLayer.businessRules.map((rule, idx) => (
                            <li key={idx} style={{ marginBottom: 4 }}>{rule}</li>
                          ))}
                        </ul>
                      </div>

                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        <strong>Underlying Data Models:</strong> {currentAgent.processingLayer.dataModels}
                      </div>
                    </div>
                  )}

                  {/* =========================================================
                      PILLAR 3: PRESENTATION & USER EXPERIENCE
                      ========================================================= */}
                  {currentAgent.presentationLayer && (
                    <div
                      style={{
                        padding: 16,
                        borderRadius: 10,
                        background: 'var(--surface-hi)',
                        border: '1px solid rgba(245, 158, 11, 0.25)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, color: '#f59e0b', fontWeight: 800, fontSize: 13, textTransform: 'uppercase' }}>
                        <Eye size={16} /> {currentAgent.presentationLayer.title}
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10, fontSize: 11.5 }}>
                        <div>
                          <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: 2 }}>Dashboards &amp; Views</strong>
                          <span style={{ color: 'var(--text-secondary)' }}>{currentAgent.presentationLayer.dashboards}</span>
                        </div>
                        <div>
                          <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: 2 }}>Reports &amp; Audits</strong>
                          <span style={{ color: 'var(--text-secondary)' }}>{currentAgent.presentationLayer.reports}</span>
                        </div>
                        <div>
                          <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: 2 }}>Alerts &amp; Outbox</strong>
                          <span style={{ color: 'var(--text-secondary)' }}>{currentAgent.presentationLayer.alerts}</span>
                        </div>
                      </div>

                      <div style={{ marginTop: 12 }}>
                        <strong style={{ color: 'var(--text-primary)', display: 'block', fontSize: 11, marginBottom: 4 }}>Tracked Operational KPIs:</strong>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {currentAgent.presentationLayer.kpis.map((kpi, idx) => (
                            <span key={idx} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 6, background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.25)', color: '#b45309', fontWeight: 600 }}>
                              {kpi}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-secondary)' }}>
                        <strong>User Interfaces &amp; Controls:</strong> {currentAgent.presentationLayer.userInterfaces}
                      </div>
                    </div>
                  )}

                  {/* =========================================================
                      PILLAR 4: AI INTELLIGENCE & COGNITIVE CORE
                      ========================================================= */}
                  {currentAgent.aiLayer && (
                    <div
                      style={{
                        padding: 16,
                        borderRadius: 10,
                        background: 'var(--surface-hi)',
                        border: '1px solid rgba(139, 92, 246, 0.3)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, color: 'var(--brand-purple)', fontWeight: 800, fontSize: 13, textTransform: 'uppercase' }}>
                        <Bot size={16} /> {currentAgent.aiLayer.title}
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 10, fontSize: 11.5, marginBottom: 12 }}>
                        <div style={{ padding: '8px 10px', background: 'var(--kg-bg-2)', borderRadius: 8, border: '1px solid var(--line)' }}>
                          <strong style={{ color: '#7c3aed', display: 'block' }}>Analyses:</strong>
                          <span style={{ color: 'var(--text-secondary)' }}>{currentAgent.aiLayer.analyses}</span>
                        </div>
                        <div style={{ padding: '8px 10px', background: 'var(--kg-bg-2)', borderRadius: 8, border: '1px solid var(--line)' }}>
                          <strong style={{ color: '#0ea5e9', display: 'block' }}>Predicts:</strong>
                          <span style={{ color: 'var(--text-secondary)' }}>{currentAgent.aiLayer.predicts}</span>
                        </div>
                        <div style={{ padding: '8px 10px', background: 'var(--kg-bg-2)', borderRadius: 8, border: '1px solid var(--line)' }}>
                          <strong style={{ color: '#ef4444', display: 'block' }}>Detects:</strong>
                          <span style={{ color: 'var(--text-secondary)' }}>{currentAgent.aiLayer.detects}</span>
                        </div>
                        <div style={{ padding: '8px 10px', background: 'var(--kg-bg-2)', borderRadius: 8, border: '1px solid var(--line)' }}>
                          <strong style={{ color: '#10b981', display: 'block' }}>Recommends:</strong>
                          <span style={{ color: 'var(--text-secondary)' }}>{currentAgent.aiLayer.recommends}</span>
                        </div>
                      </div>

                      <p style={{ margin: '0 0 10px', fontSize: 12, color: 'var(--text-secondary)' }}>
                        <strong>Automates:</strong> {currentAgent.aiLayer.automates}
                      </p>

                      {/* Registered Tools */}
                      <div>
                        <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                          Registered ReAct Tools &amp; Capabilities:
                        </span>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                          {currentAgent.tools.map((t, idx) => (
                            <span
                              key={idx}
                              style={{
                                fontSize: 11,
                                fontFamily: 'monospace',
                                padding: '3px 9px',
                                borderRadius: 6,
                                background: 'var(--kg-bg-2)',
                                border: '1px solid var(--line)',
                                color: 'var(--text-primary)',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 5,
                              }}
                            >
                              <Terminal size={11} style={{ color: 'var(--brand-purple)' }} />
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Fallback Guarantee */}
                  <div
                    style={{
                      padding: '10px 14px',
                      borderRadius: 8,
                      background: 'rgba(34, 197, 94, 0.08)',
                      border: '1px solid rgba(34, 197, 94, 0.25)',
                      fontSize: 11.5,
                      color: '#16a34a',
                      fontWeight: 600,
                    }}
                  >
                    🛡️ <strong>Safety Baseline Guarantee:</strong> {currentAgent.fallback}
                  </div>
                </div>
              )
            })()}
          </div>
        )}

        {/* TAB 3: COMPONENTS & ROLES */}
        {detailTab === 'components' && stageDetail.components && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <h4 style={{ margin: 0, fontSize: 14, fontWeight: 800, color: 'var(--text-primary)' }}>
              Integrated Components &amp; System Responsibilities
            </h4>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
              {stageDetail.components.map((comp, i) => {
                const CompIcon = comp.icon || Database

                return (
                  <div
                    key={i}
                    style={{
                      padding: 14,
                      borderRadius: 10,
                      background: 'var(--kg-bg-2)',
                      border: '1px solid var(--line)',
                      display: 'flex',
                      gap: 12,
                      alignItems: 'flex-start',
                    }}
                  >
                    <div
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        background: `${activeStage.accentColor}18`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: activeStage.accentColor,
                        flexShrink: 0,
                      }}
                    >
                      <CompIcon size={16} />
                    </div>

                    <div>
                      <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>{comp.name}</strong>
                      <p style={{ margin: '3px 0 0', fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                        {comp.role}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* TAB 4: INPUTS & OUTPUTS FLOW */}
        {detailTab === 'flow' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
            {/* Inputs Box */}
            <div
              style={{
                padding: 16,
                borderRadius: 10,
                background: 'var(--kg-bg-2)',
                border: '1px solid var(--line)',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: 6,
                    background: 'rgba(59, 130, 246, 0.15)',
                    color: '#3b82f6',
                    fontSize: 10,
                    fontWeight: 800,
                  }}
                >
                  UPSTREAM INPUTS
                </span>
                <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>What Enters This Stage</strong>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {stageDetail.inputs.map((inp, idx) => (
                  <div
                    key={idx}
                    style={{
                      fontSize: 12,
                      color: 'var(--text-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '4px 0',
                    }}
                  >
                    <ChevronRight size={13} style={{ color: '#3b82f6' }} />
                    <span>{inp}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Outputs Box */}
            <div
              style={{
                padding: 16,
                borderRadius: 10,
                background: 'var(--kg-bg-2)',
                border: '1px solid var(--line)',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: 6,
                    background: 'rgba(16, 185, 129, 0.15)',
                    color: '#10b981',
                    fontSize: 10,
                    fontWeight: 800,
                  }}
                >
                  DOWNSTREAM OUTPUTS
                </span>
                <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>What Exits This Stage</strong>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {stageDetail.outputs.map((out, idx) => (
                  <div
                    key={idx}
                    style={{
                      fontSize: 12,
                      color: 'var(--text-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '4px 0',
                    }}
                  >
                    <CheckCircle2 size={13} style={{ color: '#10b981' }} />
                    <span>{out}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Database Tables Involved */}
        {stageDetail.tables && (
          <div
            style={{
              padding: '12px 16px',
              borderRadius: 8,
              background: 'var(--kg-bg-2)',
              border: '1px solid var(--line)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 10,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Table size={15} style={{ color: activeStage.accentColor }} />
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Underlying Database Tables:
              </span>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {stageDetail.tables.map((t, idx) => (
                <span
                  key={idx}
                  style={{
                    fontSize: 11,
                    fontFamily: 'monospace',
                    padding: '2px 8px',
                    borderRadius: 6,
                    background: 'var(--surface-hi)',
                    border: '1px solid var(--line)',
                    color: 'var(--text-primary)',
                  }}
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
