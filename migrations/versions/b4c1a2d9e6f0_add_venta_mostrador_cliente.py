"""add venta mostrador cliente

Revision ID: b4c1a2d9e6f0
Revises: 8f3b7f9d4c21
Create Date: 2026-04-05 20:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b4c1a2d9e6f0"
down_revision = "8f3b7f9d4c21"
branch_labels = None
depends_on = None


CORREO_MOSTRADOR = "venta.mostrador@arc-audio.local"


def _obtener_cliente_mostrador(bind):
    return bind.execute(
        sa.text(
            """
            SELECT c.IdCliente, p.IdPersona
            FROM Cliente c
            INNER JOIN Persona p ON p.IdPersona = c.IdPersona
            WHERE p.CorreoElectronico = :correo
            LIMIT 1
            """
        ),
        {"correo": CORREO_MOSTRADOR},
    ).fetchone()


def upgrade():
    bind = op.get_bind()
    cliente = _obtener_cliente_mostrador(bind)

    if cliente is None:
        bind.execute(
            sa.text(
                """
                INSERT INTO Persona (
                    Nombre,
                    Apellidos,
                    Telefono,
                    CorreoElectronico,
                    Activo
                ) VALUES (
                    :nombre,
                    :apellidos,
                    NULL,
                    :correo,
                    1
                )
                """
            ),
            {
                "nombre": "Venta",
                "apellidos": "mostrador",
                "correo": CORREO_MOSTRADOR,
            },
        )

        persona_id = bind.execute(
            sa.text(
                """
                SELECT IdPersona
                FROM Persona
                WHERE CorreoElectronico = :correo
                LIMIT 1
                """
            ),
            {"correo": CORREO_MOSTRADOR},
        ).scalar()

        bind.execute(
            sa.text(
                """
                INSERT INTO Cliente (
                    IdPersona,
                    PermiteCompraOnline
                ) VALUES (
                    :id_persona,
                    0
                )
                """
            ),
            {"id_persona": persona_id},
        )

        cliente = _obtener_cliente_mostrador(bind)

    if cliente is not None:
        bind.execute(
            sa.text(
                """
                UPDATE Venta
                SET IdCliente = :id_cliente
                WHERE IdCliente IS NULL
                """
            ),
            {"id_cliente": cliente.IdCliente},
        )


def downgrade():
    bind = op.get_bind()
    cliente = _obtener_cliente_mostrador(bind)

    if cliente is None:
        return

    bind.execute(
        sa.text(
            """
            UPDATE Venta
            SET IdCliente = NULL
            WHERE IdCliente = :id_cliente
            """
        ),
        {"id_cliente": cliente.IdCliente},
    )

    bind.execute(
        sa.text("DELETE FROM Cliente WHERE IdCliente = :id_cliente"),
        {"id_cliente": cliente.IdCliente},
    )
    bind.execute(
        sa.text("DELETE FROM Persona WHERE IdPersona = :id_persona"),
        {"id_persona": cliente.IdPersona},
    )
