from base64 import b64encode
from decimal import Decimal

from flask import current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from models import Cliente, ProductoTerminado, Usuario, Venta, VentaDetalle, db

from . import catalogo_cliente_bp

COLORES_TARJETA = ("red", "yellow", "green", "blue")
CLAVE_CARRITO = "catalogo_cliente_carrito"


def _mime_imagen(contenido):
    if contenido.startswith(b"\x89PNG"):
        return "image/png"
    if contenido.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if contenido.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if contenido.startswith(b"RIFF") and contenido[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _imagen_a_data_url(contenido):
    if not contenido:
        return None
    mime = _mime_imagen(contenido)
    return f"data:{mime};base64,{b64encode(contenido).decode('ascii')}"


def _precio_decimal(valor):
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


def _normalizar_carrito():
    bruto = session.get(CLAVE_CARRITO, {})
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

    if bruto != {str(producto_id): cantidad for producto_id, cantidad in carrito.items()}:
        _guardar_carrito(carrito)

    return carrito


def _guardar_carrito(carrito):
    session[CLAVE_CARRITO] = {
        str(producto_id): int(cantidad)
        for producto_id, cantidad in carrito.items()
        if int(cantidad) > 0
    }
    session.modified = True


def _url_catalogo(busqueda=""):
    if busqueda:
        return url_for("catalogo_cliente.catalogo", q=busqueda)
    return url_for("catalogo_cliente.catalogo")


def _serializar_producto(producto, indice):
    return {
        "id": producto.IdProductoTerminado,
        "nombre": producto.Nombre,
        "descripcion": producto.Descripcion or "Sin descripcion disponible.",
        "precio": _precio_decimal(producto.PrecioVenta),
        "stock": int(producto.StockActual or 0),
        "imagen": _imagen_a_data_url(producto.Foto),
        "color": COLORES_TARJETA[indice % len(COLORES_TARJETA)],
    }


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
    return [_serializar_producto(producto, indice) for indice, producto in enumerate(productos)]


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


def _obtener_usuario_registro():
    usuario_id = current_app.config.get("CATALOGO_USUARIO_REGISTRO_ID")
    if usuario_id:
        usuario = db.session.get(Usuario, usuario_id)
        if usuario and usuario.Activo:
            return usuario

    consulta = (
        select(Usuario)
        .where(Usuario.Activo.is_(True))
        .order_by(Usuario.IdUsuario.asc())
        .limit(1)
    )
    return db.session.execute(consulta).scalar_one_or_none()


def _obtener_cliente_configurado():
    cliente_id = current_app.config.get("CATALOGO_CLIENTE_ID")
    if not cliente_id:
        return None
    return db.session.get(Cliente, cliente_id)


def obtener_contexto_catalogo(busqueda=""):
    try:
        productos = _obtener_productos(busqueda)
        carrito, resumen = _obtener_detalle_carrito()
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible cargar el catalogo desde la base de datos.")
        productos = []
        carrito = []
        resumen = {"subtotal": Decimal("0.00"), "total": Decimal("0.00"), "cantidad_total": 0}
        flash("No fue posible cargar el catalogo desde la base de datos.", "error")

    return {
        "productos": productos,
        "carrito": carrito,
        "resumen": resumen,
        "busqueda": busqueda,
        "active": "catalogo",
        "usuario_iniciales": "RC",
    }


@catalogo_cliente_bp.route("/catalogo")
def catalogo():
    busqueda = request.args.get("q", "").strip()
    return render_template("catalogo/catalogo.html", **obtener_contexto_catalogo(busqueda))


@catalogo_cliente_bp.post("/catalogo/carrito/agregar")
def agregar_al_carrito():
    busqueda = request.form.get("q", "").strip()
    producto_id = request.form.get("producto_id", type=int)

    if not producto_id:
        flash("Producto invalido.", "error")
        return redirect(_url_catalogo(busqueda))

    try:
        producto = db.session.get(ProductoTerminado, producto_id)
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible consultar el producto %s.", producto_id)
        flash("No fue posible agregar el producto al carrito.", "error")
        return redirect(_url_catalogo(busqueda))

    if producto is None or not producto.Activo:
        flash("El producto seleccionado no esta disponible.", "error")
        return redirect(_url_catalogo(busqueda))

    stock_disponible = max(int(producto.StockActual or 0), 0)
    if stock_disponible <= 0:
        flash("El producto no tiene stock disponible.", "error")
        return redirect(_url_catalogo(busqueda))

    carrito = _normalizar_carrito()
    cantidad_actual = carrito.get(producto_id, 0)
    if cantidad_actual >= stock_disponible:
        flash("Ya agregaste el maximo disponible en stock.", "error")
        return redirect(_url_catalogo(busqueda))

    carrito[producto_id] = cantidad_actual + 1
    _guardar_carrito(carrito)
    flash(f"{producto.Nombre} se agrego al carrito.", "success")
    return redirect(_url_catalogo(busqueda))


@catalogo_cliente_bp.post("/catalogo/carrito/actualizar")
def actualizar_carrito():
    busqueda = request.form.get("q", "").strip()
    producto_id = request.form.get("producto_id", type=int)
    accion = request.form.get("accion", "").strip().lower()

    carrito = _normalizar_carrito()
    if not producto_id or producto_id not in carrito:
        flash("No se encontro el producto dentro del carrito.", "error")
        return redirect(_url_catalogo(busqueda))

    if accion == "eliminar":
        carrito.pop(producto_id, None)
        _guardar_carrito(carrito)
        flash("Producto eliminado del carrito.", "success")
        return redirect(_url_catalogo(busqueda))

    try:
        producto = db.session.get(ProductoTerminado, producto_id)
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible actualizar el carrito.")
        flash("No fue posible actualizar el carrito.", "error")
        return redirect(_url_catalogo(busqueda))

    if producto is None or not producto.Activo:
        carrito.pop(producto_id, None)
        _guardar_carrito(carrito)
        flash("El producto ya no esta disponible.", "error")
        return redirect(_url_catalogo(busqueda))

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

    return redirect(_url_catalogo(busqueda))


@catalogo_cliente_bp.post("/catalogo/compra")
def realizar_compra():
    busqueda = request.form.get("q", "").strip()
    carrito = _normalizar_carrito()

    if not carrito:
        flash("Tu carrito esta vacio.", "error")
        return redirect(_url_catalogo(busqueda))

    try:
        usuario = _obtener_usuario_registro()
        if usuario is None:
            flash("No hay un usuario disponible para registrar la venta.", "error")
            return redirect(_url_catalogo(busqueda))

        cliente = _obtener_cliente_configurado()
        consulta = (
            select(ProductoTerminado)
            .where(ProductoTerminado.IdProductoTerminado.in_(carrito.keys()))
            .with_for_update()
        )
        productos = {
            producto.IdProductoTerminado: producto
            for producto in db.session.execute(consulta).scalars().all()
        }

        venta = Venta(
            IdCliente=cliente.IdCliente if cliente else None,
            TotalVenta=Decimal("0.00"),
            IdUsuarioRegistro=usuario.IdUsuario,
        )
        db.session.add(venta)
        db.session.flush()

        total = Decimal("0.00")
        for producto_id, cantidad in carrito.items():
            producto = productos.get(producto_id)
            if producto is None or not producto.Activo:
                raise ValueError("Uno de los productos del carrito ya no esta disponible.")

            stock_disponible = max(int(producto.StockActual or 0), 0)
            if cantidad > stock_disponible:
                raise ValueError(f"Stock insuficiente para {producto.Nombre}.")

            precio = _precio_decimal(producto.PrecioVenta)
            subtotal = precio * cantidad
            total += subtotal
            producto.StockActual = stock_disponible - cantidad

            db.session.add(
                VentaDetalle(
                    IdVenta=venta.IdVenta,
                    IdProductoTerminado=producto.IdProductoTerminado,
                    Cantidad=cantidad,
                    PrecioUnitario=precio,
                    Subtotal=subtotal,
                )
            )

        venta.TotalVenta = total
        db.session.commit()
        _guardar_carrito({})
        flash("Compra registrada correctamente.", "success")
    except ValueError as error:
        db.session.rollback()
        flash(str(error), "error")
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("No fue posible registrar la compra.")
        flash("No fue posible registrar la compra en la base de datos.", "error")

    return redirect(_url_catalogo(busqueda))


@catalogo_cliente_bp.route("/layout")
def layout():
    return render_template(
        "layout_cli.html",
        active=None,
        usuario_iniciales="RC",
    )
