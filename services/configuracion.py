from datetime import timedelta

from flask import g, has_request_context

from models import ConfiguracionSistema


def _configuracion_predeterminada():
    return ConfiguracionSistema(
        CantidadMinimaMateriaPrima=0,
        CantidadMinimaProductoTerminado=0,
        HorasInactividadCierreSesion=2,
        UnidadInactividadCierreSesion='HORAS',
        AlertarPocasPiezasTerminadas=True,
        AlertarMateriaPrimaMinima=True,
    )


def obtener_configuracion_sistema():
    if has_request_context():
        configuracion = getattr(g, '_configuracion_sistema', None)
        if configuracion is not None:
            return configuracion

    configuracion = (
        ConfiguracionSistema.query
        .order_by(ConfiguracionSistema.IdConfiguracion.desc())
        .first()
    )
    if configuracion is None:
        configuracion = _configuracion_predeterminada()

    if has_request_context():
        g._configuracion_sistema = configuracion

    return configuracion


def obtener_parametros_inactividad_sesion():
    configuracion = obtener_configuracion_sistema()
    valor = getattr(configuracion, 'HorasInactividadCierreSesion', 2) or 2
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        valor = 2

    unidad = (getattr(configuracion, 'UnidadInactividadCierreSesion', 'HORAS') or 'HORAS').upper()
    if unidad not in {'HORAS', 'MINUTOS'}:
        unidad = 'HORAS'

    return {
        'valor': max(1, valor),
        'unidad': unidad,
    }


def obtener_duracion_inactividad_sesion():
    parametros = obtener_parametros_inactividad_sesion()
    if parametros['unidad'] == 'MINUTOS':
        return timedelta(minutes=parametros['valor'])
    return timedelta(hours=parametros['valor'])


def obtener_milisegundos_inactividad_sesion():
    return int(obtener_duracion_inactividad_sesion().total_seconds() * 1000)


def alertas_pocas_piezas_habilitadas():
    return bool(getattr(obtener_configuracion_sistema(), 'AlertarPocasPiezasTerminadas', True))


def alertas_materia_prima_habilitadas():
    return bool(getattr(obtener_configuracion_sistema(), 'AlertarMateriaPrimaMinima', True))
