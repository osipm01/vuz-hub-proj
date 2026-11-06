"""remove_users_group_id_fk

Revision ID: aab707c5d453
Revises: 1ac195ac70f4
Create Date: 2026-11-06 12:00:00.000000

Убираем ForeignKey constraint из users.group_id,
так как таблица groups находится в study-service.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aab707c5d453'
down_revision: Union[str, Sequence[str], None] = '1ac195ac70f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Удаляем foreign key constraint для users.group_id
    op.drop_constraint('users_group_id_fkey', 'users', type_='foreignkey')
    # Пересоздаём table без constraint (PostgreSQL)
    op.alter_column('users', 'group_id',
                    existing_type=sa.Integer(),
                    nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Восстанавливаем foreign key constraint
    op.create_foreign_key(
        'users_group_id_fkey', 'users', 'groups',
        ['group_id'], ['id'], ondelete='SET NULL'
    )
