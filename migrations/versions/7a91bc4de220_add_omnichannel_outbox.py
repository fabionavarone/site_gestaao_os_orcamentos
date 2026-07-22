"""add canonical omnichannel persistence and outbox

Revision ID: 7a91bc4de220
Revises: 441a00f1e659
"""
from alembic import op
import sqlalchemy as sa

revision = "7a91bc4de220"
down_revision = "441a00f1e659"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("channels", sa.Column("id", sa.String(36), primary_key=True), sa.Column("company_id", sa.String(36), nullable=False), sa.Column("kind", sa.String(32), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("active", sa.Boolean, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.ForeignKeyConstraint(["company_id"], ["companies.id"]), sa.UniqueConstraint("company_id", "kind", "name"))
    op.create_index("ix_channels_company_id", "channels", ["company_id"])
    op.create_index("ix_channels_kind", "channels", ["kind"])
    op.create_table("channel_bots", sa.Column("id", sa.String(36), primary_key=True), sa.Column("company_id", sa.String(36), nullable=False), sa.Column("channel_id", sa.String(36), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("active", sa.Boolean, nullable=False), sa.Column("token_ciphertext", sa.Text), sa.Column("webhook_secret_hash", sa.String(64)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.ForeignKeyConstraint(["company_id"], ["companies.id"]), sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]))
    op.create_index("ix_channel_bots_company_id", "channel_bots", ["company_id"])
    op.create_index("ix_channel_bots_channel_id", "channel_bots", ["channel_id"])
    op.create_table("external_identities", sa.Column("id", sa.String(36), primary_key=True), sa.Column("company_id", sa.String(36), nullable=False), sa.Column("channel_id", sa.String(36), nullable=False), sa.Column("external_id", sa.String(160), nullable=False), sa.Column("display_name", sa.String(160)), sa.Column("user_id", sa.String(36)), sa.Column("customer_id", sa.String(36)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.ForeignKeyConstraint(["company_id"], ["companies.id"]), sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]), sa.ForeignKeyConstraint(["user_id"], ["users.id"]), sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]), sa.UniqueConstraint("channel_id", "external_id"))
    op.create_index("ix_external_identities_company_id", "external_identities", ["company_id"])
    op.create_index("ix_external_identities_channel_id", "external_identities", ["channel_id"])
    op.create_table("conversation_participants", sa.Column("conversation_id", sa.String(36), nullable=False), sa.Column("external_identity_id", sa.String(36), nullable=False), sa.Column("user_id", sa.String(36), nullable=True), sa.Column("role", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["external_identity_id"], ["external_identities.id"]), sa.ForeignKeyConstraint(["user_id"], ["users.id"]), sa.PrimaryKeyConstraint("conversation_id", "external_identity_id"))
    op.create_table("external_events", sa.Column("id", sa.String(36), primary_key=True), sa.Column("company_id", sa.String(36), nullable=False), sa.Column("channel_id", sa.String(36), nullable=False), sa.Column("bot_id", sa.String(36)), sa.Column("external_event_id", sa.String(160), nullable=False), sa.Column("idempotency_key", sa.String(128), nullable=False), sa.Column("payload", sa.JSON, nullable=False), sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("processed_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["company_id"], ["companies.id"]), sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]), sa.ForeignKeyConstraint(["bot_id"], ["channel_bots.id"]), sa.UniqueConstraint("channel_id", "external_event_id"), sa.UniqueConstraint("idempotency_key"))
    op.create_index("ix_external_events_company_id", "external_events", ["company_id"])
    op.create_index("ix_external_events_channel_id", "external_events", ["channel_id"])
    op.create_index("ix_external_events_bot_id", "external_events", ["bot_id"])
    op.create_table("outbox_events", sa.Column("id", sa.String(36), primary_key=True), sa.Column("company_id", sa.String(36), nullable=False), sa.Column("channel_id", sa.String(36), nullable=False), sa.Column("bot_id", sa.String(36)), sa.Column("conversation_id", sa.String(36), nullable=False), sa.Column("message_id", sa.String(36)), sa.Column("event_type", sa.String(64), nullable=False), sa.Column("payload", sa.JSON, nullable=False), sa.Column("idempotency_key", sa.String(128), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("attempts", sa.Integer, nullable=False), sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("last_error", sa.Text), sa.Column("delivered_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.ForeignKeyConstraint(["company_id"], ["companies.id"]), sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]), sa.ForeignKeyConstraint(["bot_id"], ["channel_bots.id"]), sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]), sa.ForeignKeyConstraint(["message_id"], ["conversation_messages.id"]), sa.UniqueConstraint("idempotency_key"))
    for name, columns in (("ix_outbox_events_company_id", ["company_id"]), ("ix_outbox_events_channel_id", ["channel_id"]), ("ix_outbox_events_bot_id", ["bot_id"]), ("ix_outbox_events_conversation_id", ["conversation_id"]), ("ix_outbox_events_message_id", ["message_id"]), ("ix_outbox_events_status", ["status"]), ("ix_outbox_events_available_at", ["available_at"])):
        op.create_index(name, "outbox_events", columns)


def downgrade():
    for name in ("ix_outbox_events_available_at", "ix_outbox_events_status", "ix_outbox_events_message_id", "ix_outbox_events_conversation_id", "ix_outbox_events_bot_id", "ix_outbox_events_channel_id", "ix_outbox_events_company_id"):
        op.drop_index(name, table_name="outbox_events")
    op.drop_table("outbox_events")
    for name in ("ix_external_events_bot_id", "ix_external_events_channel_id", "ix_external_events_company_id"):
        op.drop_index(name, table_name="external_events")
    op.drop_table("external_events")
    op.drop_table("conversation_participants")
    op.drop_index("ix_external_identities_channel_id", table_name="external_identities")
    op.drop_index("ix_external_identities_company_id", table_name="external_identities")
    op.drop_table("external_identities")
    op.drop_index("ix_channel_bots_channel_id", table_name="channel_bots")
    op.drop_index("ix_channel_bots_company_id", table_name="channel_bots")
    op.drop_table("channel_bots")
    op.drop_index("ix_channels_kind", table_name="channels")
    op.drop_index("ix_channels_company_id", table_name="channels")
    op.drop_table("channels")
