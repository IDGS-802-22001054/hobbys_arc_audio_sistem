"""add incremental backup metadata

Revision ID: e4a7c2b9f130
Revises: d2f4c6b8e1a0
Create Date: 2026-04-15 18:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e4a7c2b9f130"
down_revision = "d2f4c6b8e1a0"
branch_labels = None
depends_on = None


def _drop_procedure(bind, name):
    bind.execute(sa.text(f"DROP PROCEDURE IF EXISTS {name}"))


def _crear_procedimiento(bind, sql):
    bind.execute(sa.text(sql))


def upgrade():
    op.add_column(
        "RespaldoSistema",
        sa.Column(
            "TipoRespaldo",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'COMPLETO'"),
        ),
    )
    op.add_column("RespaldoSistema", sa.Column("BinlogArchivoInicio", sa.String(length=255)))
    op.add_column("RespaldoSistema", sa.Column("BinlogPosicionInicio", sa.BigInteger()))
    op.add_column("RespaldoSistema", sa.Column("BinlogArchivoFin", sa.String(length=255)))
    op.add_column("RespaldoSistema", sa.Column("BinlogPosicionFin", sa.BigInteger()))

    bind = op.get_bind()
    _drop_procedure(bind, "SP_BackupIncremental_Registrar")
    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_BackupIncremental_Registrar(
            IN p_nombre_archivo VARCHAR(255),
            IN p_ruta_archivo VARCHAR(500),
            IN p_estado VARCHAR(20),
            IN p_mensaje VARCHAR(255),
            IN p_binlog_archivo_inicio VARCHAR(255),
            IN p_binlog_posicion_inicio BIGINT,
            IN p_binlog_archivo_fin VARCHAR(255),
            IN p_binlog_posicion_fin BIGINT,
            IN p_id_usuario INT
        )
        BEGIN
            INSERT INTO RespaldoSistema (
                TipoRespaldo,
                NombreArchivo,
                RutaArchivo,
                Estado,
                Mensaje,
                BinlogArchivoInicio,
                BinlogPosicionInicio,
                BinlogArchivoFin,
                BinlogPosicionFin,
                IdUsuario
            )
            VALUES (
                'INCREMENTAL',
                p_nombre_archivo,
                p_ruta_archivo,
                COALESCE(NULLIF(p_estado, ''), 'EXITOSO'),
                p_mensaje,
                p_binlog_archivo_inicio,
                p_binlog_posicion_inicio,
                p_binlog_archivo_fin,
                p_binlog_posicion_fin,
                p_id_usuario
            );
        END
        """,
    )


def downgrade():
    bind = op.get_bind()
    _drop_procedure(bind, "SP_BackupIncremental_Registrar")
    op.drop_column("RespaldoSistema", "BinlogPosicionFin")
    op.drop_column("RespaldoSistema", "BinlogArchivoFin")
    op.drop_column("RespaldoSistema", "BinlogPosicionInicio")
    op.drop_column("RespaldoSistema", "BinlogArchivoInicio")
    op.drop_column("RespaldoSistema", "TipoRespaldo")
