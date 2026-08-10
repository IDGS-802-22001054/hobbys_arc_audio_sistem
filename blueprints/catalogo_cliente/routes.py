from base64 import b64encode
from datetime import date, datetime
from decimal import Decimal
import re
from uuid import uuid4

from flask import current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import Cliente, Persona, ProductoTerminado, SesionUsuario, SolicitudProduccion, TarjetaCliente, Usuario, db
from services.ventas import registrar_venta_catalogo_cliente
from werkzeug.security import check_password_hash, generate_password_hash

from blueprints.clientes.routes_cliente import (
    _enmascarar_correo,
    _enviar_codigo_verificacion,
    _generar_codigo,
    obtener_rol_cliente_id,
)

from . import catalogo_cliente_bp

COLORES_TARJETA = ("red", "yellow", "green", "blue")
CLAVE_CARRITO = "catalogo_cliente_carrito"
MAX_UNIDADES_SOLICITUD_SIN_EXISTENCIA = 3
ENDPOINTS_CATALOGO_PROTEGIDOS = {
    "catalogo_cliente.catalogo",
    "catalogo_cliente.agregar_al_carrito",
    "catalogo_cliente.actualizar_carrito",
    "catalogo_cliente.checkout",
    "catalogo_cliente.realizar_compra",
    "catalogo_cliente.layout",
    "catalogo_cliente.api_catalogo",
    "catalogo_cliente.api_producto",
    "catalogo_cliente.api_obtener_carrito",
    "catalogo_cliente.api_agregar_carrito",
    "catalogo_cliente.api_actualizar_carrito",
    "catalogo_cliente.api_actualizar_carrito_post",
    "catalogo_cliente.api_eliminar_carrito",
    "catalogo_cliente.api_eliminar_carrito_post",
    "catalogo_cliente.api_checkout",
    "catalogo_cliente.api_registrar_compra",
    "catalogo_cliente.api_actualizar_usuario",
    "catalogo_cliente.api_obtener_usuario",
}


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


def _texto_limpio(valor):
    texto = (valor or "").strip()
    return texto or None


def _limite_carrito_por_stock(stock_disponible):
    return max(int(stock_disponible or 0), 0) + MAX_UNIDADES_SOLICITUD_SIN_EXISTENCIA


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
    stock = max(int(producto.StockActual or 0), 0)
    return {
        "id": producto.IdProductoTerminado,
        "nombre": producto.Nombre,
        "descripcion": producto.Descripcion or "Sin descripcion disponible.",
        "precio": _precio_decimal(producto.PrecioVenta),
        "stock": stock,
        "sin_existencia": stock <= 0,
        "limite_total": _limite_carrito_por_stock(stock),
        "limite_solicitud": MAX_UNIDADES_SOLICITUD_SIN_EXISTENCIA,
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


def _obtener_productos_carrito(carrito):
    consulta = select(ProductoTerminado).where(
        ProductoTerminado.IdProductoTerminado.in_(carrito.keys())
    )
    return {
        producto.IdProductoTerminado: producto
        for producto in db.session.execute(consulta).scalars().all()
    }


def _separar_carrito_por_existencia(carrito):
    productos = _obtener_productos_carrito(carrito) if carrito else {}
    carrito_compra = {}
    carrito_solicitud = {}
    carrito_actualizado = {}

    for producto_id, cantidad_solicitada in carrito.items():
        producto = productos.get(producto_id)
        if producto is None or not producto.Activo:
            continue

        stock_disponible = max(int(producto.StockActual or 0), 0)
        limite = _limite_carrito_por_stock(stock_disponible)
        cantidad = min(int(cantidad_solicitada), limite)
        if cantidad <= 0:
            continue

        carrito_actualizado[producto_id] = cantidad
        cantidad_compra = min(cantidad, stock_disponible)
        cantidad_solicitud = min(
            max(cantidad - stock_disponible, 0),
            MAX_UNIDADES_SOLICITUD_SIN_EXISTENCIA,
        )

        if cantidad_compra > 0:
            carrito_compra[producto_id] = cantidad_compra
        if cantidad_solicitud > 0:
            carrito_solicitud[producto_id] = cantidad_solicitud

    return productos, carrito_compra, carrito_solicitud, carrito_actualizado


def _obtener_detalle_carrito():
    carrito = _normalizar_carrito()
    if not carrito:
        return [], {
            "subtotal": Decimal("0.00"),
            "total": Decimal("0.00"),
            "subtotal_compra": Decimal("0.00"),
            "cantidad_total": 0,
            "cantidad_compra": 0,
            "cantidad_solicitud": 0,
        }

    productos, carrito_compra, carrito_solicitud, carrito_actualizado = _separar_carrito_por_existencia(carrito)

    lineas = []
    subtotal = Decimal("0.00")
    subtotal_compra = Decimal("0.00")
    cantidad_total = 0
    cantidad_compra = 0
    cantidad_solicitud = 0

    for producto_id, cantidad_solicitada in carrito.items():
        producto = productos.get(producto_id)
        if producto is None or not producto.Activo:
            continue

        stock_disponible = max(int(producto.StockActual or 0), 0)
        cantidad = carrito_actualizado.get(producto_id, 0)
        if cantidad <= 0:
            continue

        precio = _precio_decimal(producto.PrecioVenta)
        cantidad_total += cantidad

        cantidad_compra_linea = carrito_compra.get(producto_id, 0)
        cantidad_solicitud_linea = carrito_solicitud.get(producto_id, 0)
        requiere_produccion = cantidad_solicitud_linea > 0
        subtotal_linea = precio * cantidad
        subtotal_compra_linea = precio * cantidad_compra_linea
        subtotal += subtotal_linea
        subtotal_compra += subtotal_compra_linea
        cantidad_compra += cantidad_compra_linea
        cantidad_solicitud += cantidad_solicitud_linea

        lineas.append(
            {
                "id": producto.IdProductoTerminado,
                "nombre": producto.Nombre,
                "cantidad": cantidad,
                "precio": precio,
                "subtotal": subtotal_linea,
                "subtotal_compra": subtotal_compra_linea,
                "stock": stock_disponible,
                "cantidad_compra": cantidad_compra_linea,
                "cantidad_solicitud": cantidad_solicitud_linea,
                "requiere_produccion": requiere_produccion,
                "limite": _limite_carrito_por_stock(stock_disponible),
            }
        )

    if carrito_actualizado != carrito:
        _guardar_carrito(carrito_actualizado)

    return lineas, {
        "subtotal": subtotal,
        "total": subtotal,
        "subtotal_compra": subtotal_compra,
        "cantidad_total": cantidad_total,
        "cantidad_compra": cantidad_compra,
        "cantidad_solicitud": cantidad_solicitud,
    }


def _decimal_a_texto(valor):
    return format(_precio_decimal(valor), ".2f")


def _serializar_linea_api(linea):
    return {
        **linea,
        "precio": _decimal_a_texto(linea["precio"]),
        "subtotal": _decimal_a_texto(linea["subtotal"]),
        "subtotal_compra": _decimal_a_texto(linea["subtotal_compra"]),
    }


def _respuesta_carrito_api():
    lineas, resumen = _obtener_detalle_carrito()
    return {
        "items": [_serializar_linea_api(linea) for linea in lineas],
        "resumen": {
            **resumen,
            "subtotal": _decimal_a_texto(resumen["subtotal"]),
            "total": _decimal_a_texto(resumen["total"]),
            "subtotal_compra": _decimal_a_texto(resumen["subtotal_compra"]),
        },
    }


def _cuerpo_json():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise ValueError("El cuerpo de la solicitud debe ser un objeto JSON.")
    return datos


def _entero_positivo(valor, campo):
    if isinstance(valor, bool):
        raise ValueError(f"{campo} debe ser un entero positivo.")
    try:
        numero = int(valor)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{campo} debe ser un entero positivo.") from error
    if numero <= 0:
        raise ValueError(f"{campo} debe ser un entero positivo.")
    return numero


def _serializar_usuario_api(usuario):
    persona = usuario.persona
    return {
        "id": usuario.IdUsuario,
        "identificador": usuario.Identificador,
        "nombre": persona.Nombre,
        "apellidos": persona.Apellidos,
        "correo": persona.CorreoElectronico,
        "telefono": persona.Telefono or "",
        "direccion": {
            "calle": persona.Calle or "",
            "colonia": persona.Colonia or "",
            "numero_exterior": persona.NumeroExterior or "",
            "numero_interior": persona.NumeroInterior or "",
            "codigo_postal": persona.CodigoPostal or "",
        },
    }


def _validar_texto_usuario(datos, campo, minimo, maximo, obligatorio=True):
    valor = datos.get(campo)
    if valor is None:
        if obligatorio:
            raise ValueError(f"El campo {campo} es obligatorio.")
        return None
    if not isinstance(valor, str):
        raise ValueError(f"El campo {campo} debe ser texto.")
    valor = valor.strip()
    if obligatorio and not valor:
        raise ValueError(f"El campo {campo} es obligatorio.")
    if valor and not minimo <= len(valor) <= maximo:
        raise ValueError(
            f"El campo {campo} debe tener entre {minimo} y {maximo} caracteres."
        )
    return valor or None


def _booleano_json(valor):
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return valor != 0
    if isinstance(valor, str):
        return valor.strip().lower() in {"1", "true", "si", "sí", "yes", "on"}
    return False


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


def _obtener_cliente_autenticado():
    if not current_user.is_authenticated:
        return None

    persona = getattr(current_user, "persona", None)
    if not persona:
        return None

    cliente = getattr(persona, "cliente", None)
    if cliente:
        return cliente

    consulta = select(Cliente).where(Cliente.IdPersona == current_user.IdPersona)
    return db.session.execute(consulta).scalar_one_or_none()


def _obtener_tarjetas_cliente(cliente):
    if cliente is None:
        return []

    tarjetas = [tarjeta for tarjeta in cliente.tarjetas if tarjeta.Activa]
    return sorted(
        tarjetas,
        key=lambda tarjeta: (
            not bool(tarjeta.EsPredeterminada),
            -(tarjeta.IdTarjetaCliente or 0),
        ),
    )


def _serializar_tarjeta_api(tarjeta):
    return {
        "id": tarjeta.IdTarjetaCliente,
        "alias": tarjeta.Alias or "",
        "titular": tarjeta.Titular,
        "marca": tarjeta.Marca,
        "ultimos4": tarjeta.Ultimos4,
        "mes_expiracion": tarjeta.MesExpiracion,
        "anio_expiracion": tarjeta.AnioExpiracion,
        "es_predeterminada": bool(tarjeta.EsPredeterminada),
    }


def _direccion_envio_actual(persona, form_data=None):
    form_data = form_data or {}
    return {
        "calle": (form_data.get("calle_envio") or getattr(persona, "Calle", None) or "").strip(),
        "colonia": (form_data.get("colonia_envio") or getattr(persona, "Colonia", None) or "").strip(),
        "numero_exterior": (
            form_data.get("numero_exterior_envio") or getattr(persona, "NumeroExterior", None) or ""
        ).strip(),
        "numero_interior": (
            form_data.get("numero_interior_envio") or getattr(persona, "NumeroInterior", None) or ""
        ).strip(),
        "codigo_postal": (
            form_data.get("codigo_postal_envio") or getattr(persona, "CodigoPostal", None) or ""
        ).strip(),
    }


def _contexto_checkout(busqueda="", form_data=None):
    carrito, resumen = _obtener_detalle_carrito()
    cliente = _obtener_cliente_autenticado()
    persona = getattr(cliente, "persona", None) or getattr(current_user, "persona", None)
    tarjetas = _obtener_tarjetas_cliente(cliente)

    tarjeta_guardada_id = ""
    if form_data is not None:
        tarjeta_guardada_id = (form_data.get("tarjeta_guardada_id") or "").strip()
    elif tarjetas:
        tarjeta_guardada_id = str(tarjetas[0].IdTarjetaCliente)

    return {
        "carrito": carrito,
        "resumen": resumen,
        "busqueda": busqueda,
        "cliente": cliente,
        "direccion_envio": _direccion_envio_actual(persona, form_data),
        "tarjetas": tarjetas,
        "tarjeta_guardada_id": tarjeta_guardada_id,
        "nueva_tarjeta": {
            "alias": (form_data.get("alias_tarjeta") or "").strip() if form_data else "",
            "titular": (form_data.get("titular_tarjeta") or "").strip() if form_data else "",
            "marca": (form_data.get("marca_tarjeta") or "").strip() if form_data else "",
            "numero": (form_data.get("numero_tarjeta") or "").strip() if form_data else "",
            "mes_expiracion": (form_data.get("mes_expiracion") or "").strip() if form_data else "",
            "anio_expiracion": (form_data.get("anio_expiracion") or "").strip() if form_data else "",
            "guardar_tarjeta": bool(form_data.get("guardar_tarjeta")) if form_data else False,
            "tarjeta_predeterminada": bool(form_data.get("tarjeta_predeterminada")) if form_data else False,
            "acepto_terminos": bool(form_data.get("acepto_terminos")) if form_data else False,
        },
        "anios_expiracion": list(range(date.today().year, date.today().year + 15)),
        "active": "catalogo",
        "usuario_iniciales": "RC",
    }


def _validar_direccion_envio(form_data):
    direccion = {
        "calle": _texto_limpio(form_data.get("calle_envio")),
        "colonia": _texto_limpio(form_data.get("colonia_envio")),
        "numero_exterior": _texto_limpio(form_data.get("numero_exterior_envio")),
        "numero_interior": _texto_limpio(form_data.get("numero_interior_envio")),
        "codigo_postal": _texto_limpio(form_data.get("codigo_postal_envio")),
    }

    if not direccion["calle"] or not direccion["colonia"] or not direccion["numero_exterior"] or not direccion["codigo_postal"]:
        raise ValueError(
            "Completa la direccion de envio con calle, colonia, numero exterior y codigo postal."
        )

    return direccion


def _resolver_tarjeta_checkout(cliente, form_data):
    tarjeta_guardada_id = (form_data.get("tarjeta_guardada_id") or "").strip()
    tarjetas = _obtener_tarjetas_cliente(cliente)

    if tarjeta_guardada_id:
        try:
            tarjeta_id = int(tarjeta_guardada_id)
        except (TypeError, ValueError) as error:
            raise ValueError("La tarjeta seleccionada no es valida.") from error

        tarjeta = next(
            (item for item in tarjetas if item.IdTarjetaCliente == tarjeta_id),
            None,
        )
        if tarjeta is None:
            raise ValueError("La tarjeta seleccionada ya no esta disponible.")
        return {
            "tipo": "guardada",
            "tarjeta": tarjeta,
            "guardar_tarjeta": False,
            "tarjeta_predeterminada": False,
            "nueva_tarjeta": None,
        }

    numero_tarjeta = "".join(
        caracter for caracter in (form_data.get("numero_tarjeta") or "") if caracter.isdigit()
    )
    titular = _texto_limpio(form_data.get("titular_tarjeta"))
    marca = _texto_limpio(form_data.get("marca_tarjeta"))
    alias = _texto_limpio(form_data.get("alias_tarjeta"))

    try:
        mes_expiracion = int(form_data.get("mes_expiracion", "0"))
        anio_expiracion = int(form_data.get("anio_expiracion", "0"))
    except (TypeError, ValueError) as error:
        raise ValueError("La fecha de expiracion de la tarjeta no es valida.") from error

    if not numero_tarjeta and not titular and not marca:
        raise ValueError("Selecciona una tarjeta guardada o registra una nueva para continuar.")

    if len(numero_tarjeta) < 13 or len(numero_tarjeta) > 19:
        raise ValueError("El numero de tarjeta no es valido.")

    if not titular or not marca:
        raise ValueError("Completa el titular y la marca de la tarjeta.")

    if mes_expiracion < 1 or mes_expiracion > 12:
        raise ValueError("El mes de expiracion no es valido.")

    hoy = date.today()
    if anio_expiracion < hoy.year or (
        anio_expiracion == hoy.year and mes_expiracion < hoy.month
    ):
        raise ValueError("La tarjeta ya esta vencida.")

    guardar_tarjeta = bool(form_data.get("guardar_tarjeta"))
    usar_predeterminada = bool(form_data.get("tarjeta_predeterminada"))

    return {
        "tipo": "nueva",
        "tarjeta": None,
        "guardar_tarjeta": guardar_tarjeta,
        "tarjeta_predeterminada": usar_predeterminada,
        "nueva_tarjeta": {
            "Alias": alias,
            "Titular": titular,
            "Marca": marca,
            "Ultimos4": numero_tarjeta[-4:],
            "MesExpiracion": mes_expiracion,
            "AnioExpiracion": anio_expiracion,
        },
    }


def _mapear_checkout_desde_json(datos):
    direccion = datos.get("direccion_envio") or {}
    nueva_tarjeta = datos.get("nueva_tarjeta") or {}
    return {
        "acepto_terminos": _booleano_json(datos.get("acepto_terminos")),
        "tarjeta_guardada_id": str(datos.get("tarjeta_guardada_id") or "").strip(),
        "calle_envio": (direccion.get("calle") or "").strip(),
        "colonia_envio": (direccion.get("colonia") or "").strip(),
        "numero_exterior_envio": (direccion.get("numero_exterior") or "").strip(),
        "numero_interior_envio": (direccion.get("numero_interior") or "").strip(),
        "codigo_postal_envio": (direccion.get("codigo_postal") or "").strip(),
        "alias_tarjeta": (nueva_tarjeta.get("alias") or "").strip(),
        "titular_tarjeta": (nueva_tarjeta.get("titular") or "").strip(),
        "marca_tarjeta": (nueva_tarjeta.get("marca") or "").strip(),
        "numero_tarjeta": (nueva_tarjeta.get("numero") or "").strip(),
        "mes_expiracion": str(nueva_tarjeta.get("mes_expiracion") or "").strip(),
        "anio_expiracion": str(nueva_tarjeta.get("anio_expiracion") or "").strip(),
        "guardar_tarjeta": _booleano_json(nueva_tarjeta.get("guardar_tarjeta")),
        "tarjeta_predeterminada": _booleano_json(nueva_tarjeta.get("tarjeta_predeterminada")),
    }


def _respuesta_checkout_api():
    carrito, resumen = _obtener_detalle_carrito()
    cliente = _obtener_cliente_autenticado()
    persona = getattr(cliente, "persona", None) or getattr(current_user, "persona", None)
    tarjetas = _obtener_tarjetas_cliente(cliente)
    direccion = _direccion_envio_actual(persona)
    return {
        "cliente": {
            "id": cliente.IdCliente if cliente else None,
            "nombre": (
                f"{(persona.Nombre or '').strip()} {(persona.Apellidos or '').strip()}".strip()
                if persona else ""
            ),
            "correo": getattr(persona, "CorreoElectronico", "") or "",
        },
        "direccion_envio": direccion,
        "tarjetas": [_serializar_tarjeta_api(tarjeta) for tarjeta in tarjetas],
        "anios_expiracion": list(range(date.today().year, date.today().year + 15)),
        "carrito": {
            "items": [_serializar_linea_api(linea) for linea in carrito],
            "resumen": {
                **resumen,
                "subtotal": _decimal_a_texto(resumen["subtotal"]),
                "total": _decimal_a_texto(resumen["total"]),
                "subtotal_compra": _decimal_a_texto(resumen["subtotal_compra"]),
            },
        },
    }


def _actualizar_carrito_api(producto_id, cantidad):
    carrito = _normalizar_carrito()
    if producto_id not in carrito:
        return jsonify({"error": "El producto no esta en el carrito."}), 404

    producto = db.session.get(ProductoTerminado, producto_id)
    if producto is None or not producto.Activo:
        carrito.pop(producto_id, None)
        _guardar_carrito(carrito)
        return jsonify({"error": "Producto no encontrado o no disponible."}), 404

    limite = _limite_carrito_por_stock(producto.StockActual)
    if cantidad > limite:
        return jsonify(
            {
                "error": "La cantidad solicitada supera el limite disponible.",
                "limite": limite,
            }
        ), 409

    carrito[producto_id] = cantidad
    _guardar_carrito(carrito)
    return jsonify(_respuesta_carrito_api())


def _eliminar_carrito_api(producto_id):
    carrito = _normalizar_carrito()
    if producto_id not in carrito:
        return jsonify({"error": "El producto no esta en el carrito."}), 404
    carrito.pop(producto_id)
    _guardar_carrito(carrito)
    return jsonify(_respuesta_carrito_api())


def _registrar_compra_catalogo(form_data):
    carrito = _normalizar_carrito()
    if not carrito:
        raise ValueError("Tu carrito esta vacio.")

    cliente = _obtener_cliente_autenticado()
    if cliente is None:
        raise ValueError("No se encontro un cliente asociado a tu usuario.")

    productos, carrito_compra, carrito_solicitud, carrito_actualizado = _separar_carrito_por_existencia(carrito)
    if carrito_actualizado != carrito:
        _guardar_carrito(carrito_actualizado)
        carrito = carrito_actualizado

    if not carrito_compra and not carrito_solicitud:
        raise ValueError("Tu carrito ya no tiene productos disponibles para procesar.")

    if not form_data.get("acepto_terminos"):
        raise ValueError("Debes aceptar los terminos y condiciones para continuar.")

    direccion_envio = _validar_direccion_envio(form_data)
    tarjeta_checkout = _resolver_tarjeta_checkout(cliente, form_data)
    venta_registrada = False
    solicitudes_creadas = 0

    usuario = _obtener_usuario_registro()
    if usuario is None:
        raise ValueError("No hay un usuario disponible para registrar la venta.")

    if carrito_compra or carrito_solicitud:
        venta = registrar_venta_catalogo_cliente(
            id_cliente=cliente.IdCliente,
            id_usuario=usuario.IdUsuario,
            metodo_pago="TARJETA",
            carrito_total=carrito,
            carrito_con_stock=carrito_compra,
        )
        venta_registrada = True
    else:
        venta = None

    try:
        persona = cliente.persona
        persona.Calle = direccion_envio["calle"]
        persona.Colonia = direccion_envio["colonia"]
        persona.NumeroExterior = direccion_envio["numero_exterior"]
        persona.NumeroInterior = direccion_envio["numero_interior"]
        persona.CodigoPostal = direccion_envio["codigo_postal"]

        if tarjeta_checkout and tarjeta_checkout["guardar_tarjeta"] and tarjeta_checkout["nueva_tarjeta"]:
            tarjetas = _obtener_tarjetas_cliente(cliente)
            if tarjeta_checkout["tarjeta_predeterminada"] or not tarjetas:
                for tarjeta in tarjetas:
                    tarjeta.EsPredeterminada = False

            nueva_tarjeta = tarjeta_checkout["nueva_tarjeta"]
            db.session.add(
                TarjetaCliente(
                    IdCliente=cliente.IdCliente,
                    Alias=nueva_tarjeta["Alias"],
                    Titular=nueva_tarjeta["Titular"],
                    Marca=nueva_tarjeta["Marca"],
                    Ultimos4=nueva_tarjeta["Ultimos4"],
                    MesExpiracion=nueva_tarjeta["MesExpiracion"],
                    AnioExpiracion=nueva_tarjeta["AnioExpiracion"],
                    TokenPasarela=f"manual_{uuid4().hex}",
                    EsPredeterminada=tarjeta_checkout["tarjeta_predeterminada"] or not tarjetas,
                )
            )

        for producto_id, cantidad in carrito_solicitud.items():
            producto = productos.get(producto_id)
            if producto is None:
                continue

            db.session.add(
                SolicitudProduccion(
                    IdVenta=venta.IdVenta if venta is not None else None,
                    IdProductoTerminado=producto_id,
                    CantidadSolicitada=min(int(cantidad), MAX_UNIDADES_SOLICITUD_SIN_EXISTENCIA),
                    Motivo=(
                        "Solicitud automatica desde catalogo cliente por falta de existencia: "
                        f"{producto.Nombre}"
                    ),
                    IdUsuarioSolicita=current_user.IdUsuario,
                )
            )
            solicitudes_creadas += 1

        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        if venta_registrada:
            solicitudes_creadas = 0
            current_app.logger.exception(
                "La compra se registro, pero no fue posible actualizar la direccion, guardar la tarjeta o crear solicitudes."
            )
            raise ValueError(
                "La compra se registro, pero no fue posible actualizar la direccion, guardar la tarjeta o crear las solicitudes de produccion pendientes."
            )
        raise

    _guardar_carrito({})
    mensajes = []
    if venta_registrada:
        mensajes.append("Compra registrada correctamente.")
    if solicitudes_creadas:
        mensajes.append(
            f"Se generaron {solicitudes_creadas} solicitud(es) de produccion para piezas sin existencia."
        )

    return {
        "venta_id": venta.IdVenta if venta is not None else None,
        "venta_registrada": venta_registrada,
        "solicitudes_creadas": solicitudes_creadas,
        "mensajes": mensajes,
    }


@catalogo_cliente_bp.before_request
def _proteger_catalogo_cliente():
    if request.endpoint not in ENDPOINTS_CATALOGO_PROTEGIDOS:
        return None

    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()

    if _obtener_cliente_autenticado() is None:
        flash("Solo los clientes pueden acceder al catalogo.", "error")
        return redirect(url_for("auth.login"))

    return None


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


@catalogo_cliente_bp.post("/api/clientes/registro")
def api_registro_cliente():
    try:
        datos = _cuerpo_json()
        identificador = (datos.get("identificador") or "").strip()
        password = datos.get("password") or ""
        confirm = datos.get("password_confirm") or ""
        nombre = (datos.get("nombre") or "").strip()
        apellidos = (datos.get("apellidos") or "").strip()
        correo = (datos.get("correo") or "").strip()

        if not nombre or not apellidos or not correo:
            raise ValueError("Nombre, apellidos y correo son obligatorios.")
        if password != confirm:
            raise ValueError("Las contrasenas no coinciden.")
        if not identificador:
            raise ValueError("El nombre de usuario es requerido.")
        if len(password) < 8:
            raise ValueError("La contrasena debe tener al menos 8 caracteres.")

        correo_existe = db.session.execute(
            select(Persona.IdPersona).where(Persona.CorreoElectronico == correo).limit(1)
        ).scalar_one_or_none()
        if correo_existe:
            raise ValueError("El correo electronico ya esta registrado.")

        usuario_existe = db.session.execute(
            select(Usuario.IdUsuario).where(Usuario.Identificador == identificador).limit(1)
        ).scalar_one_or_none()
        if usuario_existe:
            raise ValueError("El nombre de usuario ya esta en uso.")

        codigo = _generar_codigo()
        session["verificacion"] = {
            "codigo": codigo,
            "expira": (datetime.now() + timedelta(minutes=10)).isoformat(),
            "correo": correo,
            "nombre": nombre,
            "apellidos": apellidos,
            "identificador": identificador,
            "password_hash": generate_password_hash(password),
        }
        session.modified = True

        if not _enviar_codigo_verificacion(correo, codigo, nombre):
            return jsonify({"error": "No se pudo enviar el correo de verificacion. Intenta de nuevo."}), 502

        return jsonify(
            {
                "mensaje": "Codigo de verificacion enviado correctamente.",
                "correo_enmascarado": _enmascarar_correo(correo),
            }
        ), 202
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("No fue posible iniciar el registro de cliente por API.")
        return jsonify({"error": "Error interno del servidor."}), 500


@catalogo_cliente_bp.post("/api/clientes/registro/verificar")
def api_verificar_registro_cliente():
    try:
        datos = _cuerpo_json()
        codigo_ingresado = (datos.get("codigo_verificacion") or "").strip()
        verificacion = session.get("verificacion")
        if not verificacion:
            raise ValueError("La sesion de verificacion expiro. Intenta de nuevo.")
        if datetime.now() > datetime.fromisoformat(verificacion["expira"]):
            session.pop("verificacion", None)
            raise ValueError("El codigo expiro. Vuelve a solicitar uno nuevo.")
        if codigo_ingresado != verificacion["codigo"]:
            raise ValueError("El codigo de verificacion es incorrecto.")

        rol_cliente_id = obtener_rol_cliente_id()
        if rol_cliente_id is None:
            raise ValueError("No existe el rol Cliente. Contacta al administrador.")

        db.session.execute(
            text(
                """
            CALL SP_Clientes_Registrar(
                :nombre,
                :apellidos,
                :correo,
                :identificador,
                :password_hash,
                :id_rol,
                :calle,
                :colonia,
                :numero_exterior,
                :numero_interior,
                :codigo_postal,
                @id_cliente
            )
            """
            ),
            {
                "nombre": verificacion["nombre"],
                "apellidos": verificacion["apellidos"],
                "correo": verificacion["correo"],
                "identificador": verificacion["identificador"],
                "password_hash": verificacion["password_hash"],
                "id_rol": rol_cliente_id,
                "calle": None,
                "colonia": None,
                "numero_exterior": None,
                "numero_interior": None,
                "codigo_postal": None,
            },
        )
        db.session.commit()

        session.pop("verificacion", None)

        usuario = db.session.execute(
            select(Usuario).where(Usuario.Identificador == verificacion["identificador"]).limit(1)
        ).scalar_one_or_none()
        if usuario is None:
            raise ValueError("La cuenta se creo, pero no fue posible recuperar el usuario.")

        nueva_sesion = SesionUsuario(
            IdUsuario=usuario.IdUsuario,
            FechaInicio=datetime.now(),
            FechaUltimaActividad=datetime.now(),
            Activa=True,
        )
        usuario.FechaUltimoAcceso = datetime.now()
        db.session.add(nueva_sesion)
        db.session.commit()

        session["id_sesion_usuario"] = nueva_sesion.IdSesionUsuario
        session["app_role_nombre"] = "cliente"
        login_user(usuario, remember=False)

        return jsonify(
            {
                "mensaje": "Cuenta creada y correo verificado correctamente.",
                "usuario": usuario.Identificador,
            }
        ), 201
    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("No fue posible verificar el registro de cliente por API.")
        return jsonify({"error": "Error interno del servidor."}), 500


@catalogo_cliente_bp.post("/api/clientes/registro/reenviar-codigo")
def api_reenviar_codigo_registro():
    datos = session.get("verificacion")
    if not datos:
        return jsonify({"error": "La sesion de verificacion expiro. Vuelve a llenar el formulario."}), 400

    nuevo_codigo = _generar_codigo()
    datos["codigo"] = nuevo_codigo
    datos["expira"] = (datetime.now() + timedelta(minutes=10)).isoformat()
    session["verificacion"] = datos
    session.modified = True

    if not _enviar_codigo_verificacion(datos["correo"], nuevo_codigo, datos["nombre"]):
        return jsonify({"error": "No se pudo reenviar el correo de verificacion."}), 502

    return jsonify(
        {
            "mensaje": "Codigo reenviado correctamente.",
            "correo_enmascarado": _enmascarar_correo(datos["correo"]),
        }
    )


@catalogo_cliente_bp.post("/api/clientes/login")
def api_login():
    try:
        datos = _cuerpo_json()
        identificador = (datos.get("identificador") or "").strip()
        password = datos.get("password") or ""
        if len(identificador) < 3 or len(password) < 6:
            return jsonify({"error": "Usuario o contrasena no validos."}), 400

        usuario = db.session.execute(
            select(Usuario).where(Usuario.Identificador == identificador)
        ).scalar_one_or_none()
        persona = getattr(usuario, "persona", None)
        cliente = getattr(persona, "cliente", None)
        if usuario is None or not usuario.Activo or cliente is None or not check_password_hash(usuario.PasswordHash, password):
            return jsonify({"error": "Credenciales de cliente incorrectas."}), 401

        sesion_usuario = SesionUsuario(
            IdUsuario=usuario.IdUsuario,
            FechaInicio=datetime.now(),
            FechaUltimaActividad=datetime.now(),
            Activa=True,
        )
        usuario.FechaUltimoAcceso = datetime.now()
        db.session.add(sesion_usuario)
        db.session.commit()
        session["id_sesion_usuario"] = sesion_usuario.IdSesionUsuario
        session["app_role_nombre"] = "cliente"
        login_user(usuario, remember=False)
        return jsonify({"mensaje": "Sesion iniciada.", "usuario": usuario.Identificador})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("No fue posible iniciar sesion desde la API.")
        return jsonify({"error": "Error interno del servidor."}), 500


@catalogo_cliente_bp.put("/api/clientes/usuario")
@login_required
def api_actualizar_usuario():
    try:
        datos = _cuerpo_json()
        nombre = _validar_texto_usuario(datos, "nombre", 2, 100)
        apellidos = _validar_texto_usuario(datos, "apellidos", 2, 150)
        correo = _validar_texto_usuario(datos, "correo", 5, 120)
        identificador = _validar_texto_usuario(datos, "identificador", 3, 50)
        telefono = _validar_texto_usuario(datos, "telefono", 1, 30, obligatorio=False)
        password = _validar_texto_usuario(datos, "password", 6, 128, obligatorio=False)

        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", correo):
            raise ValueError("El correo electronico no tiene un formato valido.")

        direccion = datos.get("direccion", {})
        if direccion is None:
            direccion = {}
        if not isinstance(direccion, dict):
            raise ValueError("El campo direccion debe ser un objeto JSON.")

        calle = _validar_texto_usuario(direccion, "calle", 1, 120, obligatorio=False)
        colonia = _validar_texto_usuario(direccion, "colonia", 1, 120, obligatorio=False)
        numero_exterior = _validar_texto_usuario(
            direccion, "numero_exterior", 1, 20, obligatorio=False
        )
        numero_interior = _validar_texto_usuario(
            direccion, "numero_interior", 1, 20, obligatorio=False
        )
        codigo_postal = _validar_texto_usuario(
            direccion, "codigo_postal", 1, 10, obligatorio=False
        )

        usuario = db.session.get(Usuario, current_user.IdUsuario)
        persona = getattr(usuario, "persona", None)
        cliente = getattr(persona, "cliente", None)
        if usuario is None or persona is None or cliente is None:
            return jsonify({"error": "No se encontro el perfil del cliente."}), 404

        correo_ocupado = db.session.execute(
            select(Persona.IdPersona).where(
                Persona.CorreoElectronico == correo,
                Persona.IdPersona != persona.IdPersona,
            )
        ).scalar_one_or_none()
        if correo_ocupado is not None:
            return jsonify({"error": "El correo electronico ya esta registrado."}), 409

        identificador_ocupado = db.session.execute(
            select(Usuario.IdUsuario).where(
                Usuario.Identificador == identificador,
                Usuario.IdUsuario != usuario.IdUsuario,
            )
        ).scalar_one_or_none()
        if identificador_ocupado is not None:
            return jsonify({"error": "El identificador ya esta registrado."}), 409

        persona.Nombre = nombre
        persona.Apellidos = apellidos
        persona.CorreoElectronico = correo
        persona.Telefono = telefono
        persona.Calle = calle
        persona.Colonia = colonia
        persona.NumeroExterior = numero_exterior
        persona.NumeroInterior = numero_interior
        persona.CodigoPostal = codigo_postal
        usuario.Identificador = identificador
        if password:
            usuario.PasswordHash = generate_password_hash(password)

        db.session.commit()
        return jsonify(
            {
                "mensaje": "Datos del usuario actualizados correctamente.",
                "usuario": _serializar_usuario_api(usuario),
            }
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "El correo o identificador ya esta registrado."}), 409
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("No fue posible actualizar el usuario desde la API.")
        return jsonify({"error": "Error interno del servidor."}), 500


@catalogo_cliente_bp.get("/api/clientes/usuario")
@login_required
def api_obtener_usuario():
    try:
        usuario = db.session.get(Usuario, current_user.IdUsuario)
        persona = getattr(usuario, "persona", None)
        cliente = getattr(persona, "cliente", None)
        if usuario is None or persona is None or cliente is None:
            return jsonify({"error": "No se encontro el perfil del cliente."}), 404
        return jsonify({"usuario": _serializar_usuario_api(usuario)})
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible consultar el usuario desde la API.")
        return jsonify({"error": "Error interno del servidor."}), 500


@catalogo_cliente_bp.get("/api/clientes/catalogo")
@login_required
def api_catalogo():
    busqueda = request.args.get("q", "").strip()
    try:
        productos = _obtener_productos(busqueda)
        return jsonify(
            {
                "productos": [
                    {
                        **producto,
                        "precio": _decimal_a_texto(producto["precio"]),
                    }
                    for producto in productos
                ],
                "total": len(productos),
                "busqueda": busqueda,
            }
        )
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible consultar el catalogo mediante la API.")
        return jsonify({"error": "No fue posible consultar el catalogo."}), 500


@catalogo_cliente_bp.get("/api/clientes/catalogo/<int:producto_id>")
@login_required
def api_producto(producto_id):
    try:
        producto = db.session.get(ProductoTerminado, producto_id)
        if producto is None or not producto.Activo:
            return jsonify({"error": "Producto no encontrado."}), 404
        datos = _serializar_producto(producto, 0)
        datos["precio"] = _decimal_a_texto(datos["precio"])
        return jsonify(datos)
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible consultar el producto %s.", producto_id)
        return jsonify({"error": "No fue posible consultar el producto."}), 500


@catalogo_cliente_bp.get("/api/clientes/carrito")
@login_required
def api_obtener_carrito():
    try:
        return jsonify(_respuesta_carrito_api())
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible consultar el carrito mediante la API.")
        return jsonify({"error": "No fue posible consultar el carrito."}), 500


@catalogo_cliente_bp.post("/api/clientes/carrito")
@login_required
def api_agregar_carrito():
    try:
        datos = _cuerpo_json()
        producto_id = _entero_positivo(datos.get("producto_id"), "producto_id")
        cantidad = _entero_positivo(datos.get("cantidad", 1), "cantidad")
        producto = db.session.get(ProductoTerminado, producto_id)
        if producto is None or not producto.Activo:
            return jsonify({"error": "Producto no encontrado o no disponible."}), 404

        carrito = _normalizar_carrito()
        nueva_cantidad = carrito.get(producto_id, 0) + cantidad
        limite = _limite_carrito_por_stock(producto.StockActual)
        if nueva_cantidad > limite:
            return jsonify(
                {
                    "error": "La cantidad solicitada supera el limite disponible.",
                    "limite": limite,
                }
            ), 409

        carrito[producto_id] = nueva_cantidad
        _guardar_carrito(carrito)
        return jsonify(_respuesta_carrito_api()), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible agregar un producto al carrito mediante la API.")
        return jsonify({"error": "No fue posible actualizar el carrito."}), 500


@catalogo_cliente_bp.get("/api/clientes/checkout")
@login_required
def api_checkout():
    try:
        return jsonify(_respuesta_checkout_api())
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible consultar el checkout mediante la API.")
        return jsonify({"error": "No fue posible consultar la informacion de compra."}), 500


@catalogo_cliente_bp.post("/api/clientes/checkout")
@login_required
def api_registrar_compra():
    try:
        datos = _cuerpo_json()
        form_data = _mapear_checkout_desde_json(datos)
        resultado = _registrar_compra_catalogo(form_data)
        return jsonify(
            {
                **resultado,
                "mensaje": " ".join(resultado["mensajes"]).strip(),
                "carrito": _respuesta_carrito_api(),
            }
        ), 201
    except ValueError as error:
        current_app.logger.warning("Checkout API rechazado: %s", error)
        return jsonify({"error": str(error)}), 400
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible registrar la compra por API.")
        return jsonify({"error": "No fue posible registrar la compra."}), 500


@catalogo_cliente_bp.put("/api/clientes/carrito/<int:producto_id>")
@login_required
def api_actualizar_carrito(producto_id):
    try:
        datos = _cuerpo_json()
        cantidad = _entero_positivo(datos.get("cantidad"), "cantidad")
        return _actualizar_carrito_api(producto_id, cantidad)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible modificar el carrito mediante la API.")
        return jsonify({"error": "No fue posible actualizar el carrito."}), 500


@catalogo_cliente_bp.post("/api/clientes/carrito/<int:producto_id>/actualizar")
@login_required
def api_actualizar_carrito_post(producto_id):
    try:
        datos = _cuerpo_json()
        cantidad = _entero_positivo(datos.get("cantidad"), "cantidad")
        return _actualizar_carrito_api(producto_id, cantidad)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible modificar el carrito mediante la API por POST.")
        return jsonify({"error": "No fue posible actualizar el carrito."}), 500


@catalogo_cliente_bp.delete("/api/clientes/carrito/<int:producto_id>")
@login_required
def api_eliminar_carrito(producto_id):
    return _eliminar_carrito_api(producto_id)


@catalogo_cliente_bp.post("/api/clientes/carrito/<int:producto_id>/eliminar")
@login_required
def api_eliminar_carrito_post(producto_id):
    return _eliminar_carrito_api(producto_id)


@catalogo_cliente_bp.route("/catalogo")
@login_required
def catalogo():
    busqueda = request.args.get("q", "").strip()
    return render_template("catalogo/catalogo.html", **obtener_contexto_catalogo(busqueda))


@catalogo_cliente_bp.route("/catalogo/checkout")
@login_required
def checkout():
    busqueda = request.args.get("q", "").strip()
    carrito = _normalizar_carrito()
    if not carrito:
        flash("Tu carrito esta vacio.", "error")
        return redirect(_url_catalogo(busqueda))

    return render_template("catalogo_checkout.html", **_contexto_checkout(busqueda))


@catalogo_cliente_bp.post("/catalogo/carrito/agregar")
@login_required
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
    carrito = _normalizar_carrito()
    cantidad_actual = carrito.get(producto_id, 0)
    limite = _limite_carrito_por_stock(stock_disponible)
    if cantidad_actual >= limite:
        if cantidad_actual >= stock_disponible:
            flash(
                f"Solo puedes solicitar hasta {MAX_UNIDADES_SOLICITUD_SIN_EXISTENCIA} unidades adicionales cuando no hay existencia suficiente.",
                "error",
            )
        else:
            flash("Ya agregaste el maximo disponible en stock.", "error")
        return redirect(_url_catalogo(busqueda))

    carrito[producto_id] = cantidad_actual + 1
    _guardar_carrito(carrito)
    if stock_disponible <= 0:
        flash(
            f"{producto.Nombre} se agrego como solicitud de produccion. Maximo {MAX_UNIDADES_SOLICITUD_SIN_EXISTENCIA} unidades.",
            "success",
        )
    elif cantidad_actual + 1 > stock_disponible:
        flash(
            f"{producto.Nombre} excede el stock disponible. Las unidades faltantes se agregaran como solicitud de produccion.",
            "success",
        )
    else:
        flash(f"{producto.Nombre} se agrego al carrito.", "success")
    return redirect(_url_catalogo(busqueda))


@catalogo_cliente_bp.post("/catalogo/carrito/actualizar")
@login_required
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
        limite = _limite_carrito_por_stock(stock_disponible)
        if carrito[producto_id] >= limite:
            if carrito[producto_id] >= stock_disponible:
                flash(
                    f"Solo puedes solicitar hasta {MAX_UNIDADES_SOLICITUD_SIN_EXISTENCIA} unidades adicionales cuando no hay existencia suficiente.",
                    "error",
                )
            else:
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
@login_required
def realizar_compra():
    busqueda = request.form.get("q", "").strip()

    try:
        resultado = _registrar_compra_catalogo(request.form)
        if resultado["mensajes"]:
            flash(" ".join(resultado["mensajes"]), "success")
        return redirect(_url_catalogo(busqueda))
    except ValueError as error:
        flash(str(error), "error")
        return render_template("catalogo_checkout.html", **_contexto_checkout(busqueda, request.form))
    except SQLAlchemyError:
        current_app.logger.exception("No fue posible registrar la compra.")
        flash("No fue posible registrar la compra en la base de datos.", "error")
        return render_template("catalogo_checkout.html", **_contexto_checkout(busqueda, request.form))


@catalogo_cliente_bp.route("/layout")
def layout():
    return render_template(
        "layout_cli.html",
        active=None,
        usuario_iniciales="RC",
    )
