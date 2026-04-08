"""remove stored calculated fields

Revision ID: f1a6d3b8c2e4
Revises: c7e2a1d4f9b3
Create Date: 2026-04-05 22:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1a6d3b8c2e4"
down_revision = "c7e2a1d4f9b3"
branch_labels = None
depends_on = None


def _drop_procedure(bind, name):
    bind.execute(sa.text(f"DROP PROCEDURE IF EXISTS {name}"))


def _crear_procedimiento(bind, sql):
    bind.execute(sa.text(sql))


def _recrear_sp_ventas_registrar(bind):
    _drop_procedure(bind, "SP_Ventas_Registrar")
    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Ventas_Registrar(
            IN p_IdCliente INT,
            IN p_IdUsuarioRegistro INT,
            IN p_MetodoPago VARCHAR(20),
            IN p_Detalles LONGTEXT
        )
        BEGIN
            DECLARE v_Index INT DEFAULT 0;
            DECLARE v_Longitud INT DEFAULT 0;
            DECLARE v_ProductoId INT;
            DECLARE v_Cantidad INT;
            DECLARE v_Existe INT DEFAULT 0;
            DECLARE v_Activo TINYINT DEFAULT 0;
            DECLARE v_Stock INT DEFAULT 0;
            DECLARE v_Precio DECIMAL(18, 2) DEFAULT 0;
            DECLARE v_Subtotal DECIMAL(18, 2) DEFAULT 0;
            DECLARE v_Total DECIMAL(18, 2) DEFAULT 0;
            DECLARE v_IdVenta INT;

            DECLARE EXIT HANDLER FOR SQLEXCEPTION
            BEGIN
                ROLLBACK;
                RESIGNAL;
            END;

            IF p_IdCliente IS NULL THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'La venta requiere un cliente valido.';
            END IF;

            IF p_IdUsuarioRegistro IS NULL THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'La venta requiere un usuario valido.';
            END IF;

            IF p_MetodoPago NOT IN ('EFECTIVO', 'TARJETA') THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'El metodo de pago enviado no es valido.';
            END IF;

            IF p_Detalles IS NULL OR JSON_VALID(p_Detalles) = 0 OR JSON_LENGTH(p_Detalles) = 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'La venta requiere al menos un detalle valido.';
            END IF;

            START TRANSACTION;

            INSERT INTO Venta (IdCliente, MetodoPago, IdUsuarioRegistro)
            VALUES (p_IdCliente, p_MetodoPago, p_IdUsuarioRegistro);

            SET v_IdVenta = LAST_INSERT_ID();
            SET v_Longitud = JSON_LENGTH(p_Detalles);

            WHILE v_Index < v_Longitud DO
                SET v_ProductoId = CAST(
                    JSON_UNQUOTE(JSON_EXTRACT(p_Detalles, CONCAT('$[', v_Index, '].producto_id')))
                    AS UNSIGNED
                );
                SET v_Cantidad = CAST(
                    JSON_UNQUOTE(JSON_EXTRACT(p_Detalles, CONCAT('$[', v_Index, '].cantidad')))
                    AS UNSIGNED
                );

                IF v_ProductoId IS NULL OR v_ProductoId <= 0 OR v_Cantidad IS NULL OR v_Cantidad <= 0 THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'Uno de los detalles de la venta no es valido.';
                END IF;

                SELECT COUNT(*)
                INTO v_Existe
                FROM ProductoTerminado
                WHERE IdProductoTerminado = v_ProductoId;

                IF v_Existe = 0 THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'Uno de los productos enviados no existe.';
                END IF;

                SELECT Activo, StockActual, PrecioVenta
                INTO v_Activo, v_Stock, v_Precio
                FROM ProductoTerminado
                WHERE IdProductoTerminado = v_ProductoId
                FOR UPDATE;

                IF v_Activo <> 1 THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'Uno de los productos de la venta ya no esta disponible.';
                END IF;

                IF v_Cantidad > v_Stock THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'Stock insuficiente para uno de los productos seleccionados.';
                END IF;

                SET v_Subtotal = v_Precio * v_Cantidad;
                SET v_Total = v_Total + v_Subtotal;

                INSERT INTO VentaDetalle (
                    IdVenta,
                    IdProductoTerminado,
                    Cantidad,
                    PrecioUnitario
                )
                VALUES (
                    v_IdVenta,
                    v_ProductoId,
                    v_Cantidad,
                    v_Precio
                );

                UPDATE ProductoTerminado
                SET StockActual = StockActual - v_Cantidad
                WHERE IdProductoTerminado = v_ProductoId;

                SET v_Index = v_Index + 1;
            END WHILE;

            COMMIT;

            SELECT v_IdVenta AS IdVenta, v_Total AS TotalVenta;
        END
        """,
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columnas_compra = {columna["name"] for columna in inspector.get_columns("CompraMateriaPrima")}
    if "TotalCompra" in columnas_compra:
        op.drop_column("CompraMateriaPrima", "TotalCompra")

    columnas_compra_detalle = {
        columna["name"] for columna in inspector.get_columns("CompraMateriaPrimaDetalle")
    }
    if "Subtotal" in columnas_compra_detalle:
        op.drop_column("CompraMateriaPrimaDetalle", "Subtotal")

    columnas_producto = {columna["name"] for columna in inspector.get_columns("ProductoTerminado")}
    if "CostoProduccion" in columnas_producto:
        op.drop_column("ProductoTerminado", "CostoProduccion")

    columnas_venta = {columna["name"] for columna in inspector.get_columns("Venta")}
    if "TotalVenta" in columnas_venta:
        op.drop_column("Venta", "TotalVenta")

    columnas_venta_detalle = {columna["name"] for columna in inspector.get_columns("VentaDetalle")}
    if "Subtotal" in columnas_venta_detalle:
        op.drop_column("VentaDetalle", "Subtotal")

    columnas_corte = {columna["name"] for columna in inspector.get_columns("CorteVentaDiario")}
    if "TotalVentas" in columnas_corte:
        op.drop_column("CorteVentaDiario", "TotalVentas")
    if "TotalCosto" in columnas_corte:
        op.drop_column("CorteVentaDiario", "TotalCosto")
    if "UtilidadDiaria" in columnas_corte:
        op.drop_column("CorteVentaDiario", "UtilidadDiaria")

    _recrear_sp_ventas_registrar(bind)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columnas_compra = {columna["name"] for columna in inspector.get_columns("CompraMateriaPrima")}
    if "TotalCompra" not in columnas_compra:
        op.add_column(
            "CompraMateriaPrima",
            sa.Column("TotalCompra", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        )
        bind.execute(
            sa.text(
                """
                UPDATE CompraMateriaPrima c
                SET TotalCompra = COALESCE(
                    (
                        SELECT SUM(Cantidad * CostoUnitario)
                        FROM CompraMateriaPrimaDetalle d
                        WHERE d.IdCompraMateriaPrima = c.IdCompraMateriaPrima
                    ),
                    0
                )
                """
            )
        )

    columnas_compra_detalle = {
        columna["name"] for columna in inspector.get_columns("CompraMateriaPrimaDetalle")
    }
    if "Subtotal" not in columnas_compra_detalle:
        op.add_column(
            "CompraMateriaPrimaDetalle",
            sa.Column("Subtotal", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        )
        bind.execute(
            sa.text("UPDATE CompraMateriaPrimaDetalle SET Subtotal = Cantidad * CostoUnitario")
        )

    columnas_producto = {columna["name"] for columna in inspector.get_columns("ProductoTerminado")}
    if "CostoProduccion" not in columnas_producto:
        op.add_column(
            "ProductoTerminado",
            sa.Column("CostoProduccion", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        )

    columnas_venta = {columna["name"] for columna in inspector.get_columns("Venta")}
    if "TotalVenta" not in columnas_venta:
        op.add_column(
            "Venta",
            sa.Column("TotalVenta", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        )
        bind.execute(
            sa.text(
                """
                UPDATE Venta v
                SET TotalVenta = COALESCE(
                    (
                        SELECT SUM(Cantidad * PrecioUnitario)
                        FROM VentaDetalle d
                        WHERE d.IdVenta = v.IdVenta
                    ),
                    0
                )
                """
            )
        )

    columnas_venta_detalle = {columna["name"] for columna in inspector.get_columns("VentaDetalle")}
    if "Subtotal" not in columnas_venta_detalle:
        op.add_column(
            "VentaDetalle",
            sa.Column("Subtotal", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        )
        bind.execute(sa.text("UPDATE VentaDetalle SET Subtotal = Cantidad * PrecioUnitario"))

    columnas_corte = {columna["name"] for columna in inspector.get_columns("CorteVentaDiario")}
    if "TotalVentas" not in columnas_corte:
        op.add_column(
            "CorteVentaDiario",
            sa.Column("TotalVentas", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        )
    if "TotalCosto" not in columnas_corte:
        op.add_column(
            "CorteVentaDiario",
            sa.Column("TotalCosto", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        )
    if "UtilidadDiaria" not in columnas_corte:
        op.add_column(
            "CorteVentaDiario",
            sa.Column("UtilidadDiaria", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        )

    _drop_procedure(bind, "SP_Ventas_Registrar")
