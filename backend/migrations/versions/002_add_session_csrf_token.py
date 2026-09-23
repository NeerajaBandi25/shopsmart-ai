"""Add DB-backed csrf_token to sessions.

Revision ID: 002_add_session_csrf_token
Revises: 001_create_users_sessions_tables
Create Date: 2026-09-23

"""

import secrets

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '002_add_session_csrf_token'
down_revision = '001_create_users_sessions_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.add_column('sessions', sa.Column('csrf_token', sa.String(length=64), nullable=True))
    # Backfill existing rows so the NOT NULL constraint holds.
    conn = op.get_bind()
    rows = conn.execute(sa.text('SELECT id FROM sessions WHERE csrf_token IS NULL')).fetchall()
    for (sid,) in rows:
        conn.execute(
            sa.text('UPDATE sessions SET csrf_token = :token WHERE id = :sid'),
            {'token': secrets.token_hex(32), 'sid': str(sid)},
        )
    op.alter_column('sessions', 'csrf_token', existing_type=sa.String(length=64), nullable=False)


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_column('sessions', 'csrf_token')
