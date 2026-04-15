"""add venta to solicitud produccion

Revision ID: 5b2f4d8a1c33
Revises: 4e1a9c7b2d11
Create Date: 2026-04-15 15:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5b2f4d8a1c33"
down_revision = "4e1a9c7b2d11"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columnas = {columna["name"] for columna in inspector.get_columns("SolicitudProduccion")}

    if "IdVenta" not in columnas:
        op.add_column(
            "SolicitudProduccion",
            sa.Column("IdVenta", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_solicitudproduccion_venta",
            "SolicitudProduccion",
            "Venta",
            ["IdVenta"],
            ["IdVenta"],
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columnas = {columna["name"] for columna in inspector.get_columns("SolicitudProduccion")}

    if "IdVenta" in columnas:
        op.drop_constraint("fk_solicitudproduccion_venta", "SolicitudProduccion", type_="foreignkey")
        op.drop_column("SolicitudProduccion", "IdVenta")
