"""create sp ventas registrar

Revision ID: c7e2a1d4f9b3
Revises: b4c1a2d9e6f0
Create Date: 2026-04-05 21:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c7e2a1d4f9b3"
down_revision = "b4c1a2d9e6f0"
branch_labels = None
depends_on = None


def _drop_procedure(bind, name):
    bind.execute(sa.text(f"DROP PROCEDURE IF EXISTS {name}"))


def _crear_procedimiento(bind, sql):
    bind.execute(sa.text(sql))


def upgrade():
    bind = op.get_bind()
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

            INSERT INTO Venta (IdCliente, TotalVenta, MetodoPago, IdUsuarioRegistro)
            VALUES (p_IdCliente, 0, p_MetodoPago, p_IdUsuarioRegistro);

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
                    PrecioUnitario,
                    Subtotal
                )
                VALUES (
                    v_IdVenta,
                    v_ProductoId,
                    v_Cantidad,
                    v_Precio,
                    v_Subtotal
                );

                UPDATE ProductoTerminado
                SET StockActual = StockActual - v_Cantidad
                WHERE IdProductoTerminado = v_ProductoId;

                SET v_Index = v_Index + 1;
            END WHILE;

            UPDATE Venta
            SET TotalVenta = v_Total
            WHERE IdVenta = v_IdVenta;

            COMMIT;

            SELECT v_IdVenta AS IdVenta, v_Total AS TotalVenta;
        END
        """,
    )


def downgrade():
    bind = op.get_bind()
    _drop_procedure(bind, "SP_Ventas_Registrar")
