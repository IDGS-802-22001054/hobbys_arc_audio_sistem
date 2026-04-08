from flask import render_template, request, send_file, Response
from models import db, ProductoTerminado, Venta, CorteVentaDiario
from sqlalchemy import func
from datetime import date, datetime
from . import costos_utilidades_bp
from flask_login import login_required
import pandas as pd
from io import BytesIO

@costos_utilidades_bp.route('/costos-utilidades')
@login_required
def listar():
    hoy = date.today()
    productos = ProductoTerminado.query.filter_by(Activo=True).all()
    corte_existente = CorteVentaDiario.query.filter_by(FechaCorte=hoy).first()
    
    corte_vista = corte_existente if corte_existente else CorteVentaDiario(FechaCorte=hoy)

    return render_template('costos_utilidades/index.html', 
                           productos=productos, 
                           corte=corte_vista)

@costos_utilidades_bp.route('/configurar-reporte')
@login_required
def configurar_reporte():
    return render_template('costos_utilidades/reportes_filtro.html', hoy=date.today())

@costos_utilidades_bp.route('/generar-archivo-reporte')
@login_required
def generar_archivo_reporte():
    f_ini = request.args.get('f_inicio')
    f_fin = request.args.get('f_fin')
    formato = request.args.get('formato')

    ventas = Venta.query.filter(db.func.date(Venta.FechaVenta).between(f_ini, f_fin)).all()

    if formato == 'excel':
        return exportar_excel(ventas, f_ini, f_fin)
    
    return render_template('costos_utilidades/reporte_pdf.html', 
                           ventas=ventas, 
                           f_ini=f_ini, 
                           f_fin=f_fin,
                           hoy=datetime.now())

def exportar_excel(ventas, f_ini, f_fin):
    data = []
    for v in ventas:
        for d in v.detalles:
            costo = d.producto_terminado.CostoProduccion if d.producto_terminado else 0
            data.append({
                'Fecha': v.FechaVenta.strftime('%d/%m/%Y'),
                'ID Venta': v.IdVenta,
                'Producto': d.producto_terminado.Nombre,
                'Cantidad': d.Cantidad,
                'Precio Unit.': d.PrecioUnitario,
                'Total Venta': d.Subtotal,
                'Costo Fab.': costo * d.Cantidad,
                'Utilidad': float(d.Subtotal) - (float(costo) * d.Cantidad)
            })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte Financiero')
    output.seek(0)
    
    return send_file(output, download_name=f"Reporte_{f_ini}_{f_fin}.xlsx", as_attachment=True)