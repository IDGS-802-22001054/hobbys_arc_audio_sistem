from models import Produccion, db


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
