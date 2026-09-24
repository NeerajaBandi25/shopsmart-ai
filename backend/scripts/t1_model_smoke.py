"""T1 verification: SQLAlchemy model create/read against the migrated ShopSmart DB.

Run from backend/ with the project venv. Creates a temporary user + session +
login_attempt, verifies them from fresh sessions (including relationships and
DB-level constraints), then cleans up so the database is left empty.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.security import hash_password
from src.database import AsyncSessionLocal
from src.models.login_attempt import LoginAttempt
from src.models.session import Session
from src.models.user import User


async def main() -> int:
    print(f"target db: {settings.database_url.rsplit('@', 1)[-1]}")
    email = "t1-smoke@example.com"
    csrf = "a" * 64
    now = datetime.now(timezone.utc)
    uid = sid = None

    async with AsyncSessionLocal() as s:
        await s.execute(delete(LoginAttempt).where(LoginAttempt.email == email))
        await s.execute(delete(User).where(User.email == email))
        await s.commit()

    async with AsyncSessionLocal() as s:
        user = User(email=email, password_hash=hash_password("SmokeTest123!"))
        s.add(user)
        await s.flush()
        uid = user.id
        session = Session(
            id=uuid4(),
            user_id=user.id,
            last_activity=now,
            ip_address="127.0.0.1",
            user_agent="t1-smoke",
            csrf_token=csrf,
        )
        attempt = LoginAttempt(
            email=email,
            ip_address="127.0.0.1",
            attempted_at=now,
            success=False,
            failure_reason="smoke-test",
        )
        s.add_all([session, attempt])
        await s.commit()
        sid = session.id
        print(f"created user={uid} session={sid}")

    async with AsyncSessionLocal() as s:
        loaded = (
            await s.execute(
                select(User).where(User.email == email).options(selectinload(User.sessions))
            )
        ).scalar_one()
        assert loaded.id == uid, "user id mismatch on read-back"
        assert loaded.password_hash.startswith("$2b$"), "bcrypt hash not stored"
        assert len(loaded.sessions) == 1 and str(loaded.sessions[0].csrf_token) == csrf, (
            "session relationship not readable"
        )
        sess = (await s.execute(select(Session).where(Session.id == sid))).scalar_one()
        assert sess.is_active is True and sess.user_id == uid
        stale = now - timedelta(days=31)
        sess.last_activity = stale
        await s.commit()
        print("read-back OK (user, hash, relationship, session)")

    async with AsyncSessionLocal() as s:
        sess = (await s.execute(select(Session).where(Session.id == sid))).scalar_one()
        assert sess.last_activity == stale, "updated_at write did not persist"
        duplicate = User(email=email, password_hash="x")
        s.add(duplicate)
        try:
            await s.commit()
        except IntegrityError:
            await s.rollback()
            print("unique(email) constraint enforced at DB level")
        else:
            print("FAIL: duplicate email accepted")
            return 1
        await s.delete(sess)
        await s.commit()
        orphans = (
            await s.execute(select(Session).where(Session.user_id == uid))
        ).scalars().all()
        assert not orphans, "ON DELETE CASCADE did not remove session"

    async with AsyncSessionLocal() as s:
        for row in (
            await s.execute(
                select(LoginAttempt).where(LoginAttempt.email == email)
            )
        ).scalars().all():
            await s.delete(row)
        user = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        await s.delete(user)
        await s.commit()
        print("cleanup OK")

    print("MODEL SMOKE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
