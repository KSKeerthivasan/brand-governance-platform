from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.organizations import router as org_router
from app.api.v1.brands import router as brand_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.content import router as content_router
from app.api.v1.governance import router as governance_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.audit import router as audit_router
from app.api.v1.analytics import router as analytics_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(org_router, prefix="/organizations", tags=["Organizations"])
api_v1_router.include_router(brand_router, prefix="/brands", tags=["Brands"])
api_v1_router.include_router(knowledge_router, prefix="/knowledge", tags=["Knowledge"])
api_v1_router.include_router(content_router, prefix="/content", tags=["Content"])
api_v1_router.include_router(governance_router, prefix="/governance", tags=["Governance Engine"])
api_v1_router.include_router(approvals_router, prefix="/approvals", tags=["Approvals"])
api_v1_router.include_router(audit_router, prefix="/audit", tags=["Audit History"])
api_v1_router.include_router(analytics_router, prefix="/analytics", tags=["Governance Analytics"])
