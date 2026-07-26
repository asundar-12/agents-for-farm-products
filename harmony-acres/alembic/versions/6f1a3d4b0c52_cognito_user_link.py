"""cognito user link

Makes room for Cognito-managed identities on the users table: `hashed_password`
becomes nullable (Cognito users have no local password) and a `cognito_sub`
column links a row to its Cognito identity (the token `sub`).

Revision ID: 6f1a3d4b0c52
Revises: 5e0f2c3a8b41
Create Date: 2026-07-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6f1a3d4b0c52"
down_revision: Union[str, Sequence[str], None] = "5e0f2c3a8b41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=True)
    op.add_column("users", sa.Column("cognito_sub", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_cognito_sub", "users", ["cognito_sub"])
    op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"])


def downgrade() -> None:
    op.drop_index("ix_users_cognito_sub", table_name="users")
    op.drop_constraint("uq_users_cognito_sub", "users", type_="unique")
    op.drop_column("users", "cognito_sub")
    # Restoring NOT NULL requires the rows to have a password; any Cognito-only
    # users would violate it, so this downgrade assumes none exist yet.
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=False)
