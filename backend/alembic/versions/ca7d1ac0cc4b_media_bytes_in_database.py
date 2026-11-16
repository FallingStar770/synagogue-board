"""media bytes in database

Revision ID: ca7d1ac0cc4b
Revises: 1d7aa1ab498a
Create Date: 2026-11-16 11:39:33.598805
"""
from alembic import op
import sqlalchemy as sa


revision = 'ca7d1ac0cc4b'
down_revision = '1d7aa1ab498a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("media_assets", sa.Column("data", sa.LargeBinary(), nullable=True))
    # move images saved on disk by v1.0 into the database (keeps working where the disk is ephemeral)
    from pathlib import Path
    from app.config import get_settings
    media_dir = Path(get_settings().media_dir)
    conn = op.get_bind()
    for asset_id, key in conn.execute(sa.text("select id, storage_key from media_assets where data is null")).all():
        f = media_dir / key
        if f.exists():
            conn.execute(sa.text("update media_assets set data = :d where id = :i"), {"d": f.read_bytes(), "i": asset_id})


def downgrade() -> None:
    op.drop_column("media_assets", "data")
