from base64 import b64encode
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from models import MateriaPrima, ProductoTerminado, Receta, RecetaDetalle, Usuario, db

from . import stock_empleado_bp

COLORES_STOCK = ("blue", "green", "yellow", "red")
TIPOS_IMAGEN_PERMITIDOS = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
}


def _mime_imagen(contenido):
    if not contenido:
        return None
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
    mime = _mime_imagen(contenido)
    if not mime:
        return None
    return f"data:{mime};base64,{b64encode(contenido).decode('ascii')}"


def _decimal(valor):
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


def _contexto_base():
    return {"active": "stock"}


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


def _serializar_producto(producto, indice=0):
    tiene_receta = bool(producto.receta and producto.receta.Activa)
    return {
        "id": producto.IdProductoTerminado,
        "nombre": producto.Nombre,
        "descripcion": producto.Descripcion or "Sin descripcion disponible.",
        "costo_produccion": _decimal(producto.CostoProduccion),
        "precio_venta": _decimal(producto.PrecioVenta),
        "stock_actual": int(producto.StockActual or 0),
        "stock_minimo": int(producto.StockMinimo or 0),
        "activo": bool(producto.Activo),
        "imagen": _imagen_a_data_url(producto.Foto),
        "color": COLORES_STOCK[indice % len(COLORES_STOCK)],
        "tiene_receta": tiene_receta,
    }


def _producto_vacio():
    return {
        "id": None,
        "nombre": "",
        "descripcion": "",
        "costo_produccion": Decimal("0.00"),
        "precio_venta": Decimal("0.00"),
        "stock_actual": 0,
        "stock_minimo": 0,
        "activo": True,
        "imagen": None,
        "color": COLORES_STOCK[0],
    }


def _serializar_detalle_receta(detalle):
    unidad = ""
    if detalle.materia_prima and detalle.materia_prima.unidad_medida:
        unidad = detalle.materia_prima.unidad_medida.Abreviatura or ""

    return {
        "id": detalle.IdRecetaDetalle,
        "materia_prima_id": detalle.IdMateriaPrima,
        "materia_prima": detalle.materia_prima.Nombre if detalle.materia_prima else "Materia prima",
        "cantidad": _decimal(detalle.CantidadRequerida),
        "unidad": unidad,
    }


def _obtener_imagen_subida():
    archivo = request.files.get("foto")
    if archivo is None or not archivo.filename:
        return None

    tipo = (archivo.mimetype or "").lower()
    if tipo not in TIPOS_IMAGEN_PERMITIDOS:
        raise ValueError("La imagen debe ser PNG, JPG, GIF o WEBP.")

    contenido = archivo.read()
    if not contenido:
        raise ValueError("La imagen enviada esta vacia.")

    return contenido


def _obtener_contexto_receta(producto, receta=None, detalle_form=None):
    materias = (
        db.session.execute(
            select(MateriaPrima)
            .where(MateriaPrima.Activo.is_(True))
            .order_by(MateriaPrima.Nombre.asc())
        )
        .scalars()
        .all()
    )

    detalles = []
    if receta:
        detalles = [_serializar_detalle_receta(detalle) for detalle in receta.detalles]

    return {
        "producto": _serializar_producto(producto),
        "receta": receta,
        "detalles": detalles,
        "materias_primas": materias,
        "detalle_form": detalle_form or {"materia_prima_id": "", "cantidad": ""},
        **_contexto_base(),
    }


def _calcular_costo_produccion(producto_id):
    detalles = (
        db.session.execute(
            select(RecetaDetalle).where(RecetaDetalle.IdProductoTerminado == producto_id)
        )
        .scalars()
        .all()
    )

    total = Decimal("0.00")
    for detalle in detalles:
        materia_prima = detalle.materia_prima or db.session.get(MateriaPrima, detalle.IdMateriaPrima)
        precio_unitario = _decimal(materia_prima.PrecioUnitario if materia_prima else 0)
        total += _decimal(detalle.CantidadRequerida) * precio_unitario

    return total.quantize(Decimal("0.01"))


@stock_empleado_bp.route("/stock")
def stock():
    busqueda = request.args.get("q", "").strip()
    consulta = select(ProductoTerminado)

    if busqueda:
        criterio = f"%{busqueda}%"
        consulta = consulta.where(
            or_(
                ProductoTerminado.Nombre.ilike(criterio),
                ProductoTerminado.Descripcion.ilike(criterio),
            )
        )

    consulta = consulta.order_by(ProductoTerminado.Activo.desc(), ProductoTerminado.Nombre.asc())
    productos = db.session.execute(consulta).scalars().all()
    productos_serializados = [
        _serializar_producto(producto, indice)
        for indice, producto in enumerate(productos)
    ]

    return render_template(
        "stock/stock.html",
        productos=productos_serializados,
        busqueda=busqueda,
        **_contexto_base(),
    )


@stock_empleado_bp.route("/stock/<int:producto_id>")
def detalle_stock(producto_id):
    producto = db.get_or_404(ProductoTerminado, producto_id)
    return render_template(
        "stock/stock_detalle.html",
        producto=_serializar_producto(producto),
        **_contexto_base(),
    )


@stock_empleado_bp.route("/stock/nuevo", methods=["GET", "POST"])
def nuevo_stock():
    producto_form = _producto_vacio()

    if request.method == "POST":
        accion = request.form.get("accion", "guardar_y_receta")
        nombre = request.form.get("nombre", "").strip()
        descripcion = request.form.get("descripcion", "").strip() or None

        if not nombre:
            flash("El nombre del producto es obligatorio.")
            producto_form.update(
                {
                    "descripcion": descripcion or "",
                    "stock_actual": request.form.get("stock_actual", 0),
                    "stock_minimo": request.form.get("stock_minimo", 0),
                    "precio_venta": request.form.get("precio_venta", 0),
                }
            )
            return render_template(
                "stock/stock_editar.html",
                producto=producto_form,
                modo="nuevo",
                **_contexto_base(),
            )

        try:
            imagen = _obtener_imagen_subida()
        except ValueError as error:
            flash(str(error))
            producto_form.update(
                {
                    "nombre": nombre,
                    "descripcion": descripcion or "",
                    "stock_actual": request.form.get("stock_actual", 0),
                    "stock_minimo": request.form.get("stock_minimo", 0),
                    "precio_venta": request.form.get("precio_venta", 0),
                }
            )
            return render_template(
                "stock/stock_editar.html",
                producto=producto_form,
                modo="nuevo",
                **_contexto_base(),
            )

        try:
            producto = ProductoTerminado(
                Nombre=nombre,
                Descripcion=descripcion,
                StockActual=int(request.form.get("stock_actual", 0)),
                StockMinimo=int(request.form.get("stock_minimo", 0)),
                CostoProduccion=Decimal("0.00"),
                PrecioVenta=_decimal(request.form.get("precio_venta")),
                Foto=imagen,
                Activo=True,
            )
        except (TypeError, ValueError, InvalidOperation):
            flash("Los valores numericos enviados no son validos.")
            producto_form.update(
                {
                    "nombre": nombre,
                    "descripcion": descripcion or "",
                    "stock_actual": request.form.get("stock_actual", 0),
                    "stock_minimo": request.form.get("stock_minimo", 0),
                    "precio_venta": request.form.get("precio_venta", 0),
                }
            )
            return render_template(
                "stock/stock_editar.html",
                producto=producto_form,
                modo="nuevo",
                **_contexto_base(),
            )

        try:
            db.session.add(producto)
            db.session.commit()
            flash("Producto creado correctamente.")
            return redirect(
                url_for("stock_empleado.receta_producto", producto_id=producto.IdProductoTerminado)
            )
        except SQLAlchemyError:
            db.session.rollback()
            flash("No fue posible crear el producto.")

    return render_template(
        "stock/stock_editar.html",
        producto=producto_form,
        modo="nuevo",
        **_contexto_base(),
    )


@stock_empleado_bp.route("/stock/<int:producto_id>/editar", methods=["GET", "POST"])
def editar_stock(producto_id):
    producto = db.get_or_404(ProductoTerminado, producto_id)

    if request.method == "POST":
        producto.Nombre = request.form.get("nombre", "").strip() or producto.Nombre
        producto.Descripcion = request.form.get("descripcion", "").strip() or None

        try:
            producto.StockActual = int(request.form.get("stock_actual", producto.StockActual))
            producto.StockMinimo = int(request.form.get("stock_minimo", producto.StockMinimo))
            producto.PrecioVenta = _decimal(request.form.get("precio_venta"))
        except (TypeError, ValueError, InvalidOperation):
            flash("Los valores numericos enviados no son validos.")
            return render_template(
                "stock/stock_editar.html",
                producto=_serializar_producto(producto),
                modo="editar",
                **_contexto_base(),
            )

        try:
            db.session.commit()
            flash("Producto actualizado correctamente.")
            return redirect(url_for("stock_empleado.stock"))
        except SQLAlchemyError:
            db.session.rollback()
            flash("No fue posible actualizar el producto.")

    return render_template(
        "stock/stock_editar.html",
        producto=_serializar_producto(producto),
        modo="editar",
        **_contexto_base(),
    )


@stock_empleado_bp.route("/stock/<int:producto_id>/receta", methods=["GET", "POST"])
def receta_producto(producto_id):
    producto = db.get_or_404(ProductoTerminado, producto_id)
    receta = db.session.get(Receta, producto_id)

    if request.method == "POST":
        accion = request.form.get("accion", "").strip()

        if accion == "guardar_receta":
            usuario = _obtener_usuario_registro()
            if usuario is None:
                flash("No hay un usuario activo para registrar la receta.")
                return render_template(
                    "stock/receta_producto.html",
                    **_obtener_contexto_receta(producto, receta),
                )

            try:
                merma = _decimal(request.form.get("merma"))
            except (InvalidOperation, TypeError, ValueError):
                flash("La merma enviada no es valida.")
                return render_template(
                    "stock/receta_producto.html",
                    **_obtener_contexto_receta(producto, receta),
                )

            if receta is None:
                receta = Receta(
                    IdProductoTerminado=producto.IdProductoTerminado,
                    Merma=merma,
                    IdUsuarioRegistro=usuario.IdUsuario,
                    RequiereAprobacion=False,
                    Aprobada=True,
                    IdUsuarioAprueba=usuario.IdUsuario,
                    FechaAprobacion=datetime.utcnow(),
                    Activa=True,
                )
                db.session.add(receta)
            else:
                receta.Merma = merma
                receta.RequiereAprobacion = False
                receta.Aprobada = True
                receta.IdUsuarioAprueba = usuario.IdUsuario
                receta.FechaAprobacion = datetime.utcnow()
                receta.Activa = True

            try:
                producto.CostoProduccion = _calcular_costo_produccion(producto_id)
                db.session.commit()
                flash("Receta guardada correctamente.")
                return redirect(url_for("stock_empleado.receta_producto", producto_id=producto_id))
            except SQLAlchemyError:
                db.session.rollback()
                flash("No fue posible guardar la receta.")

        if accion == "agregar_detalle":
            if receta is None:
                flash("Primero debes guardar la receta general del producto.")
                return render_template(
                    "stock/receta_producto.html",
                    **_obtener_contexto_receta(
                        producto,
                        receta,
                        {
                            "materia_prima_id": request.form.get("materia_prima_id", ""),
                            "cantidad": request.form.get("cantidad_requerida", ""),
                        },
                    ),
                )

            materia_prima_id = request.form.get("materia_prima_id", type=int)
            try:
                cantidad = _decimal(request.form.get("cantidad_requerida"))
            except (InvalidOperation, TypeError, ValueError):
                cantidad = None

            if not materia_prima_id or cantidad is None or cantidad <= 0:
                flash("Selecciona una materia prima y una cantidad valida.")
                return render_template(
                    "stock/receta_producto.html",
                    **_obtener_contexto_receta(
                        producto,
                        receta,
                        {
                            "materia_prima_id": request.form.get("materia_prima_id", ""),
                            "cantidad": request.form.get("cantidad_requerida", ""),
                        },
                    ),
                )

            detalle = db.session.execute(
                select(RecetaDetalle).where(
                    RecetaDetalle.IdProductoTerminado == producto_id,
                    RecetaDetalle.IdMateriaPrima == materia_prima_id,
                )
            ).scalar_one_or_none()

            if detalle is None:
                detalle = RecetaDetalle(
                    IdProductoTerminado=producto_id,
                    IdMateriaPrima=materia_prima_id,
                    CantidadRequerida=cantidad,
                )
                db.session.add(detalle)
            else:
                detalle.CantidadRequerida = cantidad

            try:
                db.session.flush()
                producto.CostoProduccion = _calcular_costo_produccion(producto_id)
                db.session.commit()
                flash("Detalle de receta guardado correctamente.")
                return redirect(url_for("stock_empleado.receta_producto", producto_id=producto_id))
            except SQLAlchemyError:
                db.session.rollback()
                flash("No fue posible guardar el detalle de la receta.")

        if accion == "eliminar_detalle":
            detalle_id = request.form.get("detalle_id", type=int)
            detalle = db.session.get(RecetaDetalle, detalle_id) if detalle_id else None
            if detalle and detalle.IdProductoTerminado == producto_id:
                try:
                    db.session.delete(detalle)
                    db.session.flush()
                    producto.CostoProduccion = _calcular_costo_produccion(producto_id)
                    db.session.commit()
                    flash("Detalle eliminado correctamente.")
                    return redirect(url_for("stock_empleado.receta_producto", producto_id=producto_id))
                except SQLAlchemyError:
                    db.session.rollback()
                    flash("No fue posible eliminar el detalle.")

    return render_template(
        "stock/receta_producto.html",
        **_obtener_contexto_receta(producto, receta),
    )


@stock_empleado_bp.post("/stock/<int:producto_id>/desactivar")
def desactivar_stock(producto_id):
    producto = db.get_or_404(ProductoTerminado, producto_id)

    if not producto.Activo:
        flash("El producto ya estaba desactivado.")
        return redirect(url_for("stock_empleado.stock"))

    producto.Activo = False

    try:
        db.session.commit()
        flash("Producto desactivado correctamente.")
    except SQLAlchemyError:
        db.session.rollback()
        flash("No fue posible desactivar el producto.")

    return redirect(url_for("stock_empleado.stock"))
