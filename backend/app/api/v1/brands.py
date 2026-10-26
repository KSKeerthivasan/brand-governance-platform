from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.organization import OrganizationMembership
from app.models.brand import Brand
from app.schemas.organization import BrandOut, BrandCreate
from app.api.deps import require_any_member, require_org_admin

router = APIRouter()

@router.get("", response_model=List[BrandOut])
def list_brands(
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    brands = db.query(Brand).filter(Brand.organization_id == membership.organization_id).all()
    return brands

@router.post("", response_model=BrandOut)
def create_brand(
    req: BrandCreate,
    membership: OrganizationMembership = Depends(require_org_admin),
    db: Session = Depends(get_db)
):
    brand = Brand(
        organization_id=membership.organization_id,
        name=req.name,
        description=req.description
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand
