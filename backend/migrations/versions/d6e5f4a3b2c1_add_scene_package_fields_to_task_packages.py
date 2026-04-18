"""add scene package fields to task packages

Revision ID: d6e5f4a3b2c1
Revises: ac4d92e6b1f1
Create Date: 2026-04-18 21:30:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "d6e5f4a3b2c1"
down_revision = "ac4d92e6b1f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "task_packages" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("task_packages")}
    if "scene_package" not in columns:
        op.add_column("task_packages", sa.Column("scene_package", sa.JSON(), nullable=True))
    if "scene_run" not in columns:
        op.add_column("task_packages", sa.Column("scene_run", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "task_packages" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("task_packages")}
    if "scene_run" in columns:
        op.drop_column("task_packages", "scene_run")
    if "scene_package" in columns:
        op.drop_column("task_packages", "scene_package")
