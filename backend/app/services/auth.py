import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
from threading import Lock
import jwt
import bcrypt
from sqlalchemy.orm import Session
from app.config import settings
from app.models.organization import RevokedToken

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8")[:72], salt)
    return hashed.decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if "jti" not in to_encode:
        to_encode["jti"] = uuid.uuid4().hex

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str, verify_exp: bool = True) -> Optional[dict]:
    try:
        options = {"verify_exp": verify_exp}
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options=options)
        return payload
    except jwt.PyJWTError:
        return None

def is_token_revoked(db: Session, jti: str) -> bool:
    """
    Checks if a token's unique jti exists in the revoked_tokens store.
    """
    if not jti:
        return False
    return db.query(RevokedToken).filter(RevokedToken.jti == jti).first() is not None

def revoke_token(db: Session, token: str, reason: str = "logout") -> bool:
    """
    Decodes the token to obtain its jti and user_id, then records it as revoked.
    """
    payload = decode_access_token(token, verify_exp=False)
    if not payload:
        return False

    jti = payload.get("jti")
    user_id = payload.get("sub")
    exp_ts = payload.get("exp")

    if not jti or not user_id:
        return False

    if exp_ts:
        expires_at = datetime.utcfromtimestamp(exp_ts)
    else:
        expires_at = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # Check if already revoked
    existing = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if existing:
        return True

    revoked = RevokedToken(
        id=str(uuid.uuid4()),
        jti=jti,
        user_id=user_id,
        revoked_at=datetime.utcnow(),
        expires_at=expires_at,
        reason=reason
    )
    db.add(revoked)
    db.commit()
    return True


class LoginRateLimiter:
    """
    In-memory rate limiter to protect authentication endpoints from automated
    credential stuffing and brute-force attempts.
    """
    def __init__(self, max_attempts: int = 5, lockout_seconds: int = 300):
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self._failures: Dict[str, List[float]] = {}
        self._lock = Lock()

    def _clean_old_failures(self, key: str, now: float):
        if key in self._failures:
            threshold = now - self.lockout_seconds
            self._failures[key] = [t for t in self._failures[key] if t > threshold]
            if not self._failures[key]:
                del self._failures[key]

    def is_locked_out(self, identifier: str) -> Tuple[bool, int]:
        """
        Returns (is_locked_out, remaining_seconds_until_unlock).
        """
        key = identifier.strip().lower()
        now = time.time()
        with self._lock:
            self._clean_old_failures(key, now)
            attempts = self._failures.get(key, [])
            if len(attempts) >= self.max_attempts:
                oldest_in_window = attempts[0]
                remaining = int(self.lockout_seconds - (now - oldest_in_window))
                return True, max(1, remaining)
            return False, 0

    def record_failure(self, identifier: str) -> Tuple[bool, int]:
        """
        Records a failed attempt.
        Returns (is_locked_out, remaining_seconds_or_attempts_left).
        """
        key = identifier.strip().lower()
        now = time.time()
        with self._lock:
            self._clean_old_failures(key, now)
            if key not in self._failures:
                self._failures[key] = []
            self._failures[key].append(now)

            if len(self._failures[key]) >= self.max_attempts:
                oldest_in_window = self._failures[key][0]
                remaining = int(self.lockout_seconds - (now - oldest_in_window))
                return True, max(1, remaining)
            else:
                remaining_attempts = self.max_attempts - len(self._failures[key])
                return False, remaining_attempts

    def record_success(self, identifier: str):
        key = identifier.strip().lower()
        with self._lock:
            if key in self._failures:
                del self._failures[key]

    def reset(self):
        with self._lock:
            self._failures.clear()


login_rate_limiter = LoginRateLimiter(
    max_attempts=settings.RATE_LIMIT_FAILED_LOGINS,
    lockout_seconds=settings.RATE_LIMIT_LOCKOUT_SECONDS
)
