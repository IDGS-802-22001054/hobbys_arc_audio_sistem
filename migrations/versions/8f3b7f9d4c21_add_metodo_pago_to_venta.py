"""add metodo pago to venta

Revision ID: 8f3b7f9d4c21
Revises: 2c21a1b4f5f5
Create Date: 2026-04-05 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8f3b7f9d4c21"
down_revision = "2c21a1b4f5f5"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columnas = {columna["name"] for columna in inspector.get_columns("Venta")}

    if "MetodoPago" not in columnas:
        op.add_column(
            "Venta",
            sa.Column(
                "MetodoPago",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'EFECTIVO'"),
            ),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columnas = {columna["name"] for columna in inspector.get_columns("Venta")}

    if "MetodoPago" in columnas:
        op.drop_column("Venta", "MetodoPago")
