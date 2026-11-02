"""
Instance-Local Concurrency Limiter for Heavy Image Governance

Limits concurrent execution of heavy, memory-intensive visual governance and OCR
operations to protect memory-constrained runtimes (e.g. Render 512 MB free tier).

Architectural Notes & Limitations:
- Scope: Instance-local (in-process). Coordinates all request threads on the current
  FastAPI/Uvicorn container.
- Horizontal Scaling Limitation: If scaled horizontally across multiple distinct
  container instances, coordination across nodes would require an external distributed
  lock (e.g. Redis). For single-container deployments (such as Render free tier),
  in-process thread coordination provides deterministic protection with zero external
  dependencies or latency overhead.
"""

import threading
import time
import contextlib
import logging
from typing import Optional
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class HeavyImageGovernanceLimiter:
    """
    Coordinates execution of memory-heavy image governance requests.
    Enforces:
    - Maximum 1 active heavy operation at any time.
    - Bounded waiting queue (default: 1 waiting request; excess rejected).
    - Queue acquisition timeout (default: 25.0 seconds).
    - Fast 429 Too Many Requests response with Retry-After header when queue is full.
    - 503 Service Unavailable with Retry-After header on queue wait timeout.
    - Robust release in finally block to prevent orphaned reservations.
    """
    def __init__(
        self,
        max_active: int = 1,
        max_waiting: int = 1,
        wait_timeout: float = 25.0
    ):
        self.max_active = max_active
        self.max_waiting = max_waiting
        self.wait_timeout = wait_timeout
        self.active_count = 0
        self.waiting_count = 0
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

    def acquire(self) -> None:
        """
        Acquires an execution slot or enters the bounded waiting queue.
        Raises HTTPException(429) if the waiting queue is at capacity.
        Raises HTTPException(503) if the queue wait exceeds wait_timeout.
        """
        with self._condition:
            # 1. Slot available immediately
            if self.active_count < self.max_active:
                self.active_count += 1
                logger.info(
                    f"[ConcurrencyLimiter] Slot acquired immediately. Active: {self.active_count}, Waiting: {self.waiting_count}"
                )
                return

            # 2. Check bounded queue capacity
            if self.waiting_count >= self.max_waiting:
                logger.warning(
                    f"[ConcurrencyLimiter] Queue full (Active: {self.active_count}, Waiting: {self.waiting_count}). Rejecting request with 429."
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Heavy image governance is currently processing another creative and the queue is full. "
                        "Please retry in 10 seconds."
                    ),
                    headers={"Retry-After": "10"}
                )

            # 3. Enter bounded queue and wait for available slot
            self.waiting_count += 1
            deadline = time.time() + self.wait_timeout
            logger.info(
                f"[ConcurrencyLimiter] Queued for slot. Active: {self.active_count}, Waiting: {self.waiting_count}"
            )

            try:
                while self.active_count >= self.max_active:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        logger.warning(
                            f"[ConcurrencyLimiter] Queue wait timed out after {self.wait_timeout}s. Raising 503."
                        )
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Image governance queue wait timed out. Server is under high load; please retry shortly.",
                            headers={"Retry-After": "10"}
                        )
                    self._condition.wait(timeout=remaining)

                # Slot acquired after wait
                self.active_count += 1
                logger.info(
                    f"[ConcurrencyLimiter] Slot acquired after wait. Active: {self.active_count}, Waiting: {self.waiting_count - 1}"
                )
            finally:
                self.waiting_count -= 1

    def release(self) -> None:
        """Releases the slot and notifies the next waiting request thread."""
        with self._condition:
            if self.active_count > 0:
                self.active_count -= 1
            logger.info(
                f"[ConcurrencyLimiter] Slot released. Active: {self.active_count}, Waiting: {self.waiting_count}"
            )
            self._condition.notify()

    @contextlib.contextmanager
    def slot(self):
        """Context manager guaranteeing safe acquisition and release."""
        self.acquire()
        try:
            yield
        finally:
            self.release()

    def get_status(self) -> dict:
        """Returns current operational metrics."""
        with self._condition:
            return {
                "max_active": self.max_active,
                "max_waiting": self.max_waiting,
                "active_count": self.active_count,
                "waiting_count": self.waiting_count,
                "wait_timeout": self.wait_timeout
            }


# Singleton limiter instance for heavy visual governance across the application
image_governance_limiter = HeavyImageGovernanceLimiter(
    max_active=1,
    max_waiting=1,
    wait_timeout=25.0
)

