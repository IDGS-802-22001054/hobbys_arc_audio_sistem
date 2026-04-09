from flask import Blueprint, render_template, request, redirect, url_for, flash
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

def _normalizar(texto):
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    texto = texto.lower()
    texto = re.sub(r'[^a-z0-9]', '', texto)
    return texto


def generar_identificador(nombre, apellidos):
    partes_nombre = nombre.strip().split()
    primer_nombre = _normalizar(partes_nombre[0]) if partes_nombre else 'usuario'

    partes_apellidos = apellidos.strip().split()
    inicial_ap1 = _normalizar(partes_apellidos[0])[0] if len(partes_apellidos) > 0 else ''
    inicial_ap2 = _normalizar(partes_apellidos[1])[0] if len(partes_apellidos) > 1 else ''

    base = primer_nombre + inicial_ap1 + inicial_ap2

    existe = db.session.execute(
        text('SELECT COUNT(*) FROM Usuario WHERE Identificador = :id'),
        {'id': base}
    ).scalar()

    if not existe:
        return base

    contador = 2
    while True:
        candidato = f'{base}{contador}'
        existe = db.session.execute(
            text('SELECT COUNT(*) FROM Usuario WHERE Identificador = :id'),
            {'id': candidato}
        ).scalar()
        if not existe:
            return candidato
        contador += 1


def generar_password(nombre, apellidos, telefono):
    simbolos = '!@#$%&*'

    partes_nombre = nombre.strip().split()
    inicial_nombre = _normalizar(partes_nombre[0])[0].upper() if partes_nombre else 'U'

    partes_apellidos = apellidos.strip().split()
    dos_ap1 = _normalizar(partes_apellidos[0])[:2] if partes_apellidos else 'xx'

    digitos_tel = re.sub(r'\D', '', telefono or '')
    ultimos4 = digitos_tel[-4:] if len(digitos_tel) >= 4 else digitos_tel.zfill(4)

    simbolo = random.choice(simbolos)
    base = inicial_nombre + dos_ap1 + ultimos4 + simbolo

    while len(base) < 8:
        base += random.choice(string.ascii_lowercase + string.digits)

    return base


def enviar_credenciales_por_correo(correo_destino, nombre, identificador, password_plano):
    try:
        msg      = Message(subject='Bienvenido al sistema — Tus credenciales de acceso')
        msg.recipients = [correo_destino]
        msg.body = (
            f"Hola {nombre},\n\n"
            f"Se ha creado tu cuenta de acceso al sistema.\n\n"
            f"  Usuario:     {identificador}\n"
            f"  Contraseña:  {password_plano}\n\n"
            f"IMPORTANTE: Al iniciar sesión por primera vez el sistema te pedirá\n"
            f"cambiar tu contraseña. No podrás usar el sistema hasta\n"
            f"que realices ese cambio. Se recomienda también que cambies tu usuario,\n\n"
            f"pero eso lo puedes hacer desde tu perfil dando click en el icono\n\n"
            f"superior derecha.\n\n"
            f"Si tienes problemas para acceder, comunícate con el administrador.\n\n"
            f"Saludos,\n"
            f"Equipo de administración"
        )
        mail.send(msg)
    except Exception as e:
        print(f'[ERROR correo] {e}')
        flash('Empleado registrado, pero no se pudo enviar el correo con credenciales.', 'warning')

@empleados_bp.route('/empleados', methods=['GET'])
def empleados():
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
def nuevo_empleado():
    form = forms.EmpleadoForm(request.form)

    if request.method == 'POST':
        foto_b64  = foto_a_base64(request.files.get('foto'))
        direccion = _datos_direccion_form(form)

        nombre = (form.nombre.data or '').strip()
        apellidos = (form.apellidos.data or '').strip()
        telefono  = (form.telefono.data or '').strip()
        correo = (form.correo.data or '').strip()

        identificador  = generar_identificador(nombre, apellidos)
        password_plano = generar_password(nombre, apellidos, telefono)
        password_hash  = generate_password_hash(password_plano)

        db.session.execute(
            text(
                'CALL SP_Empleados_Registrar('
                ':nombre, :apellidos, :telefono, :correo, '
                ':calle, :colonia, :numero_exterior, :numero_interior, :codigo_postal, '
                ':foto, :puesto, :fecha_ingreso, :salario, '
                ':identificador, :password_hash, :id_rol, @id_empleado)'
            ),
            {
                'nombre':        nombre,
                'apellidos':     apellidos,
                'telefono':      telefono,
                'correo':        correo,
                'foto':          foto_b64,
                'puesto':        form.puesto.data,
                'fecha_ingreso': datetime.now(),
                'salario':       form.salario.data,
                'identificador': identificador,
                'password_hash': password_hash,
                'id_rol':        form.id_rol.data or None,
                **direccion,
            }
        )
        db.session.commit()

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

        enviar_credenciales_por_correo(correo, nombre, identificador, password_plano)

        flash(f'Empleado registrado. Usuario asignado: {identificador}. Se envió el correo con credenciales.', 'success')
        return redirect(url_for('empleados.empleados'))

    roles = db.session.execute(text('CALL SP_Roles_ListarActivos()')).fetchall()
    return render_template('empleado/registrar.html', form=form, roles=roles)


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
def ver_empleado(id):
    fila = db.session.execute(
        text('CALL SP_Empleados_Ver(:id)'), {'id': id}
    ).fetchone()
    if fila is None:
        from flask import abort; abort(404)
    return render_template('empleado/detalle.html', e=fila)


@empleados_bp.route('/empleados/editar/<int:id>', methods=['GET', 'POST'])
def editar_empleado(id):
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

    roles = db.session.execute(text('CALL SP_Roles_ListarActivos()')).fetchall()
    return render_template('empleado/editar.html', form=form, roles=roles, id=id)


@empleados_bp.route('/empleados/eliminar/<int:id>', methods=['GET', 'POST'])
def eliminar_empleado(id):
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
def activar_empleado(id):
    db.session.execute(text('CALL SP_Empleados_Activar(:id)'), {'id': id})
    db.session.commit()
    flash('Empleado activado correctamente.', 'success')
    return redirect(url_for('empleados.empleados'))


@empleados_bp.route('/perfil/editar', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    empleado = db.session.query(Empleado).filter_by(
        IdPersona=current_user.IdPersona
    ).first_or_404()

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
                'CALL SP_Perfil_ActualizarPerfil('
                ':id_empleado, :nombre, :apellidos, :telefono, :correo, '
                ':calle, :colonia, :numero_exterior, :numero_interior, :codigo_postal, '
                ':foto, :identificador, :password_hash)'
            ),
            {
                'id_empleado': empleado.IdEmpleado,
                'nombre': form.nombre.data.strip(),
                'apellidos': form.apellidos.data.strip(),
                'telefono': form.telefono.data,
                'correo': form.correo.data.strip(),
                'foto': nueva_foto,
                'identificador': form.identificador.data.strip(),
                'password_hash': password_hash,
                **direccion,
            }
        )
        db.session.commit()
        flash('Perfil actualizado correctamente.', 'success')
        return redirect(url_for('empleados.ver_perfil'))

    return render_template('empleado/editarPerfil.html', form=form)