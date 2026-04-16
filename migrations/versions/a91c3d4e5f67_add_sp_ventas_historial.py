"""add sp ventas historial

Revision ID: a91c3d4e5f67
Revises: e4a7c2b9f130
Create Date: 2026-04-15 19:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a91c3d4e5f67"
down_revision = "e4a7c2b9f130"
branch_labels = None
depends_on = None


def _drop_procedure(bind, name):
    bind.execute(sa.text(f"DROP PROCEDURE IF EXISTS {name}"))


def _crear_procedimiento(bind, sql):
    bind.execute(sa.text(sql))


def _grant_execute(bind, role_name, procedure_name):
    try:
        bind.execute(sa.text(f"GRANT EXECUTE ON PROCEDURE hobbys_car_audio.{procedure_name} TO `{role_name}`"))
    except Exception:
        # La migracion no debe fallar si el rol no existe todavia en el servidor destino.
        pass


def upgrade():
    bind = op.get_bind()
    _drop_procedure(bind, "SP_Ventas_Historial")
    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Ventas_Historial(IN p_Busqueda VARCHAR(255))
        BEGIN
            DECLARE v_Busqueda VARCHAR(255);
            SET v_Busqueda = NULLIF(TRIM(p_Busqueda), '');

            SELECT
                v.IdVenta,
                v.FechaVenta,
                v.MetodoPago,
                CONCAT_WS(' ', p.Nombre, p.Apellidos) AS NombreCliente,
                vd.IdVentaDetalle,
                vd.Cantidad,
                vd.PrecioUnitario,
                (vd.Cantidad * vd.PrecioUnitario) AS Subtotal,
                pt.Nombre AS NombreProducto,
                tot.TotalVenta
            FROM Venta v
            LEFT JOIN Cliente c
                ON c.IdCliente = v.IdCliente
            LEFT JOIN Persona p
                ON p.IdPersona = c.IdPersona
            LEFT JOIN VentaDetalle vd
                ON vd.IdVenta = v.IdVenta
            LEFT JOIN ProductoTerminado pt
                ON pt.IdProductoTerminado = vd.IdProductoTerminado
            LEFT JOIN (
                SELECT
                    IdVenta,
                    SUM(Cantidad * PrecioUnitario) AS TotalVenta
                FROM VentaDetalle
                GROUP BY IdVenta
            ) tot
                ON tot.IdVenta = v.IdVenta
            WHERE
                v_Busqueda IS NULL
                OR CONCAT_WS(' ', p.Nombre, p.Apellidos) LIKE CONCAT('%', v_Busqueda, '%')
                OR v.MetodoPago LIKE CONCAT('%', v_Busqueda, '%')
                OR CAST(v.IdVenta AS CHAR) LIKE CONCAT('%', v_Busqueda, '%')
            ORDER BY v.FechaVenta DESC, v.IdVenta DESC, vd.IdVentaDetalle ASC;
        END
        """,
    )

    _grant_execute(bind, "Administrador", "SP_Ventas_Historial")
    _grant_execute(bind, "Vendedor", "SP_Ventas_Historial")


def downgrade():
    bind = op.get_bind()
    _drop_procedure(bind, "SP_Ventas_Historial")
