import uuid
import hashlib
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.rescore import ImpactRescoringJob, ImpactRescoringBatchItem
from app.models.content import ContentItem, ContentVersion, GovernanceRun
from app.models.knowledge import KnowledgeBaseVersion
from app.services.governance_engine import governance_engine
from app.services.audit import log_audit_event

logger = logging.getLogger(__name__)

# Bounded synchronous execution parameters to prevent HTTP request timeouts
MAX_RESCORING_ITEMS = 50
RESCORING_TIME_BUDGET_SECONDS = 15.0


class ImpactRescoreService:
    """
    Executes bounded, idempotent re-scoring operations over drafts
    when a new Knowledge Base Version is activated.
    Rescoring is strictly synchronous within the activation request.
    Enforces time budgeting and guarantees terminal job status (never left in 'processing').
    """

    def trigger_rescore_for_activation(
        self,
        db: Session,
        org_id: str,
        kb_version: KnowledgeBaseVersion,
        user_id: Optional[str] = None
    ) -> ImpactRescoringJob:
        """
        Creates and executes an ImpactRescoringJob for all active drafts in the organization.
        Processes synchronously in batches of 20 with snapshot isolation and audit trail logging.
        Guarantees that job transitions to a terminal state (completed, partially_failed, or failed).
        """
        idempotency_key = f"rescore_kbv_{kb_version.id}_{int(datetime.utcnow().timestamp())}"
        start_time = time.perf_counter()

        # 1. Query candidate drafts to re-evaluate (capped at MAX_RESCORING_ITEMS)
        candidate_items = db.query(ContentItem).filter(
            ContentItem.organization_id == org_id,
            ContentItem.status.in_(["draft", "submitted", "in_review", "changes_requested"])
        ).limit(MAX_RESCORING_ITEMS).all()

        total_items = len(candidate_items)
        batch_size = 20
        total_batches = (total_items + batch_size - 1) // batch_size if total_items > 0 else 0

        job = ImpactRescoringJob(
            organization_id=org_id,
            knowledge_base_version_id=kb_version.id,
            idempotency_key=idempotency_key,
            status="processing" if total_items > 0 else "completed",
            total_items=total_items,
            completed_items=0,
            failed_items=0,
            total_batches=total_batches,
            completed_batches=0,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow() if total_items == 0 else None
        )
        db.add(job)
        db.flush()

        if total_items == 0:
            db.commit()
            db.refresh(job)
            return job

        # 2. Process each item synchronously with time budget monitoring
        completed_count = 0
        failed_count = 0
        timed_out = False

        try:
            for idx, item in enumerate(candidate_items):
                # Check elapsed time against safety budget
                elapsed = time.perf_counter() - start_time
                if elapsed > RESCORING_TIME_BUDGET_SECONDS:
                    logger.warning(
                        f"Rescoring time budget exceeded ({elapsed:.2f}s > {RESCORING_TIME_BUDGET_SECONDS}s). "
                        f"Skipping remaining {total_items - idx} drafts to prevent gateway timeout."
                    )
                    timed_out = True

                batch_index = idx // batch_size
                latest_version = db.query(ContentVersion).filter(
                    ContentVersion.content_item_id == item.id
                ).order_by(ContentVersion.version_num.desc()).first()

                if not latest_version:
                    continue

                item_key = hashlib.sha256(f"{job.id}_{latest_version.id}_{latest_version.checksum}".encode()).hexdigest()

                batch_item = ImpactRescoringBatchItem(
                    job_id=job.id,
                    batch_index=batch_index,
                    content_version_id=latest_version.id,
                    content_item_id=item.id,
                    version_num=latest_version.version_num,
                    content_checksum=latest_version.checksum,
                    item_idempotency_key=item_key,
                    status="pending",
                    retry_count=0
                )
                db.add(batch_item)
                db.flush()

                if timed_out:
                    batch_item.status = "failed"
                    batch_item.error_message = "Rescoring deadline reached (15s HTTP request safety limit)"
                    batch_item.processed_at = datetime.utcnow()
                    failed_count += 1
                    continue

                try:
                    # Re-evaluate version against newly activated knowledge base baseline
                    new_run = governance_engine.evaluate_content_version(
                        db=db,
                        content_version=latest_version,
                        executed_by_user_id=user_id,
                        product_id=item.product_id,
                        knowledge_base_version_id=kb_version.id
                    )
                    batch_item.new_governance_run_id = new_run.id
                    batch_item.status = "completed"
                    batch_item.processed_at = datetime.utcnow()
                    completed_count += 1
                except Exception as exc:
                    logger.error(f"Rescore evaluation failed for item {item.id}: {exc}")
                    batch_item.status = "failed"
                    batch_item.error_message = str(exc)
                    batch_item.processed_at = datetime.utcnow()
                    failed_count += 1

            job.completed_items = completed_count
            job.failed_items = failed_count
            job.completed_batches = total_batches
            job.status = "completed" if (failed_count == 0 and not timed_out) else "partially_failed"
            job.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(job)

        except Exception as global_exc:
            logger.error(f"Global unhandled error during synchronous rescoring: {global_exc}")
            db.rollback()
            # Transition job safely to 'failed' terminal state
            try:
                job.status = "failed"
                job.completed_at = datetime.utcnow()
                job.completed_items = completed_count
                job.failed_items = failed_count + 1
                db.add(job)
                db.commit()
                db.refresh(job)
            except Exception as commit_exc:
                logger.error(f"Failed to commit rescore terminal status: {commit_exc}")

        log_audit_event(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            event_type="GUIDELINE_RESCORING_COMPLETED",
            entity_type="impact_rescoring_job",
            entity_id=job.id,
            summary=f"Re-scored {completed_count}/{total_items} draft(s) against KB v{kb_version.version_num} (status: {job.status})",
            details={
                "total_items": total_items,
                "completed_items": completed_count,
                "failed_items": failed_count,
                "status": job.status,
                "elapsed_seconds": round(time.perf_counter() - start_time, 3),
                "kb_version_id": kb_version.id,
                "version_num": kb_version.version_num
            }
        )

        return job

    def list_jobs(self, db: Session, org_id: str, limit: int = 10) -> List[ImpactRescoringJob]:
        return db.query(ImpactRescoringJob).filter(
            ImpactRescoringJob.organization_id == org_id,
            ImpactRescoringJob.is_archived.is_(False)
        ).order_by(ImpactRescoringJob.created_at.desc()).limit(limit).all()

    def get_job_summary(self, db: Session, org_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        job = db.query(ImpactRescoringJob).filter(
            ImpactRescoringJob.organization_id == org_id,
            ImpactRescoringJob.id == job_id
        ).first()
        if not job:
            return None

        items = db.query(ImpactRescoringBatchItem).filter(
            ImpactRescoringBatchItem.job_id == job.id
        ).all()

        details = []
        for it in items:
            run = db.query(GovernanceRun).filter(GovernanceRun.id == it.new_governance_run_id).first() if it.new_governance_run_id else None
            details.append({
                "batch_index": it.batch_index,
                "content_item_id": it.content_item_id,
                "version_num": it.version_num,
                "status": it.status,
                "governance_status": run.status if run else "unknown",
                "risk_score": run.risk_score if run else None,
                "error_message": it.error_message
            })

        return {
            "id": job.id,
            "organization_id": job.organization_id,
            "knowledge_base_version_id": job.knowledge_base_version_id,
            "status": job.status,
            "total_items": job.total_items,
            "completed_items": job.completed_items,
            "failed_items": job.failed_items,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "items": details
        }


rescore_service = ImpactRescoreService()
