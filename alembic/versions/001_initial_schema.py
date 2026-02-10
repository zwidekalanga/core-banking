"""initial_schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-02-09 00:00:00.000000

Creates all core-banking tables: customers, accounts, transactions, admin_users.
Seeds the 3 default admin users for the fraud-ops portal.
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deterministic UUIDs derived from username — ensures idempotent migrations
_NS = uuid.NAMESPACE_DNS

# Pre-computed bcrypt hashes (passwords: admin123, analyst123, viewer123)
SEED_USERS = [
    {
        "id": str(uuid.uuid5(_NS, "admin")),
        "username": "admin",
        "email": "admin@capitec.co.za",
        "hashed_password": "$2b$12$xLbWBxKgZ9Qp5PWE95MtWeruOHmuw1jE4r5YxRhT8v4im6E1RHbJ2",
        "full_name": "System Administrator",
        "role": "admin",
        "is_active": True,
    },
    {
        "id": str(uuid.uuid5(_NS, "analyst")),
        "username": "analyst",
        "email": "analyst@capitec.co.za",
        "hashed_password": "$2b$12$lBbpStox7587rihT1Sfm6ONOeUNUHfJpXHv33ffv46tk1tZ0YpUa6",
        "full_name": "Fraud Analyst",
        "role": "analyst",
        "is_active": True,
    },
    {
        "id": str(uuid.uuid5(_NS, "viewer")),
        "username": "viewer",
        "email": "viewer@capitec.co.za",
        "hashed_password": "$2b$12$YOlbalmYLaYetVucK.mAFur10YfO.01RoJ2Pa3bWOM86qBxmdnKTe",
        "full_name": "Dashboard Viewer",
        "role": "viewer",
        "is_active": True,
    },
]


def upgrade() -> None:
    """Create all tables and seed admin users."""

    # -- customers --
    op.create_table(
        "customers",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("id_number", sa.String(20), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=False),
        sa.Column("kyc_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("tier", sa.String(20), nullable=False, server_default="standard"),
        sa.Column("segment", sa.String(100), nullable=True),
        sa.Column("risk_rating", sa.String(20), nullable=False, server_default="low"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_external_id", "customers", ["external_id"], unique=True)
    op.create_index("idx_customer_status", "customers", ["status"])
    op.create_index("idx_customer_tier", "customers", ["tier"])
    op.create_index("idx_customer_email", "customers", ["email"], unique=True)
    op.create_index("idx_customer_id_number", "customers", ["id_number"], unique=True)

    # -- accounts --
    op.create_table(
        "accounts",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "customer_id",
            sa.UUID(as_uuid=False),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_number", sa.String(20), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ZAR"),
        sa.Column("balance", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_account_number", "accounts", ["account_number"], unique=True)
    op.create_index("ix_accounts_customer_id", "accounts", ["customer_id"])
    op.create_index("idx_account_customer_type", "accounts", ["customer_id", "account_type"])

    # -- transactions --
    op.create_table(
        "transactions",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column(
            "account_id",
            sa.UUID(as_uuid=False),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.UUID(as_uuid=False),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="ZAR"),
        sa.Column("merchant_name", sa.String(255), nullable=True),
        sa.Column("merchant_category", sa.String(50), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="ZA"),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_external_id", "transactions", ["external_id"], unique=True)
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index("ix_transactions_customer_id", "transactions", ["customer_id"])
    op.create_index("idx_txn_customer_created", "transactions", ["customer_id", "created_at"])
    op.create_index("idx_txn_account_created", "transactions", ["account_id", "created_at"])

    # -- admin_users --
    admin_users = op.create_table(
        "admin_users",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=True)
    op.create_index("ix_admin_users_email", "admin_users", ["email"], unique=True)

    # Seed demo admin users
    op.bulk_insert(admin_users, SEED_USERS)


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("transactions")
    op.drop_table("accounts")
    op.drop_table("admin_users")
    op.drop_table("customers")
