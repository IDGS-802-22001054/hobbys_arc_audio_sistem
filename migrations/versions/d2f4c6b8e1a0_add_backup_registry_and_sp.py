"""add backup registry and stored procedure

Revision ID: d2f4c6b8e1a0
Revises: 5b2f4d8a1c33
Create Date: 2026-04-15 17:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d2f4c6b8e1a0"
down_revision = "5b2f4d8a1c33"
branch_labels = None
depends_on = None


def _drop_procedure(bind, name):
    bind.execute(sa.text(f"DROP PROCEDURE IF EXISTS {name}"))


def _crear_procedimiento(bind, sql):
    bind.execute(sa.text(sql))


def upgrade():
    op.create_table(
        "RespaldoSistema",
        sa.Column("IdRespaldoSistema", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("NombreArchivo", sa.String(length=255), nullable=False),
        sa.Column("RutaArchivo", sa.String(length=500), nullable=False),
        sa.Column("Estado", sa.String(length=20), nullable=False, server_default=sa.text("'EXITOSO'")),
        sa.Column("Mensaje", sa.String(length=255), nullable=True),
        sa.Column("FechaRegistro", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("IdUsuario", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["IdUsuario"], ["Usuario.IdUsuario"]),
        sa.PrimaryKeyConstraint("IdRespaldoSistema"),
        mysql_engine="InnoDB",
    )

    bind = op.get_bind()
    _drop_procedure(bind, "SP_Backup_Registrar")
    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Backup_Registrar(
            IN p_nombre_archivo VARCHAR(255),
            IN p_ruta_archivo VARCHAR(500),
            IN p_estado VARCHAR(20),
            IN p_mensaje VARCHAR(255),
            IN p_id_usuario INT
        )
        BEGIN
            INSERT INTO RespaldoSistema (
                NombreArchivo,
                RutaArchivo,
                Estado,
                Mensaje,
                IdUsuario
            )
            VALUES (
                p_nombre_archivo,
                p_ruta_archivo,
                COALESCE(NULLIF(p_estado, ''), 'EXITOSO'),
                p_mensaje,
                p_id_usuario
            );
        END
        """,
    )


def downgrade():
    bind = op.get_bind()
    _drop_procedure(bind, "SP_Backup_Registrar")
    op.drop_table("RespaldoSistema")
