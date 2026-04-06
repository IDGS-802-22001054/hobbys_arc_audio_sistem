import json

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from models import db


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
