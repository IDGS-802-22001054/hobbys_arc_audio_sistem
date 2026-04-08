from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from datetime import datetime
from models import db, Usuario, SesionUsuario, Cliente, Rol
from forms import LoginForm, ClienteForm

import forms, base64

clientes_bp = Blueprint('clientes', __name__, url_prefix='/clientes')

DESTINOS_POR_ROL = {
    'cliente': 'catalogo.catalogo',
}

TAMANO_MAXIMO = 2 * 1024 * 1024

FIRMAS = [
    (b'\xff\xd8\xff', 'jpeg'),
    (b'\x89PNG\r\n\x1a\n',  'png'),
    (b'GIF87a', 'gif'),
    (b'GIF89a', 'gif'),
    (b'RIFF', 'webp'),
]

def detectar_tipo(imagen_bytes):
    for firma, tipo in FIRMAS:
        if imagen_bytes.startswith(firma):
            return tipo
    return None

def foto_a_base64(archivo):
    if not archivo or archivo.filename == '':
        return None
    imagen_bytes = archivo.read()
    if len(imagen_bytes) > TAMANO_MAXIMO:
        flash('La foto no debe superar 2 MB.')
        return None
    tipo = detectar_tipo(imagen_bytes)
    if tipo is None:
        flash('Formato de imagen no permitido. Use JPG, PNG, GIF o WEBP.')
        return None
    encoded = base64.b64encode(imagen_bytes).decode('utf-8')
    return f'data:image/{tipo};base64,{encoded}'


def obtener_rol_cliente_id():
    rol = db.session.query(Rol).filter(
        db.func.lower(Rol.Nombre) == 'cliente'
    ).first()
    return rol.IdRol if rol else None


def _datos_direccion_form(form):
    return {
        'calle': (form.calle.data or '').strip() or None,
        'colonia': (form.colonia.data or '').strip() or None,
        'numero_exterior': (form.numero_exterior.data or '').strip() or None,
        'numero_interior': (form.numero_interior.data or '').strip() or None,
        'codigo_postal': (form.codigo_postal.data or '').strip() or None,
    }

@clientes_bp.route('/clientes', methods=['GET'])
def clientes():
    q = request.args.get('q', '').strip()
    resultado = db.session.execute(text('CALL SP_Clientes_Listar()'))
    lista = resultado.fetchall()

    if q:
        q_lower = q.lower()
        if q_lower in ('activo', 'activos'):
            lista = [c for c in lista if c.Activo == 1]
        elif q_lower in ('inactivo', 'inactivos'):
            lista = [c for c in lista if c.Activo == 0]
        else:
            lista = [c for c in lista if
                     q_lower in (c.Nombre or '').lower() or
                     q_lower in (c.Apellidos or '').lower() or
                     q_lower in (c.CorreoElectronico or '').lower() or
                     q_lower in (c.Telefono or '').lower() or
                     q_lower in (c.Identificador or '').lower() or
                     q_lower in str(c.IdCliente)]

    return render_template('cliente/clientes.html', clientes=lista, q=q)

@clientes_bp.route('/nuevo', methods=['GET', 'POST'])
def nuevo_cliente():
    form = forms.ClienteForm(request.form)

    if request.method == 'POST':
        identificador = request.form.get('identificador', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('password_confirm', '')

        if password != confirm:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        if not identificador:
            flash('El nombre de usuario es requerido.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        rol_cliente_id = obtener_rol_cliente_id()
        if rol_cliente_id is None:
            flash('No existe el rol Cliente en la tabla Rol.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        password_hash  = generate_password_hash(password)

        try:
            direccion = _datos_direccion_form(form)
            db.session.execute(
                text('CALL SP_Clientes_Registrar(:nombre, :apellidos, :correo, '
                     ':identificador, :password_hash, :id_rol, '
                     ':calle, :colonia, :numero_exterior, :numero_interior, :codigo_postal, @id_cliente)'),
                {
                    'nombre': form.nombre.data,
                    'apellidos': form.apellidos.data,
                    'correo': form.correo.data,
                    'identificador': identificador,
                    'password_hash': password_hash,
                    'id_rol':        rol_cliente_id,
                    **direccion,
                }
            )
            db.session.commit()

            usuario = db.session.query(Usuario).filter_by(
                Identificador=identificador
            ).first()

            if usuario:
                usuario.FechaUltimoAcceso = datetime.now()
                nueva_sesion = SesionUsuario(
                    IdUsuario = usuario.IdUsuario,
                    FechaInicio = datetime.now(),
                    FechaUltimaActividad = datetime.now(),
                    Activa = True
                )
                db.session.add(nueva_sesion)
                db.session.commit()
                login_user(usuario, remember=False)
                rol = usuario.rol.Nombre.lower().strip()
                flash('Cuenta creada correctamente. ¡Bienvenido!', 'success')
                return redirect(url_for('catalogo_cliente.catalogo'))

        except OperationalError as e:
            db.session.rollback()
            mensaje = str(e.orig.args[1]) if e.orig else 'Error al registrar la cuenta.'
            flash(mensaje, 'danger')

    return render_template('cliente/registrar.html', form=form)

@clientes_bp.route('/ver/<int:id>', methods=['GET'])
def ver_cliente(id):
    fila = db.session.execute(
        text('CALL SP_Clientes_Ver(:id)'), {'id': id}
    ).fetchone()
    if fila is None:
        abort(404)
    return render_template('cliente/detalle.html', c=fila)

@clientes_bp.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    fila = db.session.execute(
        text('CALL SP_Clientes_Ver(:id)'), {'id': id}
    ).fetchone()

    if fila is None:
        from flask import abort
        abort(404)

    form = forms.ClienteForm(request.form)

    if request.method == 'GET':
        form.nombre.data    = fila.Nombre
        form.apellidos.data = fila.Apellidos
        form.correo.data    = fila.CorreoElectronico
        form.telefono.data  = fila.Telefono
        form.calle.data = fila.Calle
        form.colonia.data = fila.Colonia
        form.numero_exterior.data = fila.NumeroExterior
        form.numero_interior.data = fila.NumeroInterior
        form.codigo_postal.data = fila.CodigoPostal

    if request.method == 'POST':
        nueva_foto = foto_a_base64(request.files.get('foto'))
        direccion = _datos_direccion_form(form)

        db.session.execute(
            text('CALL SP_Clientes_Editar(:id, :nombre, :apellidos, '
                 ':telefono, :correo, :calle, :colonia, :numero_exterior, :numero_interior, :codigo_postal, :foto)'),
            {
                'id':        id,
                'nombre':    form.nombre.data.strip(),
                'apellidos': form.apellidos.data.strip(),
                'telefono':  form.telefono.data,
                'correo':    form.correo.data.strip(),
                'foto':      nueva_foto,
                **direccion,
            }
        )
        db.session.commit()
        flash('Cliente actualizado correctamente.', 'success')
        return redirect(url_for('clientes.ver_cliente', id=id))

    return render_template('cliente/editar.html', form=form, c=fila)

@clientes_bp.route('/clientes/eliminar/<int:id>', methods=['GET', 'POST'])
def eliminar_cliente(id):
    fila = db.session.execute(
        text('CALL SP_Clientes_Ver(:id)'), {'id': id}
    ).fetchone()
    if fila is None:
        abort(404)
    if request.method == 'POST':
        db.session.execute(text('CALL SP_Clientes_Desactivar(:id)'), {'id': id})
        db.session.commit()
        flash('Cliente desactivado correctamente.')
        return redirect(url_for('clientes.clientes'))
    return render_template('cliente/eliminar.html', c=fila, p=fila)

@clientes_bp.route('/activar/<int:id>', methods=['POST'])
def activar_cliente(id):
    db.session.execute(text('CALL SP_Clientes_Activar(:id)'), {'id': id})
    db.session.commit()
    flash('Cliente activado correctamente.')
    return redirect(url_for('clientes.clientes'))

@clientes_bp.route('/perfil', methods=['GET'])
@login_required
def ver_perfil():
    cliente = db.session.query(Cliente).filter_by(
        IdPersona=current_user.IdPersona
    ).first_or_404()
    persona = current_user.persona
    return render_template('cliente/verPerfil.html', cliente=cliente, persona=persona)

@clientes_bp.route('/perfil/editar', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    cliente = db.session.query(Cliente).filter_by(
        IdPersona=current_user.IdPersona
    ).first_or_404()

    form = forms.ClientePerfilForm(request.form)

    if request.method == 'GET':
        persona = current_user.persona
        form.nombre.data = persona.Nombre
        form.apellidos.data = persona.Apellidos
        form.telefono.data = persona.Telefono
        form.correo.data = persona.CorreoElectronico
        form.calle.data = persona.Calle
        form.colonia.data = persona.Colonia
        form.numero_exterior.data = persona.NumeroExterior
        form.numero_interior.data = persona.NumeroInterior
        form.codigo_postal.data = persona.CodigoPostal
        form.identificador.data = current_user.Identificador

    if request.method == 'POST':
        nueva_foto = foto_a_base64(request.files.get('foto'))
        direccion = _datos_direccion_form(form)

        password_hash = None
        if form.password.data:
            password_hash = generate_password_hash(form.password.data)

        db.session.execute(
            text('CALL SP_Perfil_ActualizarCliente(:id_cliente, :nombre, :apellidos, '
                 ':telefono, :correo, :calle, :colonia, :numero_exterior, :numero_interior, :codigo_postal, :foto, '
                 ':identificador, :password_hash)'),
            {
                'id_cliente': cliente.IdCliente,
                'nombre': form.nombre.data.strip(),
                'apellidos': form.apellidos.data.strip(),
                'telefono':form.telefono.data,
                'correo': form.correo.data.strip(),
                'foto': nueva_foto,
                'identificador': form.identificador.data.strip(),
                'password_hash': password_hash,
                **direccion,
            }
        )
        db.session.commit()
        flash('Perfil actualizado correctamente.')
        return redirect(url_for('catalogo_cliente.catalogo')) 

    return render_template('cliente/editarPerfil.html', form=form)
