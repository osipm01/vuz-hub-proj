"""fix_role_column_enum

Revision ID: a00000000001
Revises: 1ac195ac70f4
Create Date: 2026-11-07 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a00000000001'
down_revision: Union[str, Sequence[str], None] = '1ac195ac70f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix role column type to use UserRole enum."""
    # PostgreSQL Enum(UserRole) маппится на VARCHAR с CHECK-ограничением
    # Колонка уже существует — просто обновляем тип
    op.alter_column('users', 'role',
                    type_=sa.String(20),
                    existing_type=sa.String,
                    nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('users', 'role',
                    type_=sa.String,
                    existing_type=sa.String(20),
                    nullable=False)
