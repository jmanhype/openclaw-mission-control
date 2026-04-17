"""add task packages table

Revision ID: ac4d92e6b1f1
Revises: a9b1c2d3e4f7
Create Date: 2026-04-17 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "ac4d92e6b1f1"
down_revision = "a9b1c2d3e4f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "task_packages" in table_names:
        return
    op.create_table(
        "task_packages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("board_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_agent_id", sa.Uuid(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("acceptance_target", sa.Text(), nullable=True),
        sa.Column("workflow_paths", sa.JSON(), nullable=True),
        sa.Column("input_paths", sa.JSON(), nullable=True),
        sa.Column("reference_paths", sa.JSON(), nullable=True),
        sa.Column("keyframe_paths", sa.JSON(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("intermediate_outputs", sa.JSON(), nullable=True),
        sa.Column("output_paths", sa.JSON(), nullable=True),
        sa.Column("benchmark_outputs", sa.JSON(), nullable=True),
        sa.Column("qc_checklist", sa.JSON(), nullable=True),
        sa.Column("execution_id", sa.Text(), nullable=True),
        sa.Column("qc_verdict", sa.Text(), nullable=True),
        sa.Column("next_step", sa.Text(), nullable=True),
        sa.Column("blocker", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["updated_by_agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_task_packages_task_id"),
    )
    op.create_index(op.f("ix_task_packages_board_id"), "task_packages", ["board_id"], unique=False)
    op.create_index(op.f("ix_task_packages_task_id"), "task_packages", ["task_id"], unique=False)
    op.create_index(
        op.f("ix_task_packages_updated_by_agent_id"),
        "task_packages",
        ["updated_by_agent_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "task_packages" not in table_names:
        return
    op.drop_index(op.f("ix_task_packages_updated_by_agent_id"), table_name="task_packages")
    op.drop_index(op.f("ix_task_packages_task_id"), table_name="task_packages")
    op.drop_index(op.f("ix_task_packages_board_id"), table_name="task_packages")
    op.drop_table("task_packages")
