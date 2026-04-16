from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from models import db, Empleado, Persona, Usuario, Rol
from werkzeug.security import generate_password_hash
from sqlalchemy import text
from datetime import datetime
from flask_login import login_required, current_user
from flask_mail import Message
from extensions import mail

import forms
import base64
import unicodedata
import re
import random
import string

empleados_bp = Blueprint('empleados', __name__)

TAMANO_MAXIMO = 2 * 1024 * 1024

FIRMAS = [
    (b'\xff\xd8\xff', 'jpeg'),
    (b'\x89PNG\r\n\x1a\n', 'png'),
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
        flash('La foto no debe superar 2 MB.', 'warning')
        return None
    tipo = detectar_tipo(imagen_bytes)
    if tipo is None:
        flash('Formato de imagen no permitido. Use JPG, PNG, GIF o WEBP.', 'warning')
        return None
    encoded = base64.b64encode(imagen_bytes).decode('utf-8')
    return f'data:image/{tipo};base64,{encoded}'


def _datos_direccion_form(form):
    return {
        'calle': (form.calle.data or '').strip() or None,
        'colonia': (form.colonia.data or '').strip() or None,
        'numero_exterior': (form.numero_exterior.data or '').strip() or None,
        'numero_interior': (form.numero_interior.data or '').strip() or None,
        'codigo_postal': (form.codigo_postal.data or '').strip() or None,
    }


def _rol_actual():
    return (getattr(getattr(current_user, 'rol', None), 'Nombre', '') or '').lower().strip()


def _requiere_administrador():
    if not current_user.is_authenticated:
        abort(401)
    if _rol_actual() != 'administrador':
        abort(403)


def _roles_activos():
    return db.session.execute(text('CALL SP_Roles_ListarActivos()')).fetchall()


def _puestos_desde_roles(roles):
    puestos = []
    for rol in roles:
        nombre = (rol.Nombre or '').strip()
        nombre_normalizado = nombre.lower()
        if (
            not nombre
            or 'usuario' in nombre_normalizado
            or 'consulta' in nombre_normalizado
            or 'cliente' in nombre_normalizado
        ):
            continue
        puestos.append(nombre)
    return puestos


def _texto_seguro_para_identificador(texto):
    texto = unicodedata.normalize('NFKD', (texto or '').strip().lower())
    texto = ''.join(caracter for caracter in texto if not unicodedata.combining(caracter))
    texto = re.sub(r'[^a-z0-9]+', '.', texto)
    return texto.strip('.')


def _generar_identificador_unico(nombre, apellidos):
    primer_nombre = (_texto_seguro_para_identificador(nombre).split('.') or ['empleado'])[0]
    primer_apellido = (_texto_seguro_para_identificador(apellidos).split('.') or [''])[0]
    base = '.'.join(parte for parte in [primer_nombre, primer_apellido] if parte) or 'empleado'

    candidato = base
    consecutivo = 1
    while db.session.execute(
        text('SELECT COUNT(*) FROM Usuario WHERE Identificador = :identificador'),
        {'identificador': candidato}
    ).scalar():
        consecutivo += 1
        candidato = f'{base}{consecutivo}'

    return candidato


def _generar_password_temporal(longitud=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=longitud))


def enviar_credenciales_por_correo(correo, nombre, identificador, password_plano):
    try:
        msg = Message(
            subject='Credenciales de acceso - Hobbys Car Audio',
            recipients=[correo],
            body=(
                f"Hola {nombre},\n\n"
                f"Tus credenciales de acceso son:\n"
                f"Usuario: {identificador}\n"
                f"Contraseña: {password_plano}\n\n"
                f"Al iniciar sesión deberás cambiar tu contraseña.\n"
                f"Si no solicitaste este acceso, contacta al administrador."
            )
        )
        mail.send(msg)
        return True
    except Exception as error:
        flash(f'No se pudo enviar el correo de credenciales: {error}', 'warning')
        return False

@empleados_bp.route('/empleados', methods=['GET'])
@login_required
def empleados():
    _requiere_administrador()
    q = request.args.get('q', '').strip()
    resultado = db.session.execute(text('CALL SP_Empleados_Listar()'))
    lista = resultado.fetchall()

    if q:
        q_lower = q.lower()
        if q_lower in ('activo', 'activos'):
            lista = [e for e in lista if e.Activo == 1]
        elif q_lower in ('inactivo', 'inactivos'):
            lista = [e for e in lista if e.Activo == 0]
        else:
            lista = [e for e in lista if
                     q_lower in (e.Nombre or '').lower() or
                     q_lower in (e.Apellidos or '').lower() or
                     q_lower in (e.Puesto or '').lower() or
                     q_lower in (e.CorreoElectronico or '').lower() or
                     q_lower in (e.Identificador or '').lower() or
                     q_lower in (e.NombreRol or '').lower() or
                     q_lower in str(e.IdEmpleado)]

    return render_template('empleado/empleados.html', empleados=lista, q=q)


@empleados_bp.route('/empleados/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_empleado():
    _requiere_administrador()
    form = forms.EmpleadoForm(request.form)
    roles = _roles_activos()
    puestos = _puestos_desde_roles(roles)
 
    if request.method == 'POST':
        foto_b64  = foto_a_base64(request.files.get('foto'))
        direccion = _datos_direccion_form(form)
        nombre = (form.nombre.data or '').strip()
        apellidos = (form.apellidos.data or '').strip()
        correo = (form.correo.data or '').strip()
        identificador = None
        password_plano = None
        rol_id = form.id_rol.data or None

        correo_existente = db.session.query(Persona.IdPersona).filter(
            db.func.lower(Persona.CorreoElectronico) == correo.lower()
        ).first()
        if correo_existente:
            flash('El correo ya está registrado. Use uno diferente.')
            return render_template(
                'empleado/registrar.html',
                form=form,
                roles=roles,
                puestos=puestos,
            )
 
        password_hash = None
        if rol_id:
            identificador = _generar_identificador_unico(nombre, apellidos)
            password_plano = _generar_password_temporal()
            password_hash = generate_password_hash(password_plano)
 
        db.session.execute(
            text(
                'CALL SP_Empleados_Registrar('
                ':nombre, :apellidos, :telefono, :correo, '
                ':calle, :colonia, :numero_exterior, :numero_interior, :codigo_postal, '
                ':foto, :puesto, :fecha_ingreso, :salario, '
                ':identificador, :password_hash, :id_rol, @id_empleado)'
            ),
            {
                'nombre': nombre,
                'apellidos': apellidos,
                'telefono': form.telefono.data,
                'correo': correo,
                'foto': foto_b64,
                'puesto': form.puesto.data,
                'fecha_ingreso': datetime.now(),
                'salario':       form.salario.data,
                'identificador': identificador,
                'password_hash': password_hash,
                'id_rol':        rol_id,
                **direccion,
            }
        )
        db.session.commit()

        usuario = None
        if identificador:
            usuario = db.session.execute(
                text('SELECT IdUsuario FROM Usuario WHERE Identificador = :id'),
                {'id': identificador}
            ).fetchone()

        if usuario:
            db.session.execute(
                text('UPDATE Usuario SET DebeCambiarCredenciales = 1 WHERE IdUsuario = :id'),
                {'id': usuario.IdUsuario}
            )
            db.session.commit()

        if identificador and password_plano:
            enviar_credenciales_por_correo(correo, nombre, identificador, password_plano)
            flash(f'Empleado registrado. Usuario asignado: {identificador}. Se envió el correo con credenciales.', 'success')
            return redirect(url_for('empleados.empleados'))

        flash('Empleado registrado correctamente.', 'success')
        return redirect(url_for('empleados.empleados'))

    return render_template('empleado/registrar.html', form=form, roles=roles, puestos=puestos)


@empleados_bp.route('/empleados/cambiar-credenciales', methods=['GET', 'POST'])
@login_required
def cambiar_credenciales():
    if request.method == 'POST':
        nueva_pass = request.form.get('password', '').strip()
        confirmar = request.form.get('confirmar_password', '').strip()

        errores = []
        if not nueva_pass or len(nueva_pass) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres.')
        if nueva_pass != confirmar:
            errores.append('Las contraseñas no coinciden.')

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('empleado/cambiar_credenciales.html')

        nuevo_hash = generate_password_hash(nueva_pass)
        db.session.execute(
            text('''
                UPDATE Usuario
                SET PasswordHash = :hash,
                    DebeCambiarCredenciales = 0
                WHERE IdUsuario = :id
            '''),
            {'hash': nuevo_hash, 'id': current_user.IdUsuario}
        )
        db.session.commit()

        flash('Contraseña actualizada. Ya puedes usar el sistema.', 'success')
        return redirect(url_for('dashboard.dashboard'))

    return render_template('empleado/cambiar_contraseña.html')

@empleados_bp.route('/empleados/ver/<int:id>', methods=['GET'])
@login_required
def ver_empleado(id):
    _requiere_administrador()
    fila = db.session.execute(
        text('CALL SP_Empleados_Ver(:id)'), {'id': id}
    ).fetchone()
    if fila is None:
        from flask import abort; abort(404)
    return render_template('empleado/detalle.html', e=fila)


@empleados_bp.route('/empleados/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_empleado(id):
    _requiere_administrador()
    form = forms.EmpleadoForm(request.form)

    if request.method == 'GET':
        fila = db.session.execute(
            text('CALL SP_Empleados_Ver(:id)'), {'id': id}
        ).fetchone()
        if fila is None:
            from flask import abort; abort(404)

        form.nombre.data = fila.Nombre
        form.apellidos.data = fila.Apellidos
        form.telefono.data = fila.Telefono
        form.correo.data = fila.CorreoElectronico
        form.calle.data = fila.Calle
        form.colonia.data = fila.Colonia
        form.numero_exterior.data = fila.NumeroExterior
        form.numero_interior.data = fila.NumeroInterior
        form.codigo_postal.data = fila.CodigoPostal
        form.puesto.data = fila.Puesto
        form.salario.data = fila.Salario
        form.identificador.data = fila.Identificador
        form.id_rol.data = fila.IdRol

    if request.method == 'POST':
        nueva_foto = foto_a_base64(request.files.get('foto'))
        direccion = _datos_direccion_form(form)
        password_hash = None
        if form.password.data:
            password_hash = generate_password_hash(form.password.data)

        db.session.execute(
            text(
                'CALL SP_Empleados_Actualizar('
                ':id_empleado, :nombre, :apellidos, :telefono, :correo, '
                ':calle, :colonia, :numero_exterior, :numero_interior, :codigo_postal, '
                ':foto, :puesto, :salario, :identificador, :password_hash, :id_rol)'
            ),
            {
                'id_empleado': id,
                'nombre': form.nombre.data.strip(),
                'apellidos': form.apellidos.data.strip(),
                'telefono': form.telefono.data,
                'correo': form.correo.data.strip(),
                'foto': nueva_foto,
                'puesto': form.puesto.data,
                'salario': form.salario.data,
                'identificador': form.identificador.data.strip(),
                'password_hash': password_hash,
                'id_rol': form.id_rol.data,
                **direccion,
            }
        )
        db.session.commit()
        flash('Empleado actualizado correctamente.', 'success')
        return redirect(url_for('empleados.empleados'))
 
    roles = _roles_activos()
    return render_template('empleado/editar.html', form=form, roles=roles, id=id)


@empleados_bp.route('/empleados/eliminar/<int:id>', methods=['GET', 'POST'])
@login_required
def eliminar_empleado(id):
    _requiere_administrador()
    fila = db.session.execute(
        text('CALL SP_Empleados_Ver(:id)'), {'id': id}
    ).fetchone()
    if fila is None:
        from flask import abort; abort(404)

    if request.method == 'POST':
        db.session.execute(text('CALL SP_Empleados_Eliminar(:id)'), {'id': id})
        db.session.commit()
        flash('Empleado desactivado correctamente.', 'success')
        return redirect(url_for('empleados.empleados'))

    return render_template('empleado/eliminar.html', e=fila, p=fila)


@empleados_bp.route('/empleados/activar/<int:id>', methods=['POST'])
@login_required
def activar_empleado(id):
    _requiere_administrador()
    db.session.execute(text('CALL SP_Empleados_Activar(:id)'), {'id': id})
    db.session.commit()
    flash('Empleado activado correctamente.', 'success')
    return redirect(url_for('empleados.empleados'))


@empleados_bp.route('/perfil/editar', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    form = forms.EmpleadoForm(request.form)

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
            text(
                '''
                UPDATE Persona
                SET
                    Nombre = :nombre,
                    Apellidos = :apellidos,
                    Telefono = :telefono,
                    CorreoElectronico = :correo,
                    Calle = :calle,
                    Colonia = :colonia,
                    NumeroExterior = :numero_exterior,
                    NumeroInterior = :numero_interior,
                    CodigoPostal = :codigo_postal,
                    Foto = COALESCE(NULLIF(:foto, ''), Foto)
                WHERE IdPersona = :id_persona
                '''
            ),
            {
                'id_persona': current_user.IdPersona,
                'nombre': form.nombre.data.strip(),
                'apellidos': form.apellidos.data.strip(),
                'telefono': form.telefono.data,
                'correo': form.correo.data.strip(),
                'foto': nueva_foto,
                **direccion,
            }
        )
        db.session.execute(
            text(
                '''
                UPDATE Usuario
                SET
                    Identificador = :identificador,
                    PasswordHash = COALESCE(:password_hash, PasswordHash)
                WHERE IdUsuario = :id_usuario
                '''
            ),
            {
                'id_usuario': current_user.IdUsuario,
                'identificador': form.identificador.data.strip(),
                'password_hash': password_hash,
            }
        )
        db.session.commit()
        flash('Perfil actualizado correctamente.', 'success')
        return redirect(url_for('empleados.editar_perfil'))

    return render_template('empleado/editarPerfil.html', form=form)

@empleados_bp.route('/empleados/reenviar-credenciales/<int:id>')
@login_required
def reenviar_credenciales(id):
    _requiere_administrador()
    fila = db.session.execute(
        text('CALL SP_Empleados_Ver(:id)'), {'id': id}
    ).fetchone()

    if fila is None:
        from flask import abort
        abort(404)

    correo = fila.CorreoElectronico
    nombre = fila.Nombre
    identificador = fila.Identificador

    password_plano = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    password_hash = generate_password_hash(password_plano)

    db.session.execute(
        text("""
            UPDATE Usuario 
            SET PasswordHash = :hash,
                DebeCambiarCredenciales = 1
            WHERE Identificador = :identificador
        """),
        {
            'hash': password_hash,
            'identificador': identificador
        }
    )
    db.session.commit()

    enviar_credenciales_por_correo(correo, nombre, identificador, password_plano)

    flash('Credenciales reenviadas correctamente al empleado.', 'success')
    return redirect(url_for('empleados.editar_empleado', id=id))
