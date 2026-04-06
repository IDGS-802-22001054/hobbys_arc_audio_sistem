from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import text
from models import db

produccion_bp = Blueprint('produccion', __name__)

@produccion_bp.route('/produccion')
@login_required
def produccion():
    producciones_aprobadas = db.session.execute(
        text('CALL SP_Produccion_ListarPorEstado(:estado)'),
        {'estado': 'Aprobada'}
    ).fetchall()

    producciones_proceso = db.session.execute(
        text('CALL SP_Produccion_ListarPorEstado(:estado)'),
        {'estado': 'En proceso'}
    ).fetchall()

    producciones_completadas = db.session.execute(
        text('CALL SP_Produccion_CompletadasHoy()')
    ).fetchall()

    kpis = db.session.execute(
        text('CALL SP_Produccion_KPIsHoy()')
    ).fetchone()

    aprobadas = kpis.Aprobadas if kpis else 0
    en_proceso = kpis.EnProceso if kpis else 0
    completadas = kpis.Completadas if kpis else 0
    total_defectuosas = kpis.TotalDefectuosas if kpis else 0

    return render_template(
        'produccion/producciones.html', 
        producciones_aprobadas=producciones_aprobadas,
        producciones_proceso=producciones_proceso,
        producciones_completadas=producciones_completadas,
        aprobadas=aprobadas,
        en_proceso=en_proceso,
        completadas=completadas,
        total_defectuosas=total_defectuosas,
    )

@produccion_bp.route('/produccion/<int:id>/iniciar', methods=['POST'])
@login_required
def iniciar(id: int):
    db.session.execute(
        text('CALL SP_Produccion_Iniciar(:id_produccion, :id_usuario, @ok, @mensaje)'),
        {'id_produccion': id, 'id_usuario': current_user.IdUsuario}
    )
    db.session.commit()

    salida = db.session.execute(
        text('SELECT @ok AS ok, @mensaje AS mensaje')
    ).fetchone()

    if salida and salida.ok:
        flash(f'Producción #{id} iniciada. Materia prima descontada.', 'success')
    else:
        mensaje = salida.mensaje if salida else 'Error al iniciar la producción.'
        flash(mensaje, 'danger')

    return redirect(url_for('produccion.produccion'))

@produccion_bp.route('/produccion/<int:id>/defectos', methods=['GET', 'POST'])
@login_required
def registrar_defectos(id: int):
    prod = db.session.execute(
        text('CALL SP_Produccion_Ver(:id)'), {'id': id}
    ).fetchone()

    if prod is None:
        abort(404)

    if prod.Estado != 'En proceso':
        flash('Solo se pueden registrar defectos en producciones en proceso.', 'warning')
        return redirect(url_for('produccion.produccion'))

    if request.method == 'POST':
        cantidad = request.form.get('cantidad', type=int, default=0)
        descripcion = request.form.get('descripcion', '').strip()

        if cantidad <= 0:
            flash('La cantidad de defectos debe ser mayor a 0.', 'warning')
            return redirect(url_for('produccion.registrar_defectos', id=id))

        db.session.execute(
            text('CALL SP_Produccion_RegistrarDefecto(:id_produccion, :cantidad, :descripcion, :id_usuario)'),
            {
                'id_produccion': id,
                'cantidad': cantidad,
                'descripcion': descripcion or None,
                'id_usuario': current_user.IdUsuario,
            }
        )
        db.session.commit()

        flash(f'{cantidad} pieza(s) defectuosa(s) registrada(s).', 'success')
        return redirect(url_for('produccion.produccion'))

    return render_template('produccion/defectos.html', prod=prod)  

@produccion_bp.route('/produccion/<int:id>/finalizar', methods=['GET', 'POST'])
@login_required
def finalizar(id: int):
    prod = db.session.execute(
        text('CALL SP_Produccion_Ver(:id)'), {'id': id}
    ).fetchone()

    if prod is None:
        abort(404)

    if prod.Estado != 'En proceso':
        flash('Solo se puede finalizar una producción en proceso.', 'warning')
        return redirect(url_for('produccion.produccion'))

    if request.method == 'POST':
        cantidad_buenas = request.form.get('cantidad_buenas', type=int)
        cantidad_defectuosas = request.form.get('cantidad_defectuosas', type=int, default=0)

        if cantidad_buenas is None or cantidad_buenas < 0:
            flash('Debes indicar la cantidad de piezas buenas.', 'warning')
            return redirect(url_for('produccion.finalizar', id=id))

        total = cantidad_buenas + cantidad_defectuosas
        if total > prod.CantidadPlaneada:
            flash(
                f'La suma ({total}) supera la cantidad planeada ({prod.CantidadPlaneada}).',
                'warning'
            )
            return redirect(url_for('produccion.finalizar', id=id))

        db.session.execute(
            text('CALL SP_Produccion_Finalizar(:id_produccion, :cantidad_buenas, :cantidad_defectuosas, :id_usuario)'),
            {
                'id_produccion': id,
                'cantidad_buenas': cantidad_buenas,
                'cantidad_defectuosas': cantidad_defectuosas,
                'id_usuario': current_user.IdUsuario,
            }
        )
        db.session.commit()

        flash(
            f'Producción #{id} finalizada. '
            f'{cantidad_buenas} pzas buenas ingresadas al inventario.',
            'success'
        )
        return redirect(url_for('produccion.produccion'))

    return render_template('produccion/finalizar.html', prod=prod) 

@produccion_bp.route('/produccion/<int:id>/cancelar', methods=['POST'])
@login_required
def cancelar(id: int):
    if not current_user.es_admin:
        abort(403)

    prod = db.session.execute(
        text('CALL SP_Produccion_Ver(:id)'), {'id': id}
    ).fetchone()

    if prod is None:
        abort(404)

    if prod.Estado != 'En proceso':
        flash('Solo se pueden cancelar producciones en proceso.', 'warning')
        return redirect(url_for('produccion.produccion'))

    db.session.execute(
        text('CALL SP_Produccion_Cancelar(:id_produccion, :id_usuario)'),
        {'id_produccion': id, 'id_usuario': current_user.IdUsuario}
    )
    db.session.commit()

    flash(f'Producción #{id} cancelada. Materia prima revertida al stock.', 'info')
    return redirect(url_for('produccion.produccion'))

@produccion_bp.route('/produccion/<int:id>/detalle')
@login_required
def detalle(id: int):
    prod = db.session.execute(
        text('CALL SP_Produccion_Ver(:id)'), {'id': id}
    ).fetchone()

    if prod is None:
        abort(404)

    defectos = db.session.execute(
        text('CALL SP_Produccion_ListarDefectos(:id_produccion)'),
        {'id_produccion': id}
    ).fetchall()

    return render_template('produccion/detalle.html', prod=prod, defectos=defectos)