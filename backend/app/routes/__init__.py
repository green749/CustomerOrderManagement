from .auth import router as auth_router
from .dashboard import router as dashboard_router
from .orders import router as orders_router
from .inventory import router as inventory_router
from .conversations import router as conversations_router
from .agent import router as agent_router, agents_router
from .allocation import router as allocation_router
from .commitments import router as commitments_router
from .kpis import router as kpis_router
from .feasibility import feasibility_router
from .monitoring import monitoring_router
from .alerts import alerts_router
from .connectors import connectors_router
from .actions import router as actions_router
from .customers import router as customers_router

__all__ = [
    "auth_router",
    "dashboard_router",
    "orders_router",
    "inventory_router",
    "conversations_router",
    "agent_router",
    "agents_router",
    "allocation_router",
    "commitments_router",
    "kpis_router",
    "feasibility_router",
    "monitoring_router",
    "alerts_router",
    "connectors_router",
    "actions_router",
    "customers_router",
]
