"""add unidad inactividad to configuracion

Revision ID: 9e7c1a2b4f10
Revises: f1a6d3b8c2e4
Create Date: 2026-04-14 12:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9e7c1a2b4f10"
down_revision = "f1a6d3b8c2e4"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columnas = {columna["name"] for columna in inspector.get_columns("ConfiguracionSistema")}

    if "UnidadInactividadCierreSesion" not in columnas:
        op.add_column(
            "ConfiguracionSistema",
            sa.Column(
                "UnidadInactividadCierreSesion",
                sa.String(length=10),
                nullable=False,
                server_default=sa.text("'HORAS'"),
            ),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columnas = {columna["name"] for columna in inspector.get_columns("ConfiguracionSistema")}

    if "UnidadInactividadCierreSesion" in columnas:
        op.drop_column("ConfiguracionSistema", "UnidadInactividadCierreSesion")
