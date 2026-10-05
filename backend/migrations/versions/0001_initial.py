"""Initial ADVAR schema (hand-maintained).

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-27

All tables use UUID primary keys (gen_random_uuid from pgcrypto), timestamptz
created_at/updated_at, money as integer minor units + currency, citext e-mails.
Enumerations are enforced with CHECK constraints so they can be extended in a
later migration without a type rebuild.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

TEST_STATUSES = ("draft", "awaiting_payment", "payment_review", "queued", "running", "completed", "failed", "refunded")
POST_TYPES = ("paid", "boosted", "organic")
GOALS = ("sales", "messages", "traffic", "awareness", "engagement")
PAYMENT_STATUSES = ("pending", "pending_review", "succeeded", "failed", "cancelled", "expired", "refunded", "consumed")
PAYMENT_METHODS = ("trial", "stripe", "manual")
VERSION_STATUSES = ("draft", "published", "archived")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.create_table("audit_logs",
    sa.Column("actor_id", sa.UUID(), nullable=True),
    sa.Column("action", sa.String(length=64), nullable=False),
    sa.Column("entity", sa.String(length=64), nullable=False),
    sa.Column("entity_id", sa.Text(), nullable=True),
    sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("ip", sa.String(length=64), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs"))
    )
    op.create_index("ix_audit_entity", "audit_logs", ["entity", "entity_id"], unique=False)
    op.create_table("category_templates",
    sa.Column("code", sa.String(length=64), nullable=False),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("parent_code", sa.String(length=64), nullable=True),
    sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("trait_dimensions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("activation_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("default_mixes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("buying_behavior", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("blockers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("trust_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("comment_topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("typical_goals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("analyzer_hints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("benchmark_adjustments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("calendar", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("restrictions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("country_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("change_note", sa.Text(), nullable=False),
    sa.Column("created_by", sa.UUID(), nullable=True),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("active", sa.Boolean(), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_category_templates")),
    sa.UniqueConstraint("code", "version", name="uq_category_code_version")
    )
    op.create_table("countries",
    sa.Column("code", sa.String(length=2), nullable=False),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("currency", sa.String(length=3), nullable=False),
    sa.Column("current_version", sa.Integer(), nullable=True),
    sa.Column("payment_methods", postgresql.ARRAY(sa.Text()), nullable=False),
    sa.Column("active", sa.Boolean(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("code", name=op.f("pk_countries"))
    )
    op.create_table("fx_rates",
    sa.Column("currency", sa.String(length=3), nullable=False),
    sa.Column("rate_per_usd", sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column("effective_date", sa.Date(), nullable=False),
    sa.Column("updated_by", sa.UUID(), nullable=True),
    sa.Column("note", sa.Text(), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_fx_rates")),
    sa.UniqueConstraint("currency", name=op.f("uq_fx_rates_currency"))
    )
    op.create_table("platforms",
    sa.Column("code", sa.String(length=32), nullable=False),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("current_version", sa.Integer(), nullable=True),
    sa.Column("active", sa.Boolean(), nullable=False),
    sa.Column("sort_order", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("code", name=op.f("pk_platforms"))
    )
    op.create_table("prices",
    sa.Column("tier_code", sa.String(length=16), nullable=False),
    sa.Column("currency", sa.String(length=3), nullable=False),
    sa.Column("amount_minor", sa.Integer(), nullable=False),
    sa.Column("extra_platform_minor", sa.Integer(), nullable=False),
    sa.Column("method", sa.String(length=16), nullable=False),
    sa.Column("active", sa.Boolean(), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_prices")),
    sa.UniqueConstraint("tier_code", "currency", name="uq_price_tier_currency")
    )
    op.create_table("scenarios",
    sa.Column("code", sa.String(length=64), nullable=False),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("modifiers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("country_codes", postgresql.ARRAY(sa.Text()), nullable=False),
    sa.Column("category_codes", postgresql.ARRAY(sa.Text()), nullable=False),
    sa.Column("date_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("weight", sa.Float(), nullable=False),
    sa.Column("active", sa.Boolean(), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("change_note", sa.Text(), nullable=False),
    sa.Column("created_by", sa.UUID(), nullable=True),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_scenarios")),
    sa.UniqueConstraint("code", "version", name="uq_scenario_code_version")
    )
    op.create_table("settings",
    sa.Column("key", sa.String(length=64), nullable=False),
    sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("key", name=op.f("pk_settings"))
    )
    op.create_table("stripe_events",
    sa.Column("id", sa.Text(), nullable=False),
    sa.Column("type", sa.Text(), nullable=False),
    sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_stripe_events"))
    )
    op.create_table("tiers",
    sa.Column("code", sa.String(length=16), nullable=False),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("runs_target", sa.Integer(), nullable=False),
    sa.Column("min_runs", sa.Integer(), nullable=False),
    sa.Column("scenarios", sa.Integer(), nullable=False),
    sa.Column("max_audiences", sa.Integer(), nullable=False),
    sa.Column("agents", sa.Integer(), nullable=False),
    sa.Column("archetypes", sa.Integer(), nullable=False),
    sa.Column("active", sa.Boolean(), nullable=False),
    sa.Column("sort_order", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("code", name=op.f("pk_tiers"))
    )
    op.create_table("users",
    sa.Column("email", postgresql.CITEXT(), nullable=False),
    sa.Column("email_normalized", sa.Text(), nullable=False),
    sa.Column("password_hash", sa.Text(), nullable=True),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("role", sa.String(length=16), nullable=False),
    sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("locale", sa.String(length=16), nullable=False),
    sa.Column("country", sa.String(length=2), nullable=True),
    sa.Column("is_blocked", sa.Boolean(), nullable=False),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    sa.UniqueConstraint("email_normalized", name=op.f("uq_users_email_normalized"))
    )
    op.create_table("weight_sets",
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("behavior", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("score_by_goal", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("change_note", sa.Text(), nullable=False),
    sa.Column("created_by", sa.UUID(), nullable=True),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_weight_sets")),
    sa.UniqueConstraint("version", name="uq_weight_set_version")
    )
    op.create_table("business_profiles",
    sa.Column("user_id", sa.UUID(), nullable=False),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("category_code", sa.String(length=64), nullable=False),
    sa.Column("current_version", sa.Integer(), nullable=False),
    sa.Column("is_default", sa.Boolean(), nullable=False),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_business_profiles_user_id_users"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_business_profiles"))
    )
    op.create_table("country_versions",
    sa.Column("country_code", sa.String(length=2), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("change_note", sa.Text(), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("created_by", sa.UUID(), nullable=True),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["country_code"], ["countries.code"], name=op.f("fk_country_versions_country_code_countries"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_country_versions")),
    sa.UniqueConstraint("country_code", "version", name="uq_country_version")
    )
    op.create_table("email_tokens",
    sa.Column("user_id", sa.UUID(), nullable=False),
    sa.Column("purpose", sa.String(length=16), nullable=False),
    sa.Column("token_hash", sa.Text(), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_email_tokens_user_id_users"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_email_tokens")),
    sa.UniqueConstraint("token_hash", name=op.f("uq_email_tokens_token_hash"))
    )
    op.create_table("oauth_accounts",
    sa.Column("user_id", sa.UUID(), nullable=False),
    sa.Column("provider", sa.String(length=32), nullable=False),
    sa.Column("provider_user_id", sa.Text(), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_oauth_accounts_user_id_users"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_accounts")),
    sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user")
    )
    op.create_table("platform_settings",
    sa.Column("platform_code", sa.String(length=32), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("global", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("markets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("change_note", sa.Text(), nullable=False),
    sa.Column("created_by", sa.UUID(), nullable=True),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["platform_code"], ["platforms.code"], name=op.f("fk_platform_settings_platform_code_platforms"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_settings")),
    sa.UniqueConstraint("platform_code", "version", name="uq_platform_version")
    )
    op.create_table("refresh_tokens",
    sa.Column("user_id", sa.UUID(), nullable=False),
    sa.Column("token_hash", sa.Text(), nullable=False),
    sa.Column("user_agent", sa.Text(), nullable=True),
    sa.Column("ip", sa.String(length=64), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
    sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash"))
    )
    op.create_table("profile_versions",
    sa.Column("profile_id", sa.UUID(), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("data_hash", sa.String(length=64), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["profile_id"], ["business_profiles.id"], name=op.f("fk_profile_versions_profile_id_business_profiles"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_profile_versions")),
    sa.UniqueConstraint("profile_id", "version", name="uq_profile_version")
    )
    op.create_table("ad_tests",
    sa.Column("user_id", sa.UUID(), nullable=False),
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("status", sa.String(length=24), nullable=False),
    sa.Column("tier_code", sa.String(length=16), nullable=False),
    sa.Column("country_code", sa.String(length=2), nullable=False),
    sa.Column("settings_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("post_type", sa.String(length=16), nullable=False),
    sa.Column("goal", sa.String(length=16), nullable=False),
    sa.Column("platforms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("schedule", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("budget_minor", sa.BigInteger(), nullable=True),
    sa.Column("currency", sa.String(length=3), nullable=False),
    sa.Column("audiences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("ad_copy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("profile_id", sa.UUID(), nullable=True),
    sa.Column("profile_version_id", sa.UUID(), nullable=True),
    sa.Column("profile_mode", sa.String(length=16), nullable=True),
    sa.Column("profile_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column("fingerprint", sa.String(length=64), nullable=True),
    sa.Column("fingerprint_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column("engine_version", sa.String(length=32), nullable=True),
    sa.Column("cancel_count", sa.Integer(), nullable=False),
    sa.Column("cancel_window_open", sa.Boolean(), nullable=False),
    sa.Column("paid_via", sa.String(length=16), nullable=True),
    sa.Column("payment_id", sa.UUID(), nullable=True),
    sa.Column("free_restart_available", sa.Boolean(), nullable=False),
    sa.Column("rerun_available", sa.Boolean(), nullable=False),
    sa.Column("parent_test_id", sa.UUID(), nullable=True),
    sa.Column("progress_pct", sa.Integer(), nullable=False),
    sa.Column("stage", sa.String(length=24), nullable=True),
    sa.Column("pipeline_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("score", sa.Float(), nullable=True),
    sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["parent_test_id"], ["ad_tests.id"], name=op.f("fk_ad_tests_parent_test_id_ad_tests"), ondelete="SET NULL"),
    sa.ForeignKeyConstraint(["profile_id"], ["business_profiles.id"], name=op.f("fk_ad_tests_profile_id_business_profiles"), ondelete="SET NULL"),
    sa.ForeignKeyConstraint(["profile_version_id"], ["profile_versions.id"], name=op.f("fk_ad_tests_profile_version_id_profile_versions"), ondelete="SET NULL"),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_ad_tests_user_id_users"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_ad_tests"))
    )
    op.create_index("ix_tests_fingerprint", "ad_tests", ["user_id", "fingerprint"], unique=False, postgresql_where=sa.text("status = 'completed'"))
    op.create_index("ix_tests_status", "ad_tests", ["status"], unique=False)
    op.create_index("ix_tests_user_created", "ad_tests", ["user_id", sa.text("created_at DESC")], unique=False)
    op.create_table("ad_analyses",
    sa.Column("ad_test_id", sa.UUID(), nullable=False),
    sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("description", sa.Text(), nullable=False),
    sa.Column("caption_language", sa.String(length=16), nullable=True),
    sa.Column("caption_english", sa.Text(), nullable=True),
    sa.Column("transcript", sa.Text(), nullable=True),
    sa.Column("model", sa.String(length=64), nullable=False),
    sa.Column("prompt_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["ad_test_id"], ["ad_tests.id"], name=op.f("fk_ad_analyses_ad_test_id_ad_tests"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("ad_test_id", name=op.f("pk_ad_analyses"))
    )
    op.create_table("ad_assets",
    sa.Column("ad_test_id", sa.UUID(), nullable=False),
    sa.Column("kind", sa.String(length=16), nullable=False),
    sa.Column("storage_key", sa.Text(), nullable=False),
    sa.Column("mime", sa.String(length=64), nullable=False),
    sa.Column("width", sa.Integer(), nullable=True),
    sa.Column("height", sa.Integer(), nullable=True),
    sa.Column("duration_s", sa.Float(), nullable=True),
    sa.Column("size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("sha256", sa.String(length=64), nullable=False),
    sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("parent_asset_id", sa.UUID(), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["ad_test_id"], ["ad_tests.id"], name=op.f("fk_ad_assets_ad_test_id_ad_tests"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_ad_assets"))
    )
    op.create_table("archetypes",
    sa.Column("ad_test_id", sa.UUID(), nullable=False),
    sa.Column("platform_code", sa.String(length=32), nullable=False),
    sa.Column("audience_idx", sa.Integer(), nullable=False),
    sa.Column("scenario", sa.String(length=64), nullable=False),
    sa.Column("idx", sa.Integer(), nullable=False),
    sa.Column("profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("size", sa.Integer(), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["ad_test_id"], ["ad_tests.id"], name=op.f("fk_archetypes_ad_test_id_ad_tests"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_archetypes"))
    )
    op.create_index("ix_archetypes_test", "archetypes", ["ad_test_id"], unique=False)
    op.create_table("calibration_results",
    sa.Column("ad_test_id", sa.UUID(), nullable=False),
    sa.Column("source", sa.String(length=16), nullable=False),
    sa.Column("actual_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["ad_test_id"], ["ad_tests.id"], name=op.f("fk_calibration_results_ad_test_id_ad_tests"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_calibration_results"))
    )
    op.create_table("llm_usage",
    sa.Column("ad_test_id", sa.UUID(), nullable=True),
    sa.Column("stage", sa.String(length=32), nullable=False),
    sa.Column("model", sa.String(length=64), nullable=False),
    sa.Column("input_tokens", sa.Integer(), nullable=False),
    sa.Column("cached_tokens", sa.Integer(), nullable=False),
    sa.Column("output_tokens", sa.Integer(), nullable=False),
    sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
    sa.Column("latency_ms", sa.Integer(), nullable=False),
    sa.Column("prompt_version", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.ForeignKeyConstraint(["ad_test_id"], ["ad_tests.id"], name=op.f("fk_llm_usage_ad_test_id_ad_tests"), ondelete="SET NULL"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_usage"))
    )
    op.create_index("ix_llm_usage_created", "llm_usage", ["created_at"], unique=False)
    op.create_index("ix_llm_usage_test", "llm_usage", ["ad_test_id"], unique=False)
    op.create_table("payments",
    sa.Column("user_id", sa.UUID(), nullable=False),
    sa.Column("ad_test_id", sa.UUID(), nullable=False),
    sa.Column("method", sa.String(length=16), nullable=False),
    sa.Column("mode", sa.String(length=16), nullable=False),
    sa.Column("status", sa.String(length=24), nullable=False),
    sa.Column("amount_usd_minor", sa.BigInteger(), nullable=False),
    sa.Column("currency", sa.String(length=3), nullable=False),
    sa.Column("local_currency", sa.String(length=3), nullable=True),
    sa.Column("local_amount_minor", sa.BigInteger(), nullable=True),
    sa.Column("fx_rate", sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column("payment_code", sa.String(length=32), nullable=True),
    sa.Column("stripe_session_id", sa.Text(), nullable=True),
    sa.Column("stripe_payment_intent_id", sa.Text(), nullable=True),
    sa.Column("checkout_url", sa.Text(), nullable=True),
    sa.Column("admin_reference", sa.Text(), nullable=True),
    sa.Column("approved_by", sa.UUID(), nullable=True),
    sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancel_reason", sa.Text(), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("refund_ref", sa.Text(), nullable=True),
    sa.Column("flagged", sa.Text(), nullable=True),
    sa.Column("tier_code", sa.String(length=16), nullable=False),
    sa.Column("platform_count", sa.Integer(), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["ad_test_id"], ["ad_tests.id"], name=op.f("fk_payments_ad_test_id_ad_tests"), ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_payments_user_id_users"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_payments"))
    )
    op.create_index("ix_payments_review", "payments", ["status"], unique=False, postgresql_where=sa.text("method = \'manual\'"))
    op.create_index("ix_payments_user", "payments", ["user_id", sa.text("created_at DESC")], unique=False)
    op.create_index("uq_payment_code", "payments", ["payment_code"], unique=True, postgresql_where=sa.text("payment_code IS NOT NULL"))
    op.create_index("uq_payment_success_per_test", "payments", ["ad_test_id"], unique=True, postgresql_where=sa.text("status = \'succeeded\'"))
    op.create_table("reports",
    sa.Column("ad_test_id", sa.UUID(), nullable=False),
    sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("funnel", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("segments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("brand_relationship", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("comments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("timing", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("audiences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("platforms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("language_groups", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("pdf_key", sa.Text(), nullable=True),
    sa.Column("version", sa.String(length=32), nullable=False),
    sa.Column("note", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["ad_test_id"], ["ad_tests.id"], name=op.f("fk_reports_ad_test_id_ad_tests"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("ad_test_id", name=op.f("pk_reports"))
    )
    op.create_table("run_results",
    sa.Column("ad_test_id", sa.UUID(), nullable=False),
    sa.Column("platform_code", sa.String(length=32), nullable=False),
    sa.Column("audience_idx", sa.Integer(), nullable=False),
    sa.Column("run_no", sa.Integer(), nullable=False),
    sa.Column("scenario", sa.String(length=64), nullable=False),
    sa.Column("seed", sa.BigInteger(), nullable=False),
    sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("score", sa.Float(), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["ad_test_id"], ["ad_tests.id"], name=op.f("fk_run_results_ad_test_id_ad_tests"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_run_results"))
    )
    op.create_index("ix_runs_test", "run_results", ["ad_test_id", "audience_idx", "run_no"], unique=False)
    op.create_table("trial_grants",
    sa.Column("user_id", sa.UUID(), nullable=False),
    sa.Column("ad_test_id", sa.UUID(), nullable=True),
    sa.Column("ip", sa.String(length=64), nullable=True),
    sa.Column("device_hash", sa.String(length=64), nullable=True),
    sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["ad_test_id"], ["ad_tests.id"], name=op.f("fk_trial_grants_ad_test_id_ad_tests"), ondelete="SET NULL"),
    sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_trial_grants_user_id_users"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_trial_grants")),
    sa.UniqueConstraint("user_id", name="uq_trial_user")
    )
    op.create_table("archetype_reactions",
    sa.Column("archetype_id", sa.UUID(), nullable=False),
    sa.Column("reaction", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column("comment", sa.Text(), nullable=True),
    sa.Column("reason", sa.Text(), nullable=True),
    sa.Column("model", sa.String(length=64), nullable=False),
    sa.Column("prompt_version", sa.String(length=32), nullable=False),
    sa.Column("fallback_from", sa.UUID(), nullable=True),
    sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["archetype_id"], ["archetypes.id"], name=op.f("fk_archetype_reactions_archetype_id_archetypes"), ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id", name=op.f("pk_archetype_reactions")),
    sa.UniqueConstraint("archetype_id", name=op.f("uq_archetype_reactions_archetype_id"))
    )

    # --- enumerations and business rules -----------------------------------
    op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'admin')")
    op.create_check_constraint("ck_tests_status", "ad_tests", _in("status", TEST_STATUSES))
    op.create_check_constraint("ck_tests_post_type", "ad_tests", _in("post_type", POST_TYPES))
    op.create_check_constraint("ck_tests_goal", "ad_tests", _in("goal", GOALS))
    op.create_check_constraint(
        "ck_tests_budget_by_post_type",
        "ad_tests",
        "(post_type = 'organic' AND budget_minor IS NULL) OR (post_type <> 'organic')",
    )
    op.create_check_constraint("ck_payments_status", "payments", _in("status", PAYMENT_STATUSES))
    op.create_check_constraint("ck_payments_method", "payments", _in("method", PAYMENT_METHODS))
    op.create_check_constraint("ck_platforms_status", "platforms", "status IN ('full', 'beta', 'planned')")
    op.create_check_constraint("ck_country_versions_status", "country_versions", _in("status", VERSION_STATUSES))
    op.create_check_constraint("ck_platform_settings_status", "platform_settings", _in("status", VERSION_STATUSES))
    op.create_check_constraint("ck_category_templates_status", "category_templates", _in("status", VERSION_STATUSES))
    op.create_check_constraint("ck_scenarios_status", "scenarios", _in("status", VERSION_STATUSES))
    op.create_check_constraint("ck_weight_sets_status", "weight_sets", _in("status", VERSION_STATUSES))
    op.create_check_constraint("ck_assets_kind", "ad_assets", "kind IN ('image', 'video', 'frame', 'audio')")
    op.create_check_constraint("ck_email_tokens_purpose", "email_tokens", "purpose IN ('verify', 'reset')")


def downgrade() -> None:
    op.drop_table("archetype_reactions")
    op.drop_table("trial_grants")
    op.drop_index("ix_runs_test", table_name="run_results")
    op.drop_table("run_results")
    op.drop_table("reports")
    op.drop_index("uq_payment_success_per_test", table_name="payments", postgresql_where=sa.text("status = \'succeeded\'"))
    op.drop_index("uq_payment_code", table_name="payments", postgresql_where=sa.text("payment_code IS NOT NULL"))
    op.drop_index("ix_payments_user", table_name="payments")
    op.drop_index("ix_payments_review", table_name="payments", postgresql_where=sa.text("method = \'manual\'"))
    op.drop_table("payments")
    op.drop_index("ix_llm_usage_test", table_name="llm_usage")
    op.drop_index("ix_llm_usage_created", table_name="llm_usage")
    op.drop_table("llm_usage")
    op.drop_table("calibration_results")
    op.drop_index("ix_archetypes_test", table_name="archetypes")
    op.drop_table("archetypes")
    op.drop_table("ad_assets")
    op.drop_table("ad_analyses")
    op.drop_index("ix_tests_user_created", table_name="ad_tests")
    op.drop_index("ix_tests_status", table_name="ad_tests")
    op.drop_index("ix_tests_fingerprint", table_name="ad_tests", postgresql_where=sa.text("status = 'completed'"))
    op.drop_table("ad_tests")
    op.drop_table("profile_versions")
    op.drop_table("refresh_tokens")
    op.drop_table("platform_settings")
    op.drop_table("oauth_accounts")
    op.drop_table("email_tokens")
    op.drop_table("country_versions")
    op.drop_table("business_profiles")
    op.drop_table("weight_sets")
    op.drop_table("users")
    op.drop_table("tiers")
    op.drop_table("stripe_events")
    op.drop_table("settings")
    op.drop_table("scenarios")
    op.drop_table("prices")
    op.drop_table("platforms")
    op.drop_table("fx_rates")
    op.drop_table("countries")
    op.drop_table("category_templates")
    op.drop_index("ix_audit_entity", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.execute("DROP EXTENSION IF EXISTS citext")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
