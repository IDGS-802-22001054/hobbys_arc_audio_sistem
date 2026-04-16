from decimal import Decimal

from collections import OrderedDict

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, select, text

from models import Cliente, Persona, ProductoTerminado, SolicitudProduccion, db
from services.ventas import registrar_venta_por_procedimiento

from . import ventas_bp

CLAVE_CARRITO_VENTAS = "ventas_mostrador_carrito"
CORREO_CLIENTE_MOSTRADOR = "venta.mostrador@arc-audio.local"
ROLES_VENTAS = {"administrador", "vendedor"}


def _rol_actual():
    return (getattr(getattr(current_user, "rol", None), "Nombre", "") or "").lower().strip()


def _usuario_puede_vender():
    return _rol_actual() in ROLES_VENTAS


def _precio_decimal(valor):
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


def _guardar_carrito(carrito):
    session[CLAVE_CARRITO_VENTAS] = {
        str(producto_id): int(cantidad)
        for producto_id, cantidad in carrito.items()
        if int(cantidad) > 0
    }
    session.modified = True


def _normalizar_carrito():
    bruto = session.get(CLAVE_CARRITO_VENTAS, {})
    carrito = {}

    if isinstance(bruto, dict):
        for producto_id, cantidad in bruto.items():
            try:
                producto_id_int = int(producto_id)
                cantidad_int = int(cantidad)
            except (TypeError, ValueError):
                continue

            if producto_id_int > 0 and cantidad_int > 0:
                carrito[producto_id_int] = cantidad_int

    serializado = {str(producto_id): cantidad for producto_id, cantidad in carrito.items()}
    if bruto != serializado:
        _guardar_carrito(carrito)

    return carrito


def _url_ventas(busqueda=""):
    if busqueda:
        return url_for("ventas.ventas", q=busqueda)
    return url_for("ventas.ventas")


def _serializar_producto(producto):
    return {
        "id": producto.IdProductoTerminado,
        "nombre": producto.Nombre,
        "descripcion": producto.Descripcion or "Sin descripcion disponible.",
        "precio": _precio_decimal(producto.PrecioVenta),
        "stock": int(producto.StockActual or 0),
    }


def _solicitud_pendiente_producto(producto_id):
    return (
        db.session.query(SolicitudProduccion.IdSolicitudProduccion)
        .filter_by(IdProductoTerminado=producto_id, Estado="PENDIENTE")
        .first()
    )


def _obtener_productos(busqueda=""):
    consulta = select(ProductoTerminado).where(ProductoTerminado.Activo.is_(True))

    if busqueda:
        criterio = f"%{busqueda}%"
        consulta = consulta.where(
            or_(
                ProductoTerminado.Nombre.ilike(criterio),
                ProductoTerminado.Descripcion.ilike(criterio),
            )
        )

    consulta = consulta.order_by(ProductoTerminado.Nombre.asc())
    productos = db.session.execute(consulta).scalars().all()
    return [_serializar_producto(producto) for producto in productos]


def _obtener_detalle_carrito():
    carrito = _normalizar_carrito()
    if not carrito:
        return [], {"subtotal": Decimal("0.00"), "total": Decimal("0.00"), "cantidad_total": 0}

    consulta = select(ProductoTerminado).where(
        ProductoTerminado.IdProductoTerminado.in_(carrito.keys())
    )
    productos = {
        producto.IdProductoTerminado: producto
        for producto in db.session.execute(consulta).scalars().all()
    }

    lineas = []
    subtotal = Decimal("0.00")
    cantidad_total = 0
    carrito_actualizado = {}

    for producto_id, cantidad_solicitada in carrito.items():
        producto = productos.get(producto_id)
        if producto is None or not producto.Activo:
            continue

        stock_disponible = max(int(producto.StockActual or 0), 0)
        cantidad = min(cantidad_solicitada, stock_disponible)
        if cantidad <= 0:
            continue

        carrito_actualizado[producto_id] = cantidad
        precio = _precio_decimal(producto.PrecioVenta)
        subtotal_linea = precio * cantidad
        subtotal += subtotal_linea
        cantidad_total += cantidad

        lineas.append(
            {
                "id": producto.IdProductoTerminado,
                "nombre": producto.Nombre,
                "cantidad": cantidad,
                "precio": precio,
                "subtotal": subtotal_linea,
                "stock": stock_disponible,
            }
        )

    if carrito_actualizado != carrito:
        _guardar_carrito(carrito_actualizado)

    return lineas, {
        "subtotal": subtotal,
        "total": subtotal,
        "cantidad_total": cantidad_total,
    }


def _obtener_clientes():
    consulta = (
        select(Cliente)
        .join(Persona, Cliente.IdPersona == Persona.IdPersona)
        .where(Persona.Activo.is_(True))
        .where(Persona.CorreoElectronico != CORREO_CLIENTE_MOSTRADOR)
        .order_by(Persona.Nombre.asc(), Persona.Apellidos.asc())
    )
    clientes = db.session.execute(consulta).scalars().all()
    opciones = []
    for cliente in clientes:
        persona = cliente.persona
        if persona is None:
            continue
        opciones.append(
            {
                "id": cliente.IdCliente,
                "nombre": f"{persona.Nombre} {persona.Apellidos}",
                "correo": persona.CorreoElectronico or "",
            }
        )
    return opciones


def _obtener_cliente_mostrador():
    consulta = (
        select(Cliente)
        .join(Persona, Cliente.IdPersona == Persona.IdPersona)
        .where(Persona.CorreoElectronico == CORREO_CLIENTE_MOSTRADOR)
        .limit(1)
    )
    return db.session.execute(consulta).scalar_one_or_none()


def _contexto_ventas(busqueda="", cliente_id="", metodo_pago="EFECTIVO", tipo_cliente="MOSTRADOR"):
    carrito, resumen = _obtener_detalle_carrito()
    cliente_mostrador = _obtener_cliente_mostrador()
    return {
        "productos": _obtener_productos(busqueda),
        "carrito": carrito,
        "resumen": resumen,
        "clientes": _obtener_clientes(),
        "cliente_mostrador": cliente_mostrador,
        "busqueda": busqueda,
        "cliente_id": str(cliente_id or ""),
        "metodo_pago": metodo_pago or "EFECTIVO",
        "tipo_cliente": (tipo_cliente or "MOSTRADOR").upper(),
        "active": "ventas",
    }


def _obtener_historial_ventas(busqueda=""):
    filas = db.session.execute(
        text("CALL SP_Ventas_Historial(:busqueda)"),
        {"busqueda": busqueda or None},
    ).fetchall()

    ventas = OrderedDict()
    for fila in filas:
        venta = ventas.setdefault(
            fila.IdVenta,
            {
                "IdVenta": fila.IdVenta,
                "FechaVenta": fila.FechaVenta,
                "MetodoPago": fila.MetodoPago,
                "TotalVenta": _precio_decimal(fila.TotalVenta),
                "cliente": {
                    "persona": {
                        "Nombre": fila.NombreCliente or "No disponible",
                        "Apellidos": "",
                    }
                },
                "detalles": [],
            },
        )

        if fila.IdVentaDetalle is None:
            continue

        venta["detalles"].append(
            {
                "IdVentaDetalle": fila.IdVentaDetalle,
                "Cantidad": int(fila.Cantidad or 0),
                "PrecioUnitario": _precio_decimal(fila.PrecioUnitario),
                "Subtotal": _precio_decimal(fila.Subtotal),
                "producto_terminado": {
                    "Nombre": fila.NombreProducto or "Producto no disponible",
                },
            }
        )

    return list(ventas.values())


@ventas_bp.before_request
@login_required
def proteger_ventas():
    if not _usuario_puede_vender():
        abort(403)


@ventas_bp.route("")
@ventas_bp.route("/")
@ventas_bp.route("/mostrador")
def ventas():
    busqueda = request.args.get("q", "").strip()
    return render_template("ventas/punto_venta.html", **_contexto_ventas(busqueda))


@ventas_bp.route("/historial")
def historial():
    busqueda = request.args.get("q", "").strip()
    ventas_registradas = _obtener_historial_ventas(busqueda)
    return render_template(
        "ventas/historial.html",
        ventas=ventas_registradas,
        busqueda=busqueda,
        active="ventas",
    )


@ventas_bp.post("/carrito/agregar")
def agregar_al_carrito():
    busqueda = request.form.get("q", "").strip()
    producto_id = request.form.get("producto_id", type=int)

    if not producto_id:
        flash("Producto invalido.", "error")
        return redirect(_url_ventas(busqueda))

    producto = db.session.get(ProductoTerminado, producto_id)
    if producto is None or not producto.Activo:
        flash("El producto seleccionado no esta disponible.", "error")
        return redirect(_url_ventas(busqueda))

    stock_disponible = max(int(producto.StockActual or 0), 0)
    if stock_disponible <= 0:
        flash("El producto no tiene stock disponible.", "error")
        return redirect(_url_ventas(busqueda))

    carrito = _normalizar_carrito()
    cantidad_actual = carrito.get(producto_id, 0)
    if cantidad_actual >= stock_disponible:
        flash("Ya agregaste el maximo disponible en stock.", "error")
        return redirect(_url_ventas(busqueda))

    carrito[producto_id] = cantidad_actual + 1
    _guardar_carrito(carrito)
    flash(f"{producto.Nombre} se agrego a la venta.", "success")
    return redirect(_url_ventas(busqueda))


@ventas_bp.post("/solicitud-produccion")
def solicitar_produccion():
    busqueda = request.form.get("q", "").strip()
    producto_id = request.form.get("producto_id", type=int)
    cantidad = request.form.get("cantidad", type=int, default=1) or 1

    if not producto_id or cantidad < 1:
        flash("Datos invalidos para la solicitud.", "error")
        return redirect(_url_ventas(busqueda))

    producto = db.session.get(ProductoTerminado, producto_id)
    if producto is None or not producto.Activo:
        flash("El producto seleccionado no esta disponible.", "error")
        return redirect(_url_ventas(busqueda))

    stock_disponible = max(int(producto.StockActual or 0), 0)
    if stock_disponible > 0:
        flash("El producto aun tiene stock disponible. Puedes venderlo directamente.", "warning")
        return redirect(_url_ventas(busqueda))

    if _solicitud_pendiente_producto(producto_id):
        flash("Ya existe una solicitud de produccion pendiente para esta pieza.", "warning")
        return redirect(_url_ventas(busqueda))

    db.session.execute(
        text(
            "CALL SP_SolicitudProduccion_Crear(:id_producto, :cantidad, :motivo, :id_usuario)"
        ),
        {
            "id_producto": producto_id,
            "cantidad": int(cantidad),
            "motivo": f"Solicitud desde punto de venta por pieza agotada: {producto.Nombre}",
            "id_usuario": current_user.IdUsuario,
        },
    )
    db.session.commit()

    flash(
        "Solicitud de produccion generada correctamente. El administrador ya la tiene pendiente para aprobacion.",
        "success",
    )
    return redirect(_url_ventas(busqueda))


@ventas_bp.post("/carrito/actualizar")
def actualizar_carrito():
    busqueda = request.form.get("q", "").strip()
    producto_id = request.form.get("producto_id", type=int)
    accion = (request.form.get("accion") or "").strip().lower()

    carrito = _normalizar_carrito()
    if not producto_id or producto_id not in carrito:
        flash("No se encontro el producto dentro de la venta.", "error")
        return redirect(_url_ventas(busqueda))

    if accion == "eliminar":
        carrito.pop(producto_id, None)
        _guardar_carrito(carrito)
        flash("Producto eliminado de la venta.", "success")
        return redirect(_url_ventas(busqueda))

    producto = db.session.get(ProductoTerminado, producto_id)
    if producto is None or not producto.Activo:
        carrito.pop(producto_id, None)
        _guardar_carrito(carrito)
        flash("El producto ya no esta disponible.", "error")
        return redirect(_url_ventas(busqueda))

    if accion == "sumar":
        stock_disponible = max(int(producto.StockActual or 0), 0)
        if carrito[producto_id] >= stock_disponible:
            flash("No puedes superar el stock disponible.", "error")
        else:
            carrito[producto_id] += 1
            _guardar_carrito(carrito)
    elif accion == "restar":
        nueva_cantidad = carrito[producto_id] - 1
        if nueva_cantidad <= 0:
            carrito.pop(producto_id, None)
        else:
            carrito[producto_id] = nueva_cantidad
        _guardar_carrito(carrito)

    return redirect(_url_ventas(busqueda))


@ventas_bp.post("/registrar")
def registrar_venta():
    busqueda = request.form.get("q", "").strip()
    cliente_id = request.form.get("cliente_id", "").strip()
    metodo_pago = (request.form.get("metodo_pago") or "EFECTIVO").strip().upper()
    tipo_cliente = (request.form.get("tipo_cliente") or "MOSTRADOR").strip().upper()
    carrito = _normalizar_carrito()

    if not carrito:
        flash("No hay productos agregados a la venta.", "error")
        return redirect(_url_ventas(busqueda))

    if metodo_pago not in {"EFECTIVO", "TARJETA"}:
        flash("Selecciona un metodo de pago valido.", "error")
        return render_template(
            "ventas/punto_venta.html",
            **_contexto_ventas(busqueda, cliente_id, metodo_pago, tipo_cliente),
        )

    try:
        if tipo_cliente not in {"MOSTRADOR", "REGISTRADO"}:
            raise ValueError("Selecciona si la venta es a mostrador o para un cliente registrado.")

        if tipo_cliente == "MOSTRADOR":
            cliente = _obtener_cliente_mostrador()
            if cliente is None:
                raise ValueError("No existe el cliente configurado para venta a mostrador.")
        else:
            if not cliente_id:
                raise ValueError("Selecciona un cliente registrado para continuar.")

            try:
                cliente_id_int = int(cliente_id)
            except (TypeError, ValueError) as error:
                raise ValueError("El cliente seleccionado no es valido.") from error

            cliente = db.session.get(Cliente, cliente_id_int)
            if cliente is None:
                raise ValueError("El cliente seleccionado no existe.")

            persona_cliente = getattr(cliente, "persona", None)
            if persona_cliente and persona_cliente.CorreoElectronico == CORREO_CLIENTE_MOSTRADOR:
                raise ValueError("Selecciona un cliente registrado distinto a Venta mostrador.")

        registrar_venta_por_procedimiento(
            id_cliente=cliente.IdCliente,
            id_usuario=current_user.IdUsuario,
            metodo_pago=metodo_pago,
            carrito=carrito,
        )
        _guardar_carrito({})
        flash("Venta registrada correctamente.", "success")
        return redirect(url_for("ventas.ventas"))
    except ValueError as error:
        flash(str(error), "error")
        return render_template(
            "ventas/punto_venta.html",
            **_contexto_ventas(busqueda, cliente_id, metodo_pago, tipo_cliente),
        )
