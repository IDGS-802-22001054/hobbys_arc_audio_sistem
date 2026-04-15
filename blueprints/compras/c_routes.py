from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from models import db, CompraMateriaPrima, CompraMateriaPrimaDetalle, MateriaPrima, Proveedor, UnidadMedida
from sqlalchemy import text
from . import compras_bp
from sqlalchemy import case, or_, func
from sqlalchemy.exc import SQLAlchemyError
from flask_login import current_user, login_required

@compras_bp.route('/compras')
@login_required
def listar():
    search = request.args.get('search', '').strip()
    cantidad_real = case(
        (
            func.lower(func.coalesce(UnidadMedida.Abreviatura, '')).in_(['g', 'ml']),
            CompraMateriaPrimaDetalle.Cantidad / 1000.0,
        ),
        else_=CompraMateriaPrimaDetalle.Cantidad,
    )
    
    query_base = db.session.query(
        CompraMateriaPrima.IdCompraMateriaPrima.label('id'),
        CompraMateriaPrima.FechaCompra.label('fecha'),
        Proveedor.NombreEmpresa.label('proveedor_nombre'),
        func.sum(cantidad_real * CompraMateriaPrimaDetalle.CostoUnitario).label('total'),
        CompraMateriaPrima.Observaciones.label('obs')
    ).outerjoin(Proveedor, CompraMateriaPrima.IdProveedor == Proveedor.IdProveedor)\
     .outerjoin(CompraMateriaPrimaDetalle, CompraMateriaPrima.IdCompraMateriaPrima == CompraMateriaPrimaDetalle.IdCompraMateriaPrima)\
     .outerjoin(MateriaPrima, CompraMateriaPrimaDetalle.IdMateriaPrima == MateriaPrima.IdMateriaPrima)\
     .outerjoin(UnidadMedida, MateriaPrima.IdUnidadMedida == UnidadMedida.IdUnidadMedida)

    if search:
        query_base = query_base.filter(
            or_(
                CompraMateriaPrima.FechaCompra.like(f"%{search}%"),
                Proveedor.NombreEmpresa.like(f"%{search}%"),
                MateriaPrima.Nombre.like(f"%{search}%"),
                CompraMateriaPrima.IdCompraMateriaPrima.like(f"%{search}%")
            )
        )

    compras = query_base.group_by(
        CompraMateriaPrima.IdCompraMateriaPrima, 
        CompraMateriaPrima.FechaCompra, 
        Proveedor.NombreEmpresa, 
        CompraMateriaPrima.Observaciones
    ).order_by(CompraMateriaPrima.IdCompraMateriaPrima.desc()).all()

    return render_template('compras/index.html', compras=compras, active='compras')

@compras_bp.route('/nueva', methods=['GET', 'POST'])
@login_required
def nueva_compra():
    id_usuario = current_user.IdUsuario

    if request.method == 'POST':
        accion = request.form.get('accion')
        raw_id_prov = request.form.get('id_proveedor')
        id_prov = int(raw_id_prov) if raw_id_prov and raw_id_prov.isdigit() else None
        obs = request.form.get('observaciones')

        if accion == 'agregar_tmp':
            if not id_prov:
                flash("Error: Seleccione un proveedor antes de agregar productos.", "error")
                return redirect(url_for('compras.nueva_compra'))

            id_mp = request.form.get('id_mp')
            uni = request.form.get('unidad')
            costo = float(request.form.get('costo') or 0)
            cant_user = float(request.form.get('cantidad') or 0)
            
            cant_final = cant_user * 1000 if uni in ['Kg', 'L'] else cant_user
            
            mp = db.session.get(MateriaPrima, id_mp)
            if mp:
                db.session.execute(
                    text("""INSERT INTO tmp_compra_detalle 
                         (IdUsuario, IdMateriaPrima, NombreMateria, Cantidad, UnidadMedida, CostoUnitario, IdProveedor, Observaciones) 
                         VALUES (:u, :m, :n, :can, :uni, :cos, :p, :o)"""),
                    {'u': id_usuario, 'm': id_mp, 'n': mp.Nombre, 'can': cant_final, 
                     'uni': uni, 'cos': costo, 'p': id_prov, 'o': obs}
                )
                db.session.execute(
                    text("UPDATE tmp_compra_detalle SET IdProveedor = :p, Observaciones = :o WHERE IdUsuario = :u"),
                    {'p': id_prov, 'o': obs, 'u': id_usuario}
                )
                db.session.commit()
                flash("Materia prima agregada al borrador.", "success")
            else:
                flash("La materia prima seleccionada no existe.", "error")
            return redirect(url_for('compras.nueva_compra'))

        if accion and accion.startswith('eliminar_item_'):
            id_tmp = accion.replace('eliminar_item_', '')
            db.session.execute(
                text("DELETE FROM tmp_compra_detalle WHERE IdTmp = :id AND IdUsuario = :u"),
                {'id': id_tmp, 'u': id_usuario}
            )
            db.session.commit()
            flash("Producto eliminado del borrador.", "success")
            return redirect(url_for('compras.nueva_compra'))

        if accion == 'finalizar':
            if not id_prov:
                flash("Error: Seleccione un proveedor antes de guardar.")
                return redirect(url_for('compras.nueva_compra'))

            borrador = db.session.execute(
                text("SELECT COUNT(*) FROM tmp_compra_detalle WHERE IdUsuario = :u"),
                {'u': id_usuario}
            ).scalar()
            if not borrador:
                flash("Agrega al menos una materia prima antes de guardar la compra.", "error")
                return redirect(url_for('compras.nueva_compra'))

            try:
                resultado = db.session.execute(
                    text("CALL sp_FinalizarCompraDesdeTmp(:p, :o, :u)"),
                    {'p': id_prov, 'o': obs, 'u': id_usuario}
                )
                resultado.close()
                db.session.commit()
                flash("Compra registrada correctamente.", "success")
                return redirect(url_for('compras.listar'))
            except SQLAlchemyError:
                db.session.rollback()
                current_app.logger.exception("No fue posible finalizar la compra de materia prima.")
                flash("No fue posible guardar la compra de materia prima.", "error")
                return redirect(url_for('compras.nueva_compra'))

    carrito_raw = db.session.execute(
        text("SELECT * FROM tmp_compra_detalle WHERE IdUsuario = :u"), 
        {'u': id_usuario}
    ).fetchall()
    
    datos_persistentes = carrito_raw[0] if carrito_raw else None
    proveedores = Proveedor.query.filter_by(Activo=True).all()
    materias = MateriaPrima.query.all()
    
    return render_template('compras/agregar.html', 
                           proveedores=proveedores, 
                           materias=materias, 
                           carrito=carrito_raw,
                           persist=datos_persistentes,
                           active='compras')

@compras_bp.route('/detalle/<int:id>')
@login_required
def ver_detalle(id):
    compra = db.session.get(CompraMateriaPrima, id)

    if not compra:
        flash("La compra no existe.", "error")
        return redirect(url_for('compras.listar'))

    detalles_procesados = []
    total_compra = 0

    for d in compra.detalles:
        abreviatura_db = d.materia_prima.unidad_medida.Abreviatura.lower()
        
        cantidad_base = float(d.Cantidad)
        costo_base = float(d.CostoUnitario)

        if abreviatura_db in ['g', 'kg']:
            cantidad_visual = cantidad_base / 1000.0 if abreviatura_db == 'g' else cantidad_base
            unidad_visual = 'Kg'
        elif abreviatura_db in ['ml', 'l']:
            cantidad_visual = cantidad_base / 1000.0 if abreviatura_db == 'ml' else cantidad_base
            unidad_visual = 'L'
        else:
            cantidad_visual = cantidad_base
            unidad_visual = d.materia_prima.unidad_medida.Abreviatura

        subtotal = cantidad_visual * costo_base
        total_compra += subtotal

        detalles_procesados.append({
            'Nombre': d.materia_prima.Nombre,
            'CantidadVisual': cantidad_visual,
            'unidad': unidad_visual,
            'CostoUnitario': costo_base,
            'Subtotal': subtotal
        })

    return render_template('compras/detalles.html', 
                           compra=compra, 
                           detalles=detalles_procesados, 
                           total=total_compra,
                           active='compras')
