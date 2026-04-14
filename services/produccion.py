from decimal import Decimal

from models import AlertaSistema, Produccion, Rol, Usuario, db
from services.configuracion import alertas_materia_prima_habilitadas

TIPO_ALERTA_MATERIAL_INSUFICIENTE = 'MATERIAL_INSUFICIENTE'


def _decimal_seguro(valor):
    return Decimal(str(valor or 0))


def obtener_faltantes_materia_prima(produccion):
    producto = getattr(produccion, 'producto_terminado', None)
    receta = getattr(producto, 'receta', None)
    if receta is None:
        return []

    cantidad_planeada = _decimal_seguro(produccion.CantidadPlaneada)
    faltantes = []

    for detalle in receta.detalles:
        materia = detalle.materia_prima
        if materia is None:
            continue

        requerido_unitario = _decimal_seguro(detalle.CantidadRequerida) + _decimal_seguro(detalle.Merma)
        requerido_total = requerido_unitario * cantidad_planeada
        disponible = _decimal_seguro(materia.StockActual)

        if disponible >= requerido_total:
            continue

        faltantes.append(
            {
                'id_materia_prima': materia.IdMateriaPrima,
                'nombre': materia.Nombre,
                'disponible': disponible,
                'requerido': requerido_total,
                'faltante': requerido_total - disponible,
            }
        )

    return faltantes


def notificar_material_insuficiente_a_administradores(produccion, faltantes):
    if not faltantes or not alertas_materia_prima_habilitadas():
        return 0

    producto = getattr(produccion, 'producto_terminado', None)
    nombre_producto = getattr(producto, 'Nombre', None) or f'producto #{produccion.IdProductoTerminado}'
    mensaje = (
        f'La produccion #{produccion.IdProduccion} de {nombre_producto} no pudo iniciarse '
        'por falta de materia prima.'
    )[:255]

    administradores = (
        db.session.query(Usuario)
        .join(Rol, Rol.IdRol == Usuario.IdRol)
        .filter(
            db.func.lower(Rol.Nombre) == 'administrador',
            Usuario.Activo.is_(True),
        )
        .all()
    )

    creadas = 0
    for admin in administradores:
        existente = (
            db.session.query(AlertaSistema.IdAlertaSistema)
            .filter_by(
                TipoAlerta=TIPO_ALERTA_MATERIAL_INSUFICIENTE,
                ReferenciaId=produccion.IdProduccion,
                IdUsuarioDestino=admin.IdUsuario,
                Leida=False,
            )
            .first()
        )
        if existente:
            continue

        db.session.add(
            AlertaSistema(
                TipoAlerta=TIPO_ALERTA_MATERIAL_INSUFICIENTE,
                ReferenciaId=produccion.IdProduccion,
                Mensaje=mensaje,
                IdUsuarioDestino=admin.IdUsuario,
            )
        )
        creadas += 1

    return creadas


def asegurar_produccion_aprobada(solicitud, id_usuario_registro):
    producciones = Produccion.query.filter_by(
        IdSolicitudProduccion=solicitud.IdSolicitudProduccion
    ).all()

    if not producciones:
        produccion = Produccion(
            IdSolicitudProduccion=solicitud.IdSolicitudProduccion,
            IdProductoTerminado=solicitud.IdProductoTerminado,
            CantidadPlaneada=solicitud.CantidadSolicitada,
            Estado='Aprobada',
            IdUsuarioRegistro=id_usuario_registro,
        )
        db.session.add(produccion)
        return [produccion]

    for produccion in producciones:
        produccion.Estado = 'Aprobada'

    return producciones
