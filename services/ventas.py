import json

import pymysql
from flask import current_app
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine.url import make_url

from models import ProductoTerminado, Venta, VentaDetalle, db


def _mensaje_sql(error):
    original = getattr(error, "orig", None)
    args = getattr(original, "args", None)
    if isinstance(args, (list, tuple)) and len(args) >= 2:
        return str(args[1])
    if isinstance(args, (list, tuple)) and len(args) == 1:
        return str(args[0])
    return str(error)


def _conexion_procedimiento_privilegiada():
    url = make_url(current_app.config["SQLALCHEMY_DATABASE_URI"])
    usuario = current_app.config.get("MYSQL_FALLBACK_DB_USER", "admin_app")
    password = current_app.config.get("MYSQL_ROLE_DB_PASSWORD", "Cont5445")

    return pymysql.connect(
        host=url.host or "localhost",
        port=int(url.port or 3306),
        user=usuario,
        password=password,
        database=url.database,
        charset="utf8mb4",
        autocommit=False,
    )


def _activar_rol_privilegiado(cursor):
    rol = (current_app.config.get("MYSQL_FALLBACK_ROLE") or "Administrador").replace("`", "").strip()
    if rol:
        cursor.execute(f"SET ROLE `{rol}`")


def _fila_a_dict(fila, columnas):
    if fila is None:
        return None

    if isinstance(fila, dict):
        return fila

    if hasattr(fila, "keys"):
        return {columna: fila[columna] for columna in columnas}

    if isinstance(fila, (list, tuple)):
        return {columnas[indice]: fila[indice] for indice in range(min(len(columnas), len(fila)))}

    return {columnas[0]: fila}


def _obtener_productos_privilegiado(cursor, producto_ids):
    if not producto_ids:
        return {}

    placeholders = ",".join(["%s"] * len(producto_ids))
    cursor.execute(
        f"""
        SELECT IdProductoTerminado, PrecioVenta, Activo
        FROM ProductoTerminado
        WHERE IdProductoTerminado IN ({placeholders})
        """,
        tuple(int(producto_id) for producto_id in producto_ids),
    )

    productos = {}
    for fila in cursor.fetchall():
        datos = _fila_a_dict(fila, ["IdProductoTerminado", "PrecioVenta", "Activo"])
        productos[int(datos["IdProductoTerminado"])] = datos
    return productos


def _crear_venta_privilegiada(cursor, id_cliente, metodo_pago, id_usuario):
    cursor.execute(
        """
        INSERT INTO Venta (IdCliente, MetodoPago, IdUsuarioRegistro)
        VALUES (%s, %s, %s)
        """,
        (int(id_cliente), metodo_pago, int(id_usuario)),
    )
    return int(cursor.lastrowid)


def _registrar_venta_por_procedimiento_privilegiado(cursor, id_cliente, id_usuario, metodo_pago, carrito):
    detalles = [
        {"producto_id": int(producto_id), "cantidad": int(cantidad)}
        for producto_id, cantidad in carrito.items()
    ]
    cursor.execute(
        """
        CALL SP_Ventas_Registrar(
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            int(id_cliente),
            int(id_usuario),
            metodo_pago,
            json.dumps(detalles, ensure_ascii=True),
        ),
    )
    fila = cursor.fetchone()
    while cursor.nextset():
        pass
    return _obtener_id_venta(fila)


def registrar_venta_por_procedimiento(id_cliente, id_usuario, metodo_pago, carrito):
    carrito = _normalizar_carrito(carrito)
    if not carrito:
        raise ValueError("La venta requiere al menos un detalle valido.")

    conexion = None
    try:
        conexion = _conexion_procedimiento_privilegiada()
        with conexion.cursor() as cursor:
            _activar_rol_privilegiado(cursor)
            id_venta = _registrar_venta_por_procedimiento_privilegiado(
                cursor=cursor,
                id_cliente=id_cliente,
                id_usuario=id_usuario,
                metodo_pago=metodo_pago,
                carrito=carrito,
            )
        conexion.commit()
        return db.session.get(Venta, id_venta)
    except (SQLAlchemyError, pymysql.MySQLError) as error:
        if conexion is not None:
            conexion.rollback()
        mensaje = _mensaje_sql(error)
        raise ValueError(mensaje) from error
    finally:
        if conexion is not None:
            conexion.close()


def _normalizar_carrito(carrito):
    return {
        int(producto_id): int(cantidad)
        for producto_id, cantidad in (carrito or {}).items()
        if int(producto_id) > 0 and int(cantidad) > 0
    }


def _obtener_id_venta(fila):
    if fila is None:
        raise ValueError("La venta no devolvio un identificador valido.")

    mapping = getattr(fila, "_mapping", None)
    if mapping and "IdVenta" in mapping:
        return int(mapping["IdVenta"])

    id_venta = getattr(fila, "IdVenta", None)
    if id_venta is not None:
        return int(id_venta)

    if isinstance(fila, (list, tuple)) and fila:
        return int(fila[0])

    raise ValueError("La venta no devolvio un identificador valido.")


def _sincronizar_detalles_venta_privilegiado(cursor, id_venta, carrito_total):
    productos = _obtener_productos_privilegiado(cursor, carrito_total.keys())

    cursor.execute(
        """
        SELECT IdProductoTerminado, Cantidad, PrecioUnitario
        FROM VentaDetalle
        WHERE IdVenta = %s
        """,
        (int(id_venta),),
    )
    detalles_existentes = {}
    for fila in cursor.fetchall():
        datos = _fila_a_dict(fila, ["IdProductoTerminado", "Cantidad", "PrecioUnitario"])
        detalles_existentes[int(datos["IdProductoTerminado"])] = datos

    for producto_id, cantidad_total in carrito_total.items():
        producto = productos.get(producto_id)
        if producto is None or not bool(producto["Activo"]):
            raise ValueError("Uno de los productos enviados ya no esta disponible.")

        detalle = detalles_existentes.get(producto_id)
        if detalle is None:
            cursor.execute(
                """
                INSERT INTO VentaDetalle (IdVenta, IdProductoTerminado, Cantidad, PrecioUnitario)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    int(id_venta),
                    int(producto_id),
                    int(cantidad_total),
                    producto["PrecioVenta"],
                ),
            )
            continue

        cursor.execute(
            """
            UPDATE VentaDetalle
            SET Cantidad = %s, PrecioUnitario = %s
            WHERE IdVenta = %s AND IdProductoTerminado = %s
            """,
            (
                int(cantidad_total),
                producto["PrecioVenta"],
                int(id_venta),
                int(producto_id),
            ),
        )


def registrar_venta_catalogo_cliente(
    id_cliente,
    id_usuario,
    metodo_pago,
    carrito_total,
    carrito_con_stock=None,
):
    carrito_total = _normalizar_carrito(carrito_total)
    carrito_con_stock = _normalizar_carrito(carrito_con_stock)

    if not carrito_total:
        raise ValueError("La venta requiere al menos un detalle valido.")

    conexion = None
    try:
        conexion = _conexion_procedimiento_privilegiada()
        with conexion.cursor() as cursor:
            _activar_rol_privilegiado(cursor)

            if carrito_con_stock:
                id_venta = _registrar_venta_por_procedimiento_privilegiado(
                    cursor=cursor,
                    id_cliente=id_cliente,
                    id_usuario=id_usuario,
                    metodo_pago=metodo_pago,
                    carrito=carrito_con_stock,
                )
            else:
                id_venta = _crear_venta_privilegiada(
                    cursor=cursor,
                    id_cliente=id_cliente,
                    metodo_pago=metodo_pago,
                    id_usuario=id_usuario,
                )

            _sincronizar_detalles_venta_privilegiado(cursor, id_venta, carrito_total)

        conexion.commit()
        return db.session.get(Venta, id_venta)
    except (SQLAlchemyError, pymysql.MySQLError) as error:
        if conexion is not None:
            conexion.rollback()
        mensaje = _mensaje_sql(error)
        raise ValueError(mensaje) from error
    finally:
        if conexion is not None:
            conexion.close()
