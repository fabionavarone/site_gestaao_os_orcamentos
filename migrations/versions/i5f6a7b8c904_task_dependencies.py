"""task dependency link"""
from alembic import op
import sqlalchemy as sa
revision="i5f6a7b8c904"; down_revision="h4e5f6a7b803"; branch_labels=None; depends_on=None
def upgrade():
    with op.batch_alter_table("service_order_tasks") as batch:
        batch.add_column(sa.Column("depends_on_task_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_task_dependency", "service_order_tasks", ["depends_on_task_id"], ["id"])
    op.create_index("ix_service_order_tasks_depends_on_task_id", "service_order_tasks", ["depends_on_task_id"])
def downgrade():
    op.drop_index("ix_service_order_tasks_depends_on_task_id", table_name="service_order_tasks")
    with op.batch_alter_table("service_order_tasks") as batch: batch.drop_constraint("fk_task_dependency", type_="foreignkey"); batch.drop_column("depends_on_task_id")
