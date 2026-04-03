from flask import render_template, request, redirect, url_for, flash
from . import proveedores_bp
from models import db, Proveedor

@proveedores_bp.route("/proveedores")
def listar():
    search = request.args.get('search', '')
    if search:
        proveedores = Proveedor.query.filter(
            (Proveedor.NombreEmpresa.like(f"%{search}%")) | 
            (Proveedor.RFC.like(f"%{search}%"))
        ).all()
    else:
        proveedores = Proveedor.query.all()
    
    return render_template("proveedores/index.html", 
                           proveedores=proveedores, 
                           active='proveedores', 
                           search=search)

@proveedores_bp.route("/proveedores/nuevo", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        rfc_input = request.form.get('rfc').upper()
        
        existe = Proveedor.query.filter_by(RFC=rfc_input).first()
        if existe:
            flash(f"Error: El RFC {rfc_input} ya se encuentra registrado.", "red")
            return redirect(url_for("proveedores.registrar"))

        try:
            nuevo = Proveedor(
                NombreEmpresa=request.form.get('nombre'),
                RFC=rfc_input,
                Telefono=request.form.get('telefono'),
                CorreoElectronico=request.form.get('correo'),
                Direccion=request.form.get('direccion'),
                Activo=True 
            )
            db.session.add(nuevo)
            db.session.commit()
            flash("Proveedor registrado exitosamente.", "success")
            return redirect(url_for("proveedores.listar"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar: {str(e)}", "red")
            return redirect(url_for("proveedores.registrar"))

    return render_template("proveedores/agregar.html", active='proveedores')

@proveedores_bp.route("/proveedores/detalles/<int:id>")
def detalles(id):
    proveedor = Proveedor.query.get_or_404(id)
    
    return render_template("proveedores/detalles.html", p=proveedor, active='proveedores')

@proveedores_bp.route("/proveedores/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    p = Proveedor.query.get_or_404(id)
    
    if request.method == "POST":
        try:
            p.NombreEmpresa = request.form.get('nombre')
            p.Telefono = request.form.get('telefono')
            p.CorreoElectronico = request.form.get('correo')
            p.Direccion = request.form.get('direccion')
            
            
            db.session.commit()
            flash(f"Proveedor {p.NombreEmpresa} actualizado correctamente.", "success")
            return redirect(url_for("proveedores.listar"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al actualizar: {str(e)}", "red")
            return redirect(url_for("proveedores.editar", id=id))

    return render_template("proveedores/editar.html", p=p, active='proveedores')

@proveedores_bp.route("/proveedores/desactivar/<int:id>")
def desactivar(id):
    try:
        p = Proveedor.query.get_or_404(id)
        p.Activo = False
        db.session.commit()
        flash(f"El proveedor {p.NombreEmpresa} ha sido desactivado.", "warning")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al desactivar: {str(e)}", "red")
        
    return redirect(url_for("proveedores.listar"))

@proveedores_bp.route('/proveedores/reactivar/<int:id>')
def reactivar(id):
    proveedor = Proveedor.query.get_or_404(id)
    
    try:
        proveedor.Activo = True 
        db.session.commit()
        flash(f"¡Éxito! El proveedor {proveedor.NombreEmpresa} ha sido reactivado.", "green")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al intentar reactivar al proveedor: {str(e)}", "red")
        
    return redirect(url_for('proveedores.listar'))