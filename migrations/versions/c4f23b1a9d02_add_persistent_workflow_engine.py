"""add persistent workflow engine and migrate service orders

Revision ID: c4f23b1a9d02
Revises: 9c30f4a612ef
"""
from datetime import UTC, datetime
import uuid

from alembic import op
import sqlalchemy as sa

revision = "c4f23b1a9d02"
down_revision = "9c30f4a612ef"
branch_labels = None
depends_on = None

STATES = [
    ("draft", "Rascunho", "intake", True, False, False),
    ("awaiting_receipt", "Aguardando recebimento", "intake", False, False, True),
    ("received", "Recebido", "intake", False, False, True),
    ("triage", "Triagem", "triage", False, False, True),
    ("diagnosis", "Diagnóstico", "technical", False, False, True),
    ("awaiting_budget", "Aguardando orçamento", "waiting", False, False, True),
    ("awaiting_customer_approval", "Aguardando aprovação", "waiting", False, False, True),
    ("approved", "Aprovado", "technical", False, False, True),
    ("rejected", "Rejeitado", "closed", False, False, True),
    ("awaiting_parts", "Aguardando peças", "waiting", False, False, True),
    ("repair_in_progress", "Reparo em andamento", "technical", False, False, True),
    ("quality_test", "Teste de qualidade", "technical", False, False, True),
    ("technical_hold", "Pausa técnica", "waiting", False, False, False),
    ("customer_hold", "Aguardando cliente", "waiting", False, False, True),
    ("financial_hold", "Pausa financeira", "waiting", False, False, False),
    ("ready_for_delivery", "Disponível para entrega", "delivery", False, False, True),
    ("delivered", "Entregue", "delivery", False, False, True),
    ("closed", "Encerrado", "closed", False, True, True),
    ("cancelled", "Cancelado", "cancelled", False, True, True),
    ("warranty_return", "Retorno em garantia", "warranty", False, False, True),
    ("no_repair_condition", "Sem condição de reparo", "closed", False, False, True),
]

TRANSITIONS = {
    "draft": ("awaiting_receipt", "received", "cancelled"),
    "awaiting_receipt": ("received", "cancelled"),
    "received": ("triage", "cancelled"),
    "triage": ("diagnosis", "technical_hold", "customer_hold"),
    "diagnosis": ("awaiting_budget", "no_repair_condition", "technical_hold"),
    "awaiting_budget": ("awaiting_customer_approval",),
    "awaiting_customer_approval": ("approved", "rejected", "customer_hold"),
    "approved": ("awaiting_parts", "repair_in_progress"),
    "awaiting_parts": ("repair_in_progress", "technical_hold"),
    "repair_in_progress": ("quality_test", "technical_hold"),
    "quality_test": ("ready_for_delivery", "repair_in_progress"),
    "ready_for_delivery": ("delivered", "financial_hold"),
    "delivered": ("closed", "warranty_return"),
    "rejected": ("closed",),
    "no_repair_condition": ("closed",),
    "technical_hold": ("triage", "diagnosis", "repair_in_progress"),
    "customer_hold": ("triage", "awaiting_customer_approval"),
    "financial_hold": ("ready_for_delivery", "closed"),
    "warranty_return": ("triage",),
}

def _id():
    return str(uuid.uuid4())

def upgrade():
    op.create_table("service_order_sequences",
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), primary_key=True),
        sa.Column("next_number", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.create_table("workflow_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text), sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("company_id", "code", name="uq_workflow_definition_company_code"),
        sa.CheckConstraint("status IN ('draft','active','inactive','archived')", name="ck_workflow_definition_status"))
    op.create_index("ix_workflow_definitions_company_id", "workflow_definitions", ["company_id"])
    op.create_index("ix_workflow_definitions_status", "workflow_definitions", ["status"])
    op.create_table("workflow_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_definition_id", sa.String(36), sa.ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("description", sa.Text), sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("published_by", sa.String(36), sa.ForeignKey("users.id")), sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("workflow_definition_id", "version_number", name="uq_workflow_version_number"),
        sa.CheckConstraint("status IN ('draft','published','superseded','archived')", name="ck_workflow_version_status"))
    op.create_index("ix_workflow_versions_definition", "workflow_versions", ["workflow_definition_id"])
    op.create_index("ix_workflow_versions_status", "workflow_versions", ["status"])
    op.create_table("workflow_states",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("workflow_version_id", sa.String(36), sa.ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.Text),
        sa.Column("category", sa.String(30), nullable=False), sa.Column("is_initial", sa.Boolean, nullable=False),
        sa.Column("is_terminal", sa.Boolean, nullable=False), sa.Column("is_public", sa.Boolean, nullable=False),
        sa.Column("position", sa.Integer, nullable=False), sa.Column("metadata", sa.JSON, nullable=False),
        sa.UniqueConstraint("workflow_version_id", "code", name="uq_workflow_state_code"))
    op.create_index("ix_workflow_states_version", "workflow_states", ["workflow_version_id"])
    op.create_table("workflow_transitions",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("workflow_version_id", sa.String(36), sa.ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(160), nullable=False),
        sa.Column("from_state_id", sa.String(36), sa.ForeignKey("workflow_states.id"), nullable=False),
        sa.Column("to_state_id", sa.String(36), sa.ForeignKey("workflow_states.id"), nullable=False),
        sa.Column("required_permission", sa.String(100)), sa.Column("requires_reason", sa.Boolean, nullable=False),
        sa.Column("requires_assignment", sa.Boolean, nullable=False), sa.Column("requires_checklist_completion", sa.Boolean, nullable=False),
        sa.Column("requires_diagnosis", sa.Boolean, nullable=False), sa.Column("requires_customer_notification", sa.Boolean, nullable=False),
        sa.Column("conditions", sa.JSON, nullable=False), sa.Column("actions", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False), sa.Column("position", sa.Integer, nullable=False),
        sa.UniqueConstraint("workflow_version_id", "code", name="uq_workflow_transition_code"),
        sa.CheckConstraint("from_state_id <> to_state_id", name="ck_workflow_transition_distinct_states"))
    for name, column in (("version", "workflow_version_id"), ("from_state", "from_state_id"), ("to_state", "to_state_id")):
        op.create_index(f"ix_workflow_transitions_{name}", "workflow_transitions", [column])
    op.create_table("workflow_instances",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("workflow_version_id", sa.String(36), sa.ForeignKey("workflow_versions.id"), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False), sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("current_state_id", sa.String(36), sa.ForeignKey("workflow_states.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("metadata", sa.JSON, nullable=False),
        sa.UniqueConstraint("company_id", "entity_type", "entity_id", name="uq_workflow_instance_entity"),
        sa.CheckConstraint("status IN ('running','paused','completed','cancelled')", name="ck_workflow_instance_status"))
    for column in ("company_id", "workflow_version_id", "entity_id", "current_state_id", "status"):
        op.create_index(f"ix_workflow_instances_{column}", "workflow_instances", [column])
    op.create_table("workflow_execution_events",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("workflow_instance_id", sa.String(36), sa.ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transition_id", sa.String(36), sa.ForeignKey("workflow_transitions.id")), sa.Column("from_state_id", sa.String(36), sa.ForeignKey("workflow_states.id")),
        sa.Column("to_state_id", sa.String(36), sa.ForeignKey("workflow_states.id"), nullable=False), sa.Column("performed_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("reason", sa.Text), sa.Column("context", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.create_index("ix_workflow_execution_events_instance", "workflow_execution_events", ["workflow_instance_id"])
    op.create_index("ix_workflow_execution_events_transition", "workflow_execution_events", ["transition_id"])
    op.create_table("workflow_action_executions",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("workflow_execution_event_id", sa.String(36), sa.ForeignKey("workflow_execution_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(80), nullable=False), sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False), sa.Column("result", sa.JSON, nullable=False), sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_workflow_action_executions_event", "workflow_action_executions", ["workflow_execution_event_id"])
    op.create_index("ix_workflow_action_executions_status", "workflow_action_executions", ["status"])
    with op.batch_alter_table("service_orders") as batch:
        batch.add_column(sa.Column("workflow_instance_id", sa.String(36)))
        batch.create_foreign_key("fk_service_orders_workflow_instance", "workflow_instances", ["workflow_instance_id"], ["id"])
        batch.create_index("ix_service_orders_workflow_instance_id", ["workflow_instance_id"])
    _seed_and_migrate()

def _seed_and_migrate():
    bind = op.get_bind(); now = datetime.now(UTC)
    company_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM companies"))]
    for company_id in company_ids:
        next_number = bind.execute(sa.text("SELECT COALESCE(MAX(number),0)+1 FROM service_orders WHERE company_id=:company"), {"company":company_id}).scalar_one()
        bind.execute(sa.text("INSERT INTO service_order_sequences (company_id,next_number,updated_at) VALUES (:company,:next,:now)"), {"company":company_id,"next":next_number,"now":now})
        definition_id, version_id = _id(), _id()
        bind.execute(sa.text("INSERT INTO workflow_definitions (id,company_id,code,name,description,entity_type,status,created_at,updated_at) VALUES (:id,:company,'service_order_default','Fluxo padrão de OS','Fluxo migrado da máquina de estados original','service_order','active',:now,:now)"), {"id":definition_id,"company":company_id,"now":now})
        bind.execute(sa.text("INSERT INTO workflow_versions (id,workflow_definition_id,version_number,status,description,created_at,published_at) VALUES (:id,:definition,1,'published','Versão inicial preservando os estados existentes',:now,:now)"), {"id":version_id,"definition":definition_id,"now":now})
        state_ids = {}
        for position, (code, name, category, initial, terminal, public) in enumerate(STATES):
            state_ids[code] = _id()
            bind.execute(sa.text("INSERT INTO workflow_states (id,workflow_version_id,code,name,category,is_initial,is_terminal,is_public,position,metadata) VALUES (:id,:version,:code,:name,:category,:initial,:terminal,:public,:position,:metadata)"), {"id":state_ids[code],"version":version_id,"code":code,"name":name,"category":category,"initial":initial,"terminal":terminal,"public":public,"position":position,"metadata":"{}"})
        for origin, destinations in TRANSITIONS.items():
            for position, destination in enumerate(destinations):
                transition_id = _id(); code = f"{origin}_to_{destination}"
                bind.execute(sa.text("INSERT INTO workflow_transitions (id,workflow_version_id,code,name,from_state_id,to_state_id,required_permission,requires_reason,requires_assignment,requires_checklist_completion,requires_diagnosis,requires_customer_notification,conditions,actions,active,position) VALUES (:id,:version,:code,:name,:from_id,:to_id,'service_order.transition',:reason,0,:checklist,:diagnosis,:notify,:conditions,:actions,1,:position)"), {"id":transition_id,"version":version_id,"code":code,"name":f"{origin} → {destination}","from_id":state_ids[origin],"to_id":state_ids[destination],"reason":destination in {"cancelled","technical_hold","customer_hold","closed"},"checklist":destination in {"ready_for_delivery","closed"},"diagnosis":destination in {"awaiting_budget","ready_for_delivery"},"notify":destination in {"received","triage","diagnosis","ready_for_delivery","delivered","closed","warranty_return"},"conditions":"{}","actions":"[]","position":position})
        orders = list(bind.execute(sa.text("SELECT id,status,created_at FROM service_orders WHERE company_id=:company"), {"company":company_id}))
        for order_id, status, created_at in orders:
            mapped = status if status in state_ids else "draft"; instance_id = _id()
            terminal = mapped in {"closed","cancelled"}
            bind.execute(sa.text("INSERT INTO workflow_instances (id,company_id,workflow_version_id,entity_type,entity_id,current_state_id,status,started_at,completed_at,metadata) VALUES (:id,:company,:version,'service_order',:entity,:state,:status,:started,:completed,:metadata)"), {"id":instance_id,"company":company_id,"version":version_id,"entity":order_id,"state":state_ids[mapped],"status":"completed" if terminal else "running","started":created_at or now,"completed":now if terminal else None,"metadata":"{}"})
            bind.execute(sa.text("INSERT INTO workflow_execution_events (id,workflow_instance_id,to_state_id,reason,context,created_at) VALUES (:id,:instance,:state,'Migração idempotente do estado legado',:context,:created)"), {"id":_id(),"instance":instance_id,"state":state_ids[mapped],"context":"{}","created":now})
            bind.execute(sa.text("UPDATE service_orders SET workflow_instance_id=:instance WHERE id=:order"), {"instance":instance_id,"order":order_id})

def downgrade():
    with op.batch_alter_table("service_orders") as batch:
        batch.drop_index("ix_service_orders_workflow_instance_id")
        batch.drop_constraint("fk_service_orders_workflow_instance", type_="foreignkey")
        batch.drop_column("workflow_instance_id")
    op.drop_index("ix_workflow_action_executions_status", table_name="workflow_action_executions")
    op.drop_index("ix_workflow_action_executions_event", table_name="workflow_action_executions")
    op.drop_table("workflow_action_executions")
    op.drop_index("ix_workflow_execution_events_transition", table_name="workflow_execution_events")
    op.drop_index("ix_workflow_execution_events_instance", table_name="workflow_execution_events")
    op.drop_table("workflow_execution_events")
    for column in ("status", "current_state_id", "entity_id", "workflow_version_id", "company_id"):
        op.drop_index(f"ix_workflow_instances_{column}", table_name="workflow_instances")
    op.drop_table("workflow_instances")
    for name in ("to_state", "from_state", "version"):
        op.drop_index(f"ix_workflow_transitions_{name}", table_name="workflow_transitions")
    op.drop_table("workflow_transitions")
    op.drop_index("ix_workflow_states_version", table_name="workflow_states")
    op.drop_table("workflow_states")
    op.drop_index("ix_workflow_versions_status", table_name="workflow_versions")
    op.drop_index("ix_workflow_versions_definition", table_name="workflow_versions")
    op.drop_table("workflow_versions")
    op.drop_index("ix_workflow_definitions_status", table_name="workflow_definitions")
    op.drop_index("ix_workflow_definitions_company_id", table_name="workflow_definitions")
    op.drop_table("workflow_definitions")
    op.drop_table("service_order_sequences")
