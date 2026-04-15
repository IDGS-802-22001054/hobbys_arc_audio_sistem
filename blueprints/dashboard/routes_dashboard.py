from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import text
from models import SolicitudProduccion, db

from services.configuracion import (
    alertas_materia_prima_habilitadas,
    alertas_pocas_piezas_habilitadas,
)
from services.produccion import asegurar_produccion_aprobada

dashboard_bp = Blueprint('dashboard', __name__)

PERIODOS_VALIDOS = {'semana', 'mes', 'anio'}

DIAS_ES = {
    'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mie',
    'Thu': 'Jue', 'Fri': 'Vie', 'Sat': 'Sab', 'Sun': 'Dom'
}

MESES_ES = {
    'Jan': 'Ene', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Abr',
    'May': 'May', 'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago',
    'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dec': 'Dic'
}


def _formatear_etiqueta(row, periodo):
    if periodo == 'semana':
        fmt = row.Etiqueta.strftime('%a %d')
        dia, num = fmt.split(' ')
        return f"{DIAS_ES.get(dia, dia)} {num}"

    if periodo == 'mes':
        fmt = row.FechaInicioSemana.strftime('%d %b')
        num, mes = fmt.split(' ')
        return f"{num} {MESES_ES.get(mes, mes)}"

    fmt = datetime.strptime(row.Mes, '%Y-%m').strftime('%b %y')
    mes, anio = fmt.split(' ')
    return f"{MESES_ES.get(mes, mes)} {anio}"


def _usuario_es_administrador():
    rol = (getattr(getattr(current_user, 'rol', None), 'Nombre', '') or '').lower().strip()
    return rol == 'administrador'


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    periodo = request.args.get('periodo', 'semana')
    if periodo not in PERIODOS_VALIDOS:
        periodo = 'semana'

    kpis = db.session.execute(
        text('CALL SP_Dashboard_KPIsHoy()')
    ).fetchone()

    venta_total = float(kpis.VentaTotal or 0)
    utilidad_total = float(kpis.UtilidadTotal or 0)

    top_ganancia_actual = db.session.execute(
        text('CALL SP_Dashboard_TopGananciaSemanaActual()')
    ).fetchone()

    top_unidades_actual = db.session.execute(
        text('CALL SP_Dashboard_TopUnidadesSemanaActual()')
    ).fetchone()

    top_ganancia_anterior = db.session.execute(
        text('CALL SP_Dashboard_TopGananciaSemanaAnterior()')
    ).fetchone()

    top_unidades_anterior = db.session.execute(
        text('CALL SP_Dashboard_TopUnidadesSemanaAnterior()')
    ).fetchone()

    alertas_stock = []
    if alertas_pocas_piezas_habilitadas():
        alertas_stock = db.session.execute(
            text('CALL SP_Dashboard_AlertasStockProducto()')
        ).fetchall()

    alertas_mp = []
    if alertas_materia_prima_habilitadas():
        alertas_mp = db.session.execute(
            text('CALL SP_Dashboard_AlertasStockMateriaPrima()')
        ).fetchall()

    sp_map = {
        'semana': 'CALL SP_Dashboard_GraficaSemana()',
        'mes': 'CALL SP_Dashboard_GraficaMes()',
        'anio': 'CALL SP_Dashboard_GraficaAnio()',
    }

    filas_grafica = db.session.execute(
        text(sp_map[periodo])
    ).fetchall()

    datos_grafica = [
        {
            'etiqueta': _formatear_etiqueta(row, periodo),
            'ventas': float(row.Ventas or 0),
            'utilidad': float(row.Utilidad or 0),
        }
        for row in filas_grafica
    ]

    defectos = db.session.execute(
        text('CALL SP_Dashboard_Defectos()')
    ).fetchall()

    datos_defectos = [
        {
            'etiqueta': row.Etiqueta.strftime('%d/%m') if row.Etiqueta else '',
            'alto': int(row.Alto or 0),
            'medio': int(row.Medio or 0),
            'bajo': int(row.Bajo or 0),
            'porcentaje': float(row.PorcentajeDefectos or 0)
        }
        for row in defectos
    ]

    return render_template(
        'dashboard/dashboard.html',
        venta_total=venta_total,
        utilidad_total=utilidad_total,

        top_ganancia_actual=top_ganancia_actual,
        top_unidades_actual=top_unidades_actual,
        top_ganancia_anterior=top_ganancia_anterior,
        top_unidades_anterior=top_unidades_anterior,

        alertas_stock=alertas_stock,
        alertas_mp=alertas_mp,

        datos_grafica=datos_grafica,
        datos_defectos=datos_defectos,

        periodo=periodo,
    )


@dashboard_bp.route('/dashboard/reabastecimiento', methods=['POST'])
@login_required
def solicitar_reabastecimiento():
    id_producto = request.form.get('id_producto', type=int)
    cantidad = request.form.get('cantidad', type=int, default=1)

    if not id_producto or cantidad <= 0:
        flash('Datos inválidos.', 'warning')
        return redirect(url_for('dashboard.dashboard'))

    es_admin = _usuario_es_administrador()

    db.session.execute(
        text('CALL SP_SolicitudProduccion_Crear(:id_producto, :cantidad, :motivo, :id_usuario)'),
        {
            'id_producto': id_producto,
            'cantidad': cantidad,
            'motivo': 'Reabastecimiento automático desde dashboard',
            'id_usuario': current_user.IdUsuario,
        }
    )

    if es_admin:
        solicitud = (
            SolicitudProduccion.query
            .filter_by(
                IdProductoTerminado=id_producto,
                IdUsuarioSolicita=current_user.IdUsuario,
            )
            .order_by(SolicitudProduccion.IdSolicitudProduccion.desc())
            .first()
        )

        if solicitud:
            solicitud.Estado = 'Aprobada'
            solicitud.IdUsuarioAprueba = current_user.IdUsuario
            solicitud.FechaAprobacion = datetime.now()
            solicitud.ObservacionesAprobacion = 'Aprobación automática desde dashboard'

            asegurar_produccion_aprobada(solicitud, current_user.IdUsuario)

    db.session.commit()

    flash(
        'Solicitud generada correctamente.' if not es_admin
        else 'Solicitud generada y aprobada automáticamente.',
        'success'
    )

    return redirect(url_for('dashboard.dashboard'))