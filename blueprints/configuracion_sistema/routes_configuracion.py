from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

import forms
from models import ConfiguracionSistema, db

from . import configuracion_sistema_bp


def _usuario_es_administrador():
    rol = (getattr(getattr(current_user, 'rol', None), 'Nombre', '') or '').lower().strip()
    return rol == 'administrador'


def _configuracion_actual():
    configuracion = (
        ConfiguracionSistema.query
        .order_by(ConfiguracionSistema.IdConfiguracion.desc())
        .first()
    )
    if configuracion is not None:
        return configuracion

    return ConfiguracionSistema(
        CantidadMinimaMateriaPrima=0,
        CantidadMinimaProductoTerminado=0,
        HorasInactividadCierreSesion=2,
        UnidadInactividadCierreSesion='HORAS',
        AlertarPocasPiezasTerminadas=True,
        AlertarMateriaPrimaMinima=True,
    )


def _unidad_inactividad(configuracion):
    unidad = (getattr(configuracion, 'UnidadInactividadCierreSesion', 'HORAS') or 'HORAS').upper()
    if unidad not in {'HORAS', 'MINUTOS'}:
        return 'HORAS'
    return unidad


def _cargar_formulario(formulario, configuracion):
    formulario.cantidad_minima_materia_prima.data = (
        int(configuracion.CantidadMinimaMateriaPrima or 0)
    )
    formulario.cantidad_minima_producto_terminado.data = (
        int(configuracion.CantidadMinimaProductoTerminado or 0)
    )
    formulario.horas_inactividad_cierre_sesion.data = (
        int(configuracion.HorasInactividadCierreSesion or 2)
    )
    formulario.unidad_inactividad_cierre_sesion.data = _unidad_inactividad(configuracion)
    formulario.alertar_pocas_piezas_terminadas.data = bool(
        configuracion.AlertarPocasPiezasTerminadas
    )
    formulario.alertar_materia_prima_minima.data = bool(
        configuracion.AlertarMateriaPrimaMinima
    )


def _flash_errores(formulario):
    for nombre_campo, errores in formulario.errors.items():
        campo = getattr(formulario, nombre_campo, None)
        etiqueta = None
        if campo is not None and getattr(campo, 'label', None) is not None:
            etiqueta = (campo.label.text or '').strip() or None

        for error in errores:
            if etiqueta:
                flash(f'{etiqueta}: {error}', 'warning')
            else:
                flash(error, 'warning')


def _preservar_campos_no_editables(formulario, configuracion):
    formulario.cantidad_minima_materia_prima.data = int(
        configuracion.CantidadMinimaMateriaPrima or 0
    )
    formulario.cantidad_minima_producto_terminado.data = int(
        configuracion.CantidadMinimaProductoTerminado or 0
    )


def _validar_tiempo_inactividad(formulario):
    unidad = (formulario.unidad_inactividad_cierre_sesion.data or 'HORAS').upper()
    valor = formulario.horas_inactividad_cierre_sesion.data

    if unidad == 'HORAS' and not 1 <= valor <= 72:
        flash('Si eliges horas, el tiempo debe estar entre 1 y 72.', 'warning')
        return False

    if unidad == 'MINUTOS' and not 1 <= valor <= 59:
        flash('Si eliges minutos, el tiempo debe estar entre 1 y 59.', 'warning')
        return False

    return True


def _nombre_usuario_actualiza(configuracion):
    usuario = getattr(configuracion, 'usuario_actualiza', None)
    persona = getattr(usuario, 'persona', None)
    if persona is None:
        return 'No disponible'
    nombre = (persona.Nombre or '').strip()
    apellidos = (persona.Apellidos or '').strip()
    return f'{nombre} {apellidos}'.strip() or 'No disponible'


@configuracion_sistema_bp.route('/configuracion-sistema', methods=['GET', 'POST'])
@login_required
def editar():
    if not _usuario_es_administrador():
        flash('No tienes permisos para acceder a la configuracion del sistema.', 'warning')
        return redirect(url_for('dashboard.dashboard'))

    configuracion = (
        ConfiguracionSistema.query
        .order_by(ConfiguracionSistema.IdConfiguracion.desc())
        .first()
    )
    form = forms.ConfiguracionSistemaForm(request.form if request.method == 'POST' else None)

    if request.method == 'GET':
        configuracion_vista = configuracion or _configuracion_actual()
        _cargar_formulario(form, configuracion_vista)
        return render_template(
            'configuracion_sistema/index.html',
            form=form,
            configuracion=configuracion_vista,
            actualizado_por=_nombre_usuario_actualiza(configuracion_vista),
            active='opciones',
        )

    configuracion_base = configuracion or _configuracion_actual()
    _preservar_campos_no_editables(form, configuracion_base)

    if form.validate() and _validar_tiempo_inactividad(form):
        if configuracion is None:
            configuracion = ConfiguracionSistema()
            db.session.add(configuracion)

        configuracion.CantidadMinimaMateriaPrima = form.cantidad_minima_materia_prima.data
        configuracion.CantidadMinimaProductoTerminado = (
            form.cantidad_minima_producto_terminado.data
        )
        configuracion.HorasInactividadCierreSesion = (
            form.horas_inactividad_cierre_sesion.data
        )
        configuracion.UnidadInactividadCierreSesion = (
            form.unidad_inactividad_cierre_sesion.data
        )
        configuracion.AlertarPocasPiezasTerminadas = bool(
            form.alertar_pocas_piezas_terminadas.data
        )
        configuracion.AlertarMateriaPrimaMinima = bool(
            form.alertar_materia_prima_minima.data
        )
        configuracion.FechaActualizacion = datetime.now()
        configuracion.IdUsuarioActualiza = current_user.IdUsuario

        db.session.commit()
        flash('Configuracion del sistema actualizada correctamente.', 'success')
        return redirect(url_for('configuracion_sistema.editar'))

    _flash_errores(form)
    configuracion_vista = configuracion or _configuracion_actual()
    return render_template(
        'configuracion_sistema/index.html',
        form=form,
        configuracion=configuracion_vista,
        actualizado_por=_nombre_usuario_actualiza(configuracion_vista),
        active='opciones',
    )
