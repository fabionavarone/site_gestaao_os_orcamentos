"""expand CRM customers, contacts, addresses and merge requests"""
import re
from alembic import op
import sqlalchemy as sa

revision="d7a8e2c4b901"
down_revision="c4f23b1a9d02"
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table("customers") as batch:
        batch.add_column(sa.Column("customer_type",sa.String(16),server_default="individual",nullable=False));batch.add_column(sa.Column("legal_name",sa.String(200)));batch.add_column(sa.Column("trade_name",sa.String(200)))
        batch.add_column(sa.Column("state_registration",sa.String(40)));batch.add_column(sa.Column("whatsapp",sa.String(32)));batch.add_column(sa.Column("notes",sa.Text));batch.add_column(sa.Column("status",sa.String(20),server_default="active",nullable=False))
        batch.add_column(sa.Column("tags",sa.JSON,server_default="[]",nullable=False));batch.add_column(sa.Column("branch_id",sa.String(36)));batch.add_column(sa.Column("owner_id",sa.String(36)));batch.add_column(sa.Column("source",sa.String(80)))
        batch.add_column(sa.Column("normalized_document",sa.String(20)));batch.add_column(sa.Column("normalized_email",sa.String(320)));batch.add_column(sa.Column("normalized_phone",sa.String(20)));batch.add_column(sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False))
        batch.create_foreign_key("fk_customers_branch_id_branches","branches",["branch_id"],["id"]);batch.create_foreign_key("fk_customers_owner_id_users","users",["owner_id"],["id"]);batch.create_unique_constraint("uq_customers_company_normalized_document",["company_id","normalized_document"])
        batch.create_check_constraint("ck_customers_customer_type","customer_type IN ('individual','company')");batch.create_check_constraint("ck_customers_customer_status","status IN ('active','inactive','blocked')")
    for column in ("customer_type","status","branch_id","owner_id","normalized_document","normalized_email","normalized_phone"):op.create_index(f"ix_customers_{column}","customers",[column])
    bind=op.get_bind();seen=set()
    for row in bind.execute(sa.text("SELECT id,company_id,document,email,phone FROM customers")):
        document=re.sub(r"\D","",row.document or "") or None;key=(row.company_id,document)
        if document and key in seen:document=None
        if document:seen.add(key)
        bind.execute(sa.text("UPDATE customers SET normalized_document=:document,normalized_email=:email,normalized_phone=:phone WHERE id=:id"),{"id":row.id,"document":document,"email":(row.email or "").strip().lower() or None,"phone":re.sub(r"\D","",row.phone or "") or None})
    op.create_table("customer_contacts",sa.Column("id",sa.String(36),primary_key=True),sa.Column("company_id",sa.String(36),sa.ForeignKey("companies.id"),nullable=False),sa.Column("customer_id",sa.String(36),sa.ForeignKey("customers.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(160),nullable=False),sa.Column("job_title",sa.String(100)),sa.Column("email",sa.String(320)),sa.Column("phone",sa.String(32)),sa.Column("whatsapp",sa.String(32)),sa.Column("preferred_channel",sa.String(20),nullable=False),sa.Column("is_primary",sa.Boolean,nullable=False),sa.Column("receives_notifications",sa.Boolean,nullable=False),sa.Column("active",sa.Boolean,nullable=False),sa.Column("notes",sa.Text),sa.Column("normalized_email",sa.String(320)),sa.Column("normalized_phone",sa.String(20)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False))
    for column in ("company_id","customer_id","normalized_email","normalized_phone"):op.create_index(f"ix_customer_contacts_{column}","customer_contacts",[column])
    op.create_table("customer_addresses",sa.Column("id",sa.String(36),primary_key=True),sa.Column("company_id",sa.String(36),sa.ForeignKey("companies.id"),nullable=False),sa.Column("customer_id",sa.String(36),sa.ForeignKey("customers.id",ondelete="CASCADE"),nullable=False),sa.Column("address_type",sa.String(20),nullable=False),sa.Column("postal_code",sa.String(12)),sa.Column("street",sa.String(200),nullable=False),sa.Column("number",sa.String(30)),sa.Column("complement",sa.String(120)),sa.Column("district",sa.String(120)),sa.Column("city",sa.String(120),nullable=False),sa.Column("state",sa.String(2),nullable=False),sa.Column("country",sa.String(2),nullable=False),sa.Column("reference",sa.String(300)),sa.Column("latitude",sa.String(32)),sa.Column("longitude",sa.String(32)),sa.Column("is_primary",sa.Boolean,nullable=False),sa.Column("active",sa.Boolean,nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False))
    op.create_index("ix_customer_addresses_company_id","customer_addresses",["company_id"]);op.create_index("ix_customer_addresses_customer_id","customer_addresses",["customer_id"])
    op.create_table("customer_merge_requests",sa.Column("id",sa.String(36),primary_key=True),sa.Column("company_id",sa.String(36),sa.ForeignKey("companies.id"),nullable=False),sa.Column("source_customer_id",sa.String(36),sa.ForeignKey("customers.id"),nullable=False),sa.Column("target_customer_id",sa.String(36),sa.ForeignKey("customers.id"),nullable=False),sa.Column("reason",sa.Text,nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("requested_by",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("reviewed_by",sa.String(36),sa.ForeignKey("users.id")),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False),sa.Column("reviewed_at",sa.DateTime(timezone=True)))
    for column in ("company_id","source_customer_id","target_customer_id","status"):op.create_index(f"ix_customer_merge_requests_{column}","customer_merge_requests",[column])

def downgrade():
    for column in ("status","target_customer_id","source_customer_id","company_id"):op.drop_index(f"ix_customer_merge_requests_{column}",table_name="customer_merge_requests")
    op.drop_table("customer_merge_requests");op.drop_index("ix_customer_addresses_customer_id",table_name="customer_addresses");op.drop_index("ix_customer_addresses_company_id",table_name="customer_addresses");op.drop_table("customer_addresses")
    for column in ("normalized_phone","normalized_email","customer_id","company_id"):op.drop_index(f"ix_customer_contacts_{column}",table_name="customer_contacts")
    op.drop_table("customer_contacts")
    for column in ("normalized_phone","normalized_email","normalized_document","owner_id","branch_id","status","customer_type"):op.drop_index(f"ix_customers_{column}",table_name="customers")
    with op.batch_alter_table("customers") as batch:
        for column in ("updated_at","normalized_phone","normalized_email","normalized_document","source","owner_id","branch_id","tags","status","notes","whatsapp","state_registration","trade_name","legal_name","customer_type"):batch.drop_column(column)
