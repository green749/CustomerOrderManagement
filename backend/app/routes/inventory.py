from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.inventory_service import InventoryService
from ..schemas.common import PaginatedResponse
from ..schemas.inventory import MaterialInventoryItem, MaterialInventorySummary
from ..models.auth import User
from ..services.auth_service import get_current_user

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])


@router.get("/materials", response_model=PaginatedResponse[MaterialInventoryItem])
def get_materials(
    page: int = Query(default=1, ge=1, description="Page number starting at 1"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    plant_id: Optional[str] = Query(default=None, description="Filter by plant ID (e.g. IN-TN-01)"),
    material_id: Optional[str] = Query(default=None, description="Filter by material ID (e.g. MAT-SOC-001)"),
    warehouse_id: Optional[str] = Query(default=None, description="Filter by warehouse ID"),
    status: Optional[str] = Query(default=None, description="Filter by inventory status"),
    sort_by: str = Query(default="snapshot_date", description="Field to sort by"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve raw materials inventory daily snapshots with net available quantity calculations."""
    items, total = InventoryService.get_materials(
        db=db,
        page=page,
        page_size=page_size,
        plant_id=plant_id,
        material_id=material_id,
        warehouse_id=warehouse_id,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/materials/{material_id}/summary", response_model=MaterialInventorySummary)
def get_material_summary(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve aggregate inventory totals and warehouse distribution for a specific raw material."""
    summary = InventoryService.get_material_summary(db, material_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Raw material '{material_id}' not found in inventory records",
        )
    return summary

