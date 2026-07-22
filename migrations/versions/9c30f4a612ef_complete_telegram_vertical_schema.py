"""complete Telegram, attachment and delivery schema

Revision ID: 9c30f4a612ef
Revises: 7a91bc4de220
"""
from alembic import op
import sqlalchemy as sa

revision = "9c30f4a612ef"
down_revision = "7a91bc4de220"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("channels") as batch:
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
        batch.create_check_constraint("ck_channels_channel_kind", "kind IN ('web','telegram')")
    with op.batch_alter_table("channel_bots") as batch:
        batch.add_column(sa.Column("public_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("username", sa.String(64)))
        batch.add_column(sa.Column("telegram_bot_id", sa.String(32)))
        batch.add_column(sa.Column("token_fingerprint", sa.String(16)))
        batch.add_column(sa.Column("webhook_secret_ciphertext", sa.Text))
        batch.add_column(sa.Column("mode", sa.String(16), server_default="disabled", nullable=False))
        batch.add_column(sa.Column("status", sa.String(16), server_default="draft", nullable=False))
        batch.add_column(sa.Column("polling_offset", sa.Integer, server_default="0", nullable=False))
        batch.add_column(sa.Column("last_validated_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("last_poll_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("last_error", sa.Text))
        batch.add_column(sa.Column("created_by", sa.String(36)))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
        batch.create_foreign_key("fk_channel_bots_created_by_users", "users", ["created_by"], ["id"])
        batch.create_unique_constraint("uq_channel_bots_public_id", ["public_id"])
        batch.create_unique_constraint("uq_channel_bots_company_name", ["company_id", "name"])
        batch.create_check_constraint("ck_channel_bots_telegram_bot_mode", "mode IN ('webhook','polling','disabled')")
        batch.create_check_constraint("ck_channel_bots_telegram_bot_status", "status IN ('draft','validating','active','inactive','error')")
    op.execute("UPDATE channel_bots SET public_id = id WHERE public_id IS NULL")
    with op.batch_alter_table("channel_bots") as batch:
        batch.alter_column("public_id",existing_type=sa.String(36),nullable=False)
    op.create_index("ix_channel_bots_public_id", "channel_bots", ["public_id"], unique=True)
    op.create_index("ix_channel_bots_telegram_bot_id", "channel_bots", ["telegram_bot_id"])
    op.create_index("ix_channel_bots_status", "channel_bots", ["status"])
    with op.batch_alter_table("external_identities") as batch:
        batch.drop_constraint("uq_external_identities_channel_id", type_="unique")
        batch.add_column(sa.Column("bot_id", sa.String(36)))
        batch.add_column(sa.Column("external_chat_id", sa.String(160)))
        batch.add_column(sa.Column("provider", sa.String(32), server_default="telegram", nullable=False))
        batch.add_column(sa.Column("username", sa.String(160)))
        batch.add_column(sa.Column("phone", sa.String(32)))
        batch.add_column(sa.Column("metadata", sa.JSON, server_default="{}", nullable=False))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
        batch.create_foreign_key("fk_external_identities_bot_id_channel_bots", "channel_bots", ["bot_id"], ["id"])
        batch.create_unique_constraint("uq_external_identity_provider", ["channel_id", "bot_id", "external_id", "external_chat_id"])
    op.create_index("ix_external_identities_bot_id", "external_identities", ["bot_id"])
    op.create_index("ix_external_identities_external_chat_id", "external_identities", ["external_chat_id"])
    with op.batch_alter_table("conversation_participants") as batch:
        batch.add_column(sa.Column("left_at", sa.DateTime(timezone=True)))
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("channel_id", sa.String(36)))
        batch.add_column(sa.Column("bot_id", sa.String(36)))
        batch.add_column(sa.Column("external_identity_id", sa.String(36)))
        batch.add_column(sa.Column("assigned_team_id", sa.String(36)))
        batch.add_column(sa.Column("equipment_id", sa.String(36)))
        batch.add_column(sa.Column("service_order_id", sa.String(36)))
        batch.add_column(sa.Column("priority", sa.String(20), server_default="normal", nullable=False))
        batch.add_column(sa.Column("unread_count", sa.Integer, server_default="0", nullable=False))
        batch.add_column(sa.Column("last_message_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("closed_at", sa.DateTime(timezone=True)))
        batch.create_foreign_key("fk_conversations_channel_id_channels", "channels", ["channel_id"], ["id"])
        batch.create_foreign_key("fk_conversations_bot_id_channel_bots", "channel_bots", ["bot_id"], ["id"])
        batch.create_foreign_key("fk_conversations_external_identity_id_external_identities", "external_identities", ["external_identity_id"], ["id"])
        batch.create_foreign_key("fk_conversations_assigned_team_id_teams", "teams", ["assigned_team_id"], ["id"])
        batch.create_foreign_key("fk_conversations_equipment_id_equipment", "equipment", ["equipment_id"], ["id"])
        batch.create_foreign_key("fk_conversations_service_order_id_service_orders", "service_orders", ["service_order_id"], ["id"])
    for name, col in (("ix_conversations_channel_id", "channel_id"), ("ix_conversations_bot_id", "bot_id"), ("ix_conversations_external_identity_id", "external_identity_id"), ("ix_conversations_assigned_team_id", "assigned_team_id"), ("ix_conversations_equipment_id", "equipment_id"), ("ix_conversations_service_order_id", "service_order_id"), ("ix_conversations_priority", "priority"), ("ix_conversations_last_message_at", "last_message_at")):
        op.create_index(name, "conversations", [col])
    op.execute("UPDATE conversations SET status='queued' WHERE status='human_queue'")
    with op.batch_alter_table("conversation_messages") as batch:
        batch.add_column(sa.Column("company_id", sa.String(36)))
        batch.add_column(sa.Column("channel_id", sa.String(36)))
        batch.add_column(sa.Column("status", sa.String(20), server_default="received", nullable=False))
        batch.add_column(sa.Column("provider_update_id", sa.String(160)))
        batch.add_column(sa.Column("sender_user_id", sa.String(36)))
        batch.add_column(sa.Column("sender_external_identity_id", sa.String(36)))
        batch.add_column(sa.Column("reply_to_message_id", sa.String(36)))
        batch.add_column(sa.Column("normalized_text", sa.Text))
        batch.add_column(sa.Column("received_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("sent_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("failed_at", sa.DateTime(timezone=True)))
        batch.create_foreign_key("fk_messages_company_id_companies", "companies", ["company_id"], ["id"])
        batch.create_foreign_key("fk_messages_channel_id_channels", "channels", ["channel_id"], ["id"])
        batch.create_foreign_key("fk_messages_sender_user_id_users", "users", ["sender_user_id"], ["id"])
        batch.create_foreign_key("fk_messages_sender_external_identity_id_external_identities", "external_identities", ["sender_external_identity_id"], ["id"])
        batch.create_foreign_key("fk_messages_reply_to_message_id_messages", "conversation_messages", ["reply_to_message_id"], ["id"])
    for name, col in (("ix_conversation_messages_company_id", "company_id"), ("ix_conversation_messages_channel_id", "channel_id"), ("ix_conversation_messages_status", "status"), ("ix_conversation_messages_provider_update_id", "provider_update_id")):
        op.create_index(name, "conversation_messages", [col])
    with op.batch_alter_table("external_events") as batch:
        batch.add_column(sa.Column("payload_hash", sa.String(64)))
        batch.add_column(sa.Column("status", sa.String(20), server_default="received", nullable=False))
        batch.add_column(sa.Column("error", sa.Text))
        batch.add_column(sa.Column("attempts", sa.Integer, server_default="0", nullable=False))
    op.create_index("ix_external_events_payload_hash", "external_events", ["payload_hash"])
    op.create_index("ix_external_events_status", "external_events", ["status"])
    with op.batch_alter_table("outbox_events") as batch:
        batch.add_column(sa.Column("locked_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("locked_by", sa.String(100)))
        batch.add_column(sa.Column("dead_lettered_at", sa.DateTime(timezone=True)))
    op.create_index("ix_outbox_events_locked_at", "outbox_events", ["locked_at"])
    op.create_table("attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("message_id", sa.String(36), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36)),
        sa.Column("equipment_id", sa.String(36)),
        sa.Column("service_order_id", sa.String(36)),
        sa.Column("storage_provider", sa.String(20), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("safe_filename", sa.String(255), nullable=False),
        sa.Column("declared_mime_type", sa.String(160)),
        sa.Column("detected_mime_type", sa.String(160), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("telegram_file_id", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["conversation_messages.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"]),
        sa.ForeignKeyConstraint(["service_order_id"], ["service_orders.id"]),
    )
    for name, col in (("company_id", "company_id"), ("message_id", "message_id"), ("conversation_id", "conversation_id"), ("customer_id", "customer_id"), ("equipment_id", "equipment_id"), ("service_order_id", "service_order_id"), ("sha256", "sha256"), ("status", "status")):
        op.create_index(f"ix_attachments_{name}", "attachments", [col])


def downgrade():
    for col in ("status", "sha256", "service_order_id", "equipment_id", "customer_id", "conversation_id", "message_id", "company_id"):
        op.drop_index(f"ix_attachments_{col}", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_outbox_events_locked_at", table_name="outbox_events")
    with op.batch_alter_table("outbox_events") as batch:
        batch.drop_column("dead_lettered_at"); batch.drop_column("locked_by"); batch.drop_column("locked_at")
    op.drop_index("ix_external_events_status", table_name="external_events")
    op.drop_index("ix_external_events_payload_hash", table_name="external_events")
    with op.batch_alter_table("external_events") as batch:
        batch.drop_column("attempts"); batch.drop_column("error"); batch.drop_column("status"); batch.drop_column("payload_hash")
    for name in ("provider_update_id", "status", "channel_id", "company_id"):
        op.drop_index(f"ix_conversation_messages_{name}", table_name="conversation_messages")
    with op.batch_alter_table("conversation_messages") as batch:
        for col in ("failed_at", "sent_at", "received_at", "normalized_text", "reply_to_message_id", "sender_external_identity_id", "sender_user_id", "provider_update_id", "status", "channel_id", "company_id"):
            batch.drop_column(col)
    for name in ("last_message_at", "priority", "service_order_id", "equipment_id", "assigned_team_id", "external_identity_id", "bot_id", "channel_id"):
        op.drop_index(f"ix_conversations_{name}", table_name="conversations")
    op.execute("UPDATE conversations SET status='human_queue' WHERE status='queued'")
    with op.batch_alter_table("conversations") as batch:
        for col in ("closed_at", "last_message_at", "unread_count", "priority", "service_order_id", "equipment_id", "assigned_team_id", "external_identity_id", "bot_id", "channel_id"):
            batch.drop_column(col)
    with op.batch_alter_table("conversation_participants") as batch:
        batch.drop_column("left_at")
    op.drop_index("ix_external_identities_external_chat_id", table_name="external_identities")
    op.drop_index("ix_external_identities_bot_id", table_name="external_identities")
    with op.batch_alter_table("external_identities") as batch:
        batch.drop_constraint("uq_external_identity_provider", type_="unique")
        for col in ("updated_at", "metadata", "phone", "username", "provider", "external_chat_id", "bot_id"):
            batch.drop_column(col)
        batch.create_unique_constraint("uq_external_identities_channel_id", ["channel_id", "external_id"])
    for name in ("status", "telegram_bot_id", "public_id"):
        op.drop_index(f"ix_channel_bots_{name}", table_name="channel_bots")
    with op.batch_alter_table("channel_bots") as batch:
        batch.alter_column("public_id",existing_type=sa.String(36),nullable=True)
        batch.drop_constraint("ck_channel_bots_telegram_bot_status", type_="check")
        batch.drop_constraint("ck_channel_bots_telegram_bot_mode", type_="check")
        batch.drop_constraint("uq_channel_bots_company_name", type_="unique")
        batch.drop_constraint("uq_channel_bots_public_id", type_="unique")
        for col in ("updated_at", "created_by", "last_error", "last_poll_at", "last_validated_at", "polling_offset", "status", "mode", "webhook_secret_ciphertext", "token_fingerprint", "telegram_bot_id", "username", "public_id"):
            batch.drop_column(col)
    with op.batch_alter_table("channels") as batch:
        batch.drop_constraint("ck_channels_channel_kind", type_="check")
        batch.drop_column("updated_at")
