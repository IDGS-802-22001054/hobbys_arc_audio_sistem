"""recreate sp produccion registrar defecto

Revision ID: 4e1a9c7b2d11
Revises: 9e7c1a2b4f10
Create Date: 2026-04-15 14:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4e1a9c7b2d11"
down_revision = "9e7c1a2b4f10"
branch_labels = None
depends_on = None


def _drop_procedure(bind, name):
    bind.execute(sa.text(f"DROP PROCEDURE IF EXISTS {name}"))


def _crear_procedimiento(bind, sql):
    bind.execute(sa.text(sql))


def _recrear_sp_produccion_registrar_defecto(bind):
    _drop_procedure(bind, "SP_Produccion_RegistrarDefecto")
    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Produccion_RegistrarDefecto(
            IN p_id_produccion INT,
            IN p_cantidad INT,
            IN p_descripcion VARCHAR(255),
            IN p_id_usuario INT
        )
        BEGIN
            DECLARE v_existe INT DEFAULT 0;
            DECLARE v_id_producto_terminado INT;
            DECLARE v_estado VARCHAR(50);
            DECLARE v_done INT DEFAULT 0;
            DECLARE v_id_materia_prima INT;
            DECLARE v_consumo_unitario DECIMAL(18, 2);
            DECLARE v_consumo_total DECIMAL(18, 2);
            DECLARE v_stock_actual DECIMAL(18, 2);
            DECLARE v_costo_unitario DECIMAL(18, 2);

            DECLARE cur_receta CURSOR FOR
                SELECT
                    rd.IdMateriaPrima,
                    COALESCE(rd.CantidadRequerida, 0) + COALESCE(rd.Merma, 0) AS ConsumoUnitario
                FROM RecetaDetalle rd
                WHERE rd.IdProductoTerminado = v_id_producto_terminado;

            DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

            DECLARE EXIT HANDLER FOR SQLEXCEPTION
            BEGIN
                ROLLBACK;
                RESIGNAL;
            END;

            IF p_id_produccion IS NULL OR p_id_produccion <= 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'La produccion enviada no es valida.';
            END IF;

            IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'La cantidad defectuosa debe ser mayor a cero.';
            END IF;

            IF p_id_usuario IS NULL OR p_id_usuario <= 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'El usuario que registra el defecto no es valido.';
            END IF;

            START TRANSACTION;

            SELECT COUNT(*)
            INTO v_existe
            FROM Produccion
            WHERE IdProduccion = p_id_produccion;

            IF v_existe = 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'La produccion indicada no existe.';
            END IF;

            SELECT IdProductoTerminado, Estado
            INTO v_id_producto_terminado, v_estado
            FROM Produccion
            WHERE IdProduccion = p_id_produccion
            FOR UPDATE;

            IF v_estado <> 'En proceso' THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Solo se pueden registrar defectos en producciones en proceso.';
            END IF;

            SELECT COUNT(*)
            INTO v_existe
            FROM RecetaDetalle
            WHERE IdProductoTerminado = v_id_producto_terminado;

            IF v_existe = 0 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'El producto de la produccion no tiene receta configurada.';
            END IF;

            SET v_done = 0;
            OPEN cur_receta;

            bucle_receta: LOOP
                FETCH cur_receta INTO v_id_materia_prima, v_consumo_unitario;

                IF v_done = 1 THEN
                    LEAVE bucle_receta;
                END IF;

                SET v_consumo_total = v_consumo_unitario * p_cantidad;

                SELECT StockActual, COALESCE(PrecioUnitario, 0)
                INTO v_stock_actual, v_costo_unitario
                FROM MateriaPrima
                WHERE IdMateriaPrima = v_id_materia_prima
                FOR UPDATE;

                IF v_stock_actual < v_consumo_total THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'Stock insuficiente de materia prima para registrar la pieza defectuosa.';
                END IF;

                UPDATE MateriaPrima
                SET StockActual = StockActual - v_consumo_total
                WHERE IdMateriaPrima = v_id_materia_prima;

                INSERT INTO MovimientoMateriaPrima (
                    IdMateriaPrima,
                    TipoMovimiento,
                    Cantidad,
                    CostoUnitario,
                    FechaMovimiento,
                    Motivo,
                    IdUsuario
                )
                VALUES (
                    v_id_materia_prima,
                    'SALIDA',
                    v_consumo_total,
                    v_costo_unitario,
                    NOW(),
                    CONCAT('Consumo por registro de defecto en produccion #', p_id_produccion),
                    p_id_usuario
                );
            END LOOP;

            CLOSE cur_receta;

            INSERT INTO ProduccionDefectuosa (
                IdProduccion,
                CantidadDefectuosa,
                FechaRegistro,
                Descripcion
            )
            VALUES (
                p_id_produccion,
                p_cantidad,
                NOW(),
                p_descripcion
            );

            UPDATE Produccion
            SET CantidadDefectuosa = COALESCE(CantidadDefectuosa, 0) + p_cantidad
            WHERE IdProduccion = p_id_produccion;

            COMMIT;
        END
        """,
    )


def upgrade():
    bind = op.get_bind()
    _recrear_sp_produccion_registrar_defecto(bind)


def downgrade():
    bind = op.get_bind()
    _drop_procedure(bind, "SP_Produccion_RegistrarDefecto")
    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Produccion_RegistrarDefecto(
            IN p_id_produccion INT,
            IN p_cantidad INT,
            IN p_descripcion VARCHAR(255),
            IN p_id_usuario INT
        )
        BEGIN
            INSERT INTO ProduccionDefectuosa
                (IdProduccion, CantidadDefectuosa, FechaRegistro, Descripcion)
            VALUES
                (p_id_produccion, p_cantidad, NOW(), p_descripcion);

            UPDATE Produccion
               SET CantidadDefectuosa = CantidadDefectuosa + p_cantidad
             WHERE IdProduccion = p_id_produccion;
        END
        """,
    )
