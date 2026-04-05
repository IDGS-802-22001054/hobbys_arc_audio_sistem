"""add cliente tarjetas table

Revision ID: 2c21a1b4f5f5
Revises: 6a24545be01a
Create Date: 2026-04-05 12:36:33.862763

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2c21a1b4f5f5'
down_revision = '6a24545be01a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "TarjetaCliente",
        sa.Column("IdTarjetaCliente", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("IdCliente", sa.Integer(), nullable=False),
        sa.Column("Alias", sa.String(length=100), nullable=True),
        sa.Column("Titular", sa.String(length=150), nullable=False),
        sa.Column("Marca", sa.String(length=50), nullable=False),
        sa.Column("Ultimos4", sa.String(length=4), nullable=False),
        sa.Column("MesExpiracion", sa.Integer(), nullable=False),
        sa.Column("AnioExpiracion", sa.Integer(), nullable=False),
        sa.Column("TokenPasarela", sa.String(length=255), nullable=False),
        sa.Column("EsPredeterminada", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("Activa", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "FechaRegistro",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["IdCliente"], ["Cliente.IdCliente"]),
        sa.PrimaryKeyConstraint("IdTarjetaCliente"),
        sa.UniqueConstraint("TokenPasarela", name="uq_tarjeta_cliente_token_pasarela"),
        mysql_engine="InnoDB",
    )
    op.create_index(
        "ix_tarjeta_cliente_id_cliente",
        "TarjetaCliente",
        ["IdCliente"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_tarjeta_cliente_id_cliente", table_name="TarjetaCliente")
    op.drop_table("TarjetaCliente")
