"""link rules to subscriptions

Revision ID: e51c7a9b4d20
Revises: 840840d86603
Create Date: 2026-07-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e51c7a9b4d20'
down_revision: Union[str, None] = '840840d86603'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('rule') as batch_op:
        batch_op.add_column(sa.Column('subscription_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_rule_subscription_id', 'subscription', ['subscription_id'], ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table('rule') as batch_op:
        batch_op.drop_constraint('fk_rule_subscription_id', type_='foreignkey')
        batch_op.drop_column('subscription_id')
