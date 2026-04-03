from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, MateriaPrima, UnidadMedida, Proveedor, MovimientoMateriaPrima, Usuario
from sqlalchemy.orm import joinedload
from decimal import Decimal, InvalidOperation
from sqlalchemy import text
from datetime import datetime
from . import materia_prima_bp


@materia_prima_bp.route('/inventario')
def listar():
    search = request.args.get('search')
    query = MateriaPrima.query 
    
    if search:
        query = query.filter(MateriaPrima.Nombre.like(f'%{search}%'))
    
    materiales = query.all()
    return render_template('materia_prima/index.html', materiales=materiales, search=search)

@materia_prima_bp.route('/inventario/detalles/<int:id>')
def detalles(id):
    mp = MateriaPrima.query.get_or_404(id)
    return render_template('materia_prima/detalles.html', mp=mp)

@materia_prima_bp.route('/inventario/movimiento/<tipo>')
def formulario_movimiento(tipo):
    tipo_actual = request.args.get('tipo_mov', tipo).upper()
    
    materiales = MateriaPrima.query.filter_by(Activo=True).all()
    
    busqueda = request.args.get('id_mp_temp')
    
    material_info = None
    opciones_unidades = []

    if busqueda:
        if busqueda.isdigit():
            material_info = MateriaPrima.query.get(int(busqueda))
        
        if not material_info:
            material_info = MateriaPrima.query.filter_by(Nombre=busqueda, Activo=True).first()
        
        if material_info:
            if material_info.IdUnidadMedida == 1: # Masa
                opciones_unidades = [
                    {'val': 'G', 'label': 'Gramos (g)'},
                    {'val': 'KG', 'label': 'Kilos (kg)'}
                ]
            elif material_info.IdUnidadMedida == 2: 
                opciones_unidades = [
                    {'val': 'ML', 'label': 'Mililitros (ml)'},
                    {'val': 'L', 'label': 'Litros (L)'}
                ]
        
    return render_template('materia_prima/movimiento.html', 
                           tipo=tipo_actual, 
                           materiales=materiales, 
                           info=material_info,
                           unidades=opciones_unidades)

@materia_prima_bp.route('/inventario/movimiento/registrar', methods=['POST'])
def registrar_movimiento():
    id_mp = request.form.get('id_mp')
    tipo = request.form.get('tipo').upper()
    cantidad_raw = Decimal(request.form.get('cantidad') or '0')
    unidad_reg = request.form.get('unidad_registro') # L, ML, KG o G
    costo = Decimal(request.form.get('costo') or '0')
    motivo = request.form.get('motivo')
    id_usuario = session.get('user_id', 1)

    cantidad_final = cantidad_raw
    if unidad_reg in ['L', 'KG']:
        cantidad_final = cantidad_raw * 1000

    try:
        db.session.execute(
            text("CALL sp_registrar_movimiento_mp(:id, :tipo, :cant, :costo, :mot, :user)"),
            {
                'id': id_mp, 'tipo': tipo, 'cant': cantidad_final,
                'costo': costo, 'mot': motivo, 'user': id_usuario
            }
        )
        db.session.commit()
        flash(f"¡Éxito! {tipo} registrada correctamente.", "green")
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        if 'Stock insuficiente' in error_msg:
            flash("No puedes retirar esa cantidad. Supera el stock actual.", "red")
        else:
            flash(f"Error inesperado: {error_msg}", "red")
            
    return redirect(url_for('materia_prima.listar'))

@materia_prima_bp.route('/inventario/historial')
def historial():
    movimientos = MovimientoMateriaPrima.query.options(
        joinedload(MovimientoMateriaPrima.usuario).joinedload(Usuario.datos_personales),
        joinedload(MovimientoMateriaPrima.material)
    ).order_by(MovimientoMateriaPrima.FechaMovimiento.desc()).all()
    
    return render_template('materia_prima/historial.html', movimientos=movimientos)

@materia_prima_bp.route('/inventario/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    mp = MateriaPrima.query.get_or_404(id)
    if request.method == 'POST':
        mp.Nombre = request.form.get('nombre')
        mp.Marca = request.form.get('marca')
        mp.PrecioUnitario = request.form.get('precio')
        mp.StockMinimo = request.form.get('stock_minimo')
        mp.IdProveedor = request.form.get('id_proveedor')
        mp.Descripcion = request.form.get('descripcion')
        
        db.session.commit()
        flash("Material actualizado con éxito", "green")
        return redirect(url_for('materia_prima.detalles', id=id))
    
    proveedores = Proveedor.query.filter_by(Activo=True).all()
    return render_template('materia_prima/editar.html', mp=mp, proveedores=proveedores)

@materia_prima_bp.route('/inventario/nuevo', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        marca = request.form.get('marca')
        descripcion = request.form.get('descripcion')
        
        try:
            precio = Decimal(request.form.get('precio') or '0')
            stock_minimo = Decimal(request.form.get('stock_minimo') or '0')
            id_proveedor = request.form.get('id_proveedor')
            id_unidad = request.form.get('id_unidad_medida')
            
            nueva_mp = MateriaPrima(
                Nombre=nombre,
                Marca=marca,
                Descripcion=descripcion,
                PrecioUnitario=precio,
                StockMinimo=stock_minimo,
                StockActual=0,
                IdProveedor=id_proveedor,
                IdUnidadMedida=id_unidad,
                Activo=True
            )
            
            db.session.add(nueva_mp)
            db.session.commit()
            flash(f"Material '{nombre}' registrado exitosamente.", "green")
            return redirect(url_for('materia_prima.listar'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar: {str(e)}", "red")
            return redirect(url_for('materia_prima.agregar'))

    proveedores = Proveedor.query.filter_by(Activo=True).all()
    return render_template('materia_prima/agregar.html', proveedores=proveedores)

@materia_prima_bp.route('/inventario/desactivar/<int:id>')
def desactivar(id):
    mp = MateriaPrima.query.get_or_404(id)
    
    try:
        mp.Activo = False 
        db.session.commit()
        flash(f"El material {mp.Nombre} ha sido desactivado correctamente.", "green")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al intentar desactivar: {str(e)}", "red")
        
    return redirect(url_for('materia_prima.listar'))

@materia_prima_bp.route('/inventario/reactivar/<int:id>')
def reactivar(id):
    mp = MateriaPrima.query.get_or_404(id)
    
    try:
        mp.Activo = True 
        db.session.commit()
        flash(f"¡Éxito! El material {mp.Nombre} ha sido reactivado.", "green")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al intentar reactivar: {str(e)}", "red")
        
    return redirect(url_for('materia_prima.listar'))

@materia_prima_bp.route('/alerta/leer/<int:id_alerta>')
def leer_alerta(id_alerta):
    try:
        alerta = db.session.execute(
            text("SELECT ReferenciaId FROM alertasistema WHERE IdAlertaSistema = :id"),
            {'id': id_alerta}
        ).fetchone()

        if alerta:
            db.session.execute(
                text("UPDATE alertasistema SET Leida = 1, FechaLectura = :fecha WHERE IdAlertaSistema = :id"),
                {'fecha': datetime.now(), 'id': id_alerta}
            )
            db.session.commit()
            
            return redirect(url_for('materia_prima.detalles', id=alerta.ReferenciaId))
            
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
    
    return redirect(url_for('materia_prima.listar'))