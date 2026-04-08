import json

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from models import ProductoTerminado, Venta, VentaDetalle, db


def _mensaje_sql(error):
    original = getattr(error, "orig", None)
    args = getattr(original, "args", None)
    if isinstance(args, (list, tuple)) and len(args) >= 2:
        return str(args[1])
    if isinstance(args, (list, tuple)) and len(args) == 1:
        return str(args[0])
    return str(error)


def registrar_venta_por_procedimiento(id_cliente, id_usuario, metodo_pago, carrito):
    detalles = [
        {"producto_id": int(producto_id), "cantidad": int(cantidad)}
        for producto_id, cantidad in carrito.items()
    ]

    try:
        resultado = db.session.execute(
            text(
                """
                CALL SP_Ventas_Registrar(
                    :id_cliente,
                    :id_usuario,
                    :metodo_pago,
                    :detalles
                )
                """
            ),
            {
                "id_cliente": int(id_cliente),
                "id_usuario": int(id_usuario),
                "metodo_pago": metodo_pago,
                "detalles": json.dumps(detalles, ensure_ascii=True),
            },
        )
        fila = resultado.fetchone()
        resultado.close()
        db.session.commit()
        return fila
    except SQLAlchemyError as error:
        db.session.rollback()
        mensaje = _mensaje_sql(error)
        raise ValueError(mensaje) from error


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


def _sincronizar_detalles_venta(id_venta, carrito_total):
    consulta_productos = select(ProductoTerminado).where(
        ProductoTerminado.IdProductoTerminado.in_(carrito_total.keys())
    )
    productos = {
        producto.IdProductoTerminado: producto
        for producto in db.session.execute(consulta_productos).scalars().all()
    }

    detalles_existentes = {
        detalle.IdProductoTerminado: detalle
        for detalle in db.session.execute(
            select(VentaDetalle).where(VentaDetalle.IdVenta == id_venta)
        ).scalars().all()
    }

    for producto_id, cantidad_total in carrito_total.items():
        producto = productos.get(producto_id)
        if producto is None or not producto.Activo:
            raise ValueError("Uno de los productos enviados ya no esta disponible.")

        detalle = detalles_existentes.get(producto_id)
        if detalle is None:
            db.session.add(
                VentaDetalle(
                    IdVenta=id_venta,
                    IdProductoTerminado=producto_id,
                    Cantidad=cantidad_total,
                    PrecioUnitario=producto.PrecioVenta,
                )
            )
            continue

        detalle.Cantidad = cantidad_total
        detalle.PrecioUnitario = producto.PrecioVenta


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

    try:
        if carrito_con_stock:
            fila = registrar_venta_por_procedimiento(
                id_cliente=id_cliente,
                id_usuario=id_usuario,
                metodo_pago=metodo_pago,
                carrito=carrito_con_stock,
            )
            id_venta = _obtener_id_venta(fila)
        else:
            venta = Venta(
                IdCliente=int(id_cliente),
                MetodoPago=metodo_pago,
                IdUsuarioRegistro=int(id_usuario),
            )
            db.session.add(venta)
            db.session.flush()
            id_venta = int(venta.IdVenta)

        _sincronizar_detalles_venta(id_venta, carrito_total)
        db.session.commit()
        return db.session.get(Venta, id_venta)
    except SQLAlchemyError as error:
        db.session.rollback()
        mensaje = _mensaje_sql(error)
        raise ValueError(mensaje) from error
