"""equipment catalogs, complete assets and accessories"""
from alembic import op
import sqlalchemy as sa

revision = "e1b6c7d8f902"
down_revision = "d7a8e2c4b901"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("equipment_categories", sa.Column("id",sa.String(36),primary_key=True), sa.Column("company_id",sa.String(36),sa.ForeignKey("companies.id"),nullable=False), sa.Column("parent_id",sa.String(36),sa.ForeignKey("equipment_categories.id")), sa.Column("name",sa.String(120),nullable=False), sa.Column("active",sa.Boolean,nullable=False), sa.UniqueConstraint("company_id","name"))
    op.create_index("ix_equipment_categories_company_id","equipment_categories",["company_id"])
    op.create_table("equipment_brands", sa.Column("id",sa.String(36),primary_key=True), sa.Column("company_id",sa.String(36),sa.ForeignKey("companies.id"),nullable=False), sa.Column("name",sa.String(120),nullable=False), sa.Column("active",sa.Boolean,nullable=False), sa.UniqueConstraint("company_id","name"))
    op.create_index("ix_equipment_brands_company_id","equipment_brands",["company_id"])
    op.create_table("equipment_models", sa.Column("id",sa.String(36),primary_key=True), sa.Column("company_id",sa.String(36),sa.ForeignKey("companies.id"),nullable=False), sa.Column("category_id",sa.String(36),sa.ForeignKey("equipment_categories.id")), sa.Column("brand_id",sa.String(36),sa.ForeignKey("equipment_brands.id")), sa.Column("name",sa.String(120),nullable=False), sa.Column("specifications",sa.JSON,nullable=False), sa.Column("active",sa.Boolean,nullable=False), sa.UniqueConstraint("company_id","brand_id","name"))
    for column in ("company_id","category_id","brand_id"): op.create_index(f"ix_equipment_models_{column}","equipment_models",[column])
    op.create_table("equipment_accessories", sa.Column("id",sa.String(36),primary_key=True), sa.Column("company_id",sa.String(36),sa.ForeignKey("companies.id"),nullable=False), sa.Column("equipment_id",sa.String(36),sa.ForeignKey("equipment.id",ondelete="CASCADE"),nullable=False), sa.Column("description",sa.String(200),nullable=False), sa.Column("quantity",sa.Integer,nullable=False), sa.Column("condition",sa.String(100)), sa.Column("observation",sa.Text), sa.Column("returned",sa.Boolean,nullable=False), sa.Column("returned_at",sa.DateTime(timezone=True)))
    for column in ("company_id","equipment_id"): op.create_index(f"ix_equipment_accessories_{column}","equipment_accessories",[column])
    with op.batch_alter_table("equipment") as batch:
        for name, column, typ in (("contact_id","contact_id",sa.String(36)),("address_id","address_id",sa.String(36)),("category_id","category_id",sa.String(36)),("brand_id","brand_id",sa.String(36)),("model_id","model_id",sa.String(36)),("asset_number","asset_number",sa.String(100)),("installation_date","installation_date",sa.DateTime(timezone=True)),("purchase_date","purchase_date",sa.DateTime(timezone=True)),("warranty_until","warranty_until",sa.DateTime(timezone=True)),("status","status",sa.String(24)),("location","location",sa.String(200)),("technical_data","technical_data",sa.JSON),("notes","notes",sa.Text)):
            batch.add_column(sa.Column(column,typ,server_default="active" if column=="status" else ("{}" if column=="technical_data" else None),nullable=False if column in {"status","technical_data"} else True))
        batch.create_foreign_key("fk_equipment_contact_id_contacts","customer_contacts",["contact_id"],["id"]); batch.create_foreign_key("fk_equipment_address_id_addresses","customer_addresses",["address_id"],["id"]); batch.create_foreign_key("fk_equipment_category_id_categories","equipment_categories",["category_id"],["id"]); batch.create_foreign_key("fk_equipment_brand_id_brands","equipment_brands",["brand_id"],["id"]); batch.create_foreign_key("fk_equipment_model_id_models","equipment_models",["model_id"],["id"])
    for column in ("contact_id","address_id","category_id","brand_id","model_id","asset_number","status"): op.create_index(f"ix_equipment_{column}","equipment",[column])

def downgrade():
    for column in ("contact_id","address_id","category_id","brand_id","model_id","asset_number","status"): op.drop_index(f"ix_equipment_{column}",table_name="equipment")
    with op.batch_alter_table("equipment") as batch:
        for name in ("fk_equipment_contact_id_contacts","fk_equipment_address_id_addresses","fk_equipment_category_id_categories","fk_equipment_brand_id_brands","fk_equipment_model_id_models"):
            try: batch.drop_constraint(name,type_="foreignkey")
            except Exception: pass
        for column in ("notes","technical_data","location","status","warranty_until","purchase_date","installation_date","asset_number","model_id","brand_id","category_id","address_id","contact_id"): batch.drop_column(column)
    for column in ("company_id","equipment_id"): op.drop_index(f"ix_equipment_accessories_{column}",table_name="equipment_accessories")
    op.drop_table("equipment_accessories")
    for column in ("company_id","category_id","brand_id"): op.drop_index(f"ix_equipment_models_{column}",table_name="equipment_models")
    op.drop_table("equipment_models"); op.drop_index("ix_equipment_brands_company_id",table_name="equipment_brands"); op.drop_table("equipment_brands"); op.drop_index("ix_equipment_categories_company_id",table_name="equipment_categories"); op.drop_table("equipment_categories")
