from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import text
from models import db

dashboard_bp = Blueprint('dashboard', __name__)

PERIODOS_VALIDOS = {'semana', 'mes', 'anio'}

DIAS_ES = {
    'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mié',
    'Thu': 'Jue', 'Fri': 'Vie', 'Sat': 'Sáb', 'Sun': 'Dom'
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
    elif periodo == 'mes':
        fmt = row.FechaInicioSemana.strftime('%d %b')
        num, mes = fmt.split(' ')
        return f"{num} {MESES_ES.get(mes, mes)}"
    else:
        fmt = datetime.strptime(row.Mes, '%Y-%m').strftime('%b %y')
        mes, anio = fmt.split(' ')
        return f"{MESES_ES.get(mes, mes)} {anio}"


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():

    periodo = request.args.get('periodo', 'semana')
    if periodo not in PERIODOS_VALIDOS:
        periodo = 'semana'

    kpis = db.session.execute(
        text('CALL SP_Dashboard_KPIsHoy()')
    ).fetchone()

    venta_total = float(kpis.VentaTotal) if kpis and kpis.VentaTotal else 0.0
    utilidad_total = float(kpis.UtilidadTotal) if kpis and kpis.UtilidadTotal else 0.0

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

    alertas_stock = db.session.execute(
        text('CALL SP_Dashboard_AlertasStockProducto()')
    ).fetchall()

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
            'ventas': float(row.Ventas),
            'utilidad': float(row.Utilidad),
        }
        for row in filas_grafica
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
        periodo=periodo,
    )


@dashboard_bp.route('/dashboard/reabastecimiento', methods=['POST'])
@login_required
def solicitar_reabastecimiento():
    id_producto = request.form.get('id_producto', type=int)
    cantidad = request.form.get('cantidad', type=int, default=1)

    if not id_producto or cantidad <= 0:
        flash('Datos inválidos para la solicitud.', 'warning')
        return redirect(url_for('dashboard.dashboard'))

    db.session.execute(
        text('CALL SP_SolicitudProduccion_Crear(:id_producto, :cantidad, :motivo, :id_usuario)'),
        {
            'id_producto': id_producto,
            'cantidad': cantidad,
            'motivo': 'Reabastecimiento automático desde dashboard (stock bajo)',
            'id_usuario': current_user.IdUsuario,
        }
    )
    db.session.commit()

    flash('Solicitud de reabastecimiento generada correctamente.', 'success')
    return redirect(url_for('dashboard.dashboard'))