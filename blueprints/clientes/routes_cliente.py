from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from sqlalchemy.orm import joinedload
from datetime import datetime
from decimal import Decimal
from models import db, Usuario, SesionUsuario, Cliente, Rol, Venta, VentaDetalle
from forms import LoginForm, ClienteForm
from flask_mail import Message
from extensions import mail
import forms, base64, random, string

clientes_bp = Blueprint('clientes', __name__, url_prefix='/clientes')

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

def _generar_codigo() -> str:
    return ''.join(random.choices(string.digits, k=6))


def _enviar_codigo_verificacion(correo: str, codigo: str, nombre: str):
    try:
        msg = Message(
            subject='Código de verificación para inicio de sesión.',
            recipients=[correo],
            body=f"""Hola {nombre},
            
            {codigo}

        Este código expira en 10 minutos. Si no solicitaste crear una cuenta, ignora este mensaje. \n\n"""
        f"Si tienes problemas para acceder, comunícate con el administrador.\n\n"
            f"Saludos,\n"
            f"Equipo de administración"
        )
        
        mail.send(msg)
        return True
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Error al enviar código a {correo}: {e}')
        return False

@clientes_bp.route('/nuevo', methods=['GET', 'POST'])
def nuevo_cliente():
    form = forms.ClienteForm(request.form)

    if request.method == 'POST' and request.form.get('action') == 'enviar_codigo':

        identificador = request.form.get('identificador', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('password_confirm', '')
        nombre = request.form.get('nombre', '').strip()
        correo = request.form.get('correo', '').strip()

        if password != confirm:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        if not identificador:
            flash('El nombre de usuario es requerido.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        if len(password) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        correo_existe = db.session.execute(
            text('SELECT COUNT(*) FROM Persona WHERE CorreoElectronico = :correo'),
            {'correo': correo}
        ).scalar()
        if correo_existe:
            flash('El correo electrónico ya está registrado.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        usuario_existe = db.session.execute(
            text('SELECT COUNT(*) FROM Usuario WHERE Identificador = :id'),
            {'id': identificador}
        ).scalar()
        if usuario_existe:
            flash('El nombre de usuario ya está en uso.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        codigo = _generar_codigo()
        session['verificacion'] = {
            'codigo': codigo,
            'expira': (datetime.now() + timedelta(minutes=10)).isoformat(),
            'correo': correo,
            'nombre': nombre,
            'apellidos': request.form.get('apellidos', '').strip(),
            'identificador': identificador,
            'password_hash': generate_password_hash(password),
        }

        exito = _enviar_codigo_verificacion(correo, codigo, nombre)

        if not exito:
            flash('No se pudo enviar el correo de verificación. Intenta de nuevo.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        return render_template(
            'cliente/registrar.html',
            form=form,
            mostrar_modal=True,
            correo_enmascarado=_enmascarar_correo(correo)
        )

    if request.method == 'POST' and request.form.get('action') == 'verificar':

        codigo_ingresado = request.form.get('codigo_verificacion', '').strip()
        datos = session.get('verificacion')

        if not datos:
            flash('La sesión de verificación expiró. Intenta de nuevo.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        if datetime.now() > datetime.fromisoformat(datos['expira']):
            session.pop('verificacion', None)
            flash('El código expiró. Vuelve a intentarlo.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        if codigo_ingresado != datos['codigo']:
            return render_template(
                'cliente/registrar.html',
                form=form,
                mostrar_modal=True,
                error_codigo=True,
                correo_enmascarado=_enmascarar_correo(datos['correo'])
            )

        rol_cliente_id = obtener_rol_cliente_id()
        if rol_cliente_id is None:
            flash('No existe el rol Cliente. Contacta al administrador.', 'danger')
            return render_template('cliente/registrar.html', form=form)

        try:
            db.session.execute(
                text('CALL SP_Clientes_Registrar(:nombre, :apellidos, :correo, '
                     ':identificador, :password_hash, :id_rol, '
                     ':calle, :colonia, :numero_exterior, :numero_interior, :codigo_postal, @id_cliente)'),
                {
                    'nombre': datos['nombre'],
                    'apellidos': datos['apellidos'],
                    'correo': datos['correo'],
                    'identificador': datos['identificador'],
                    'password_hash': datos['password_hash'],
                    'id_rol': rol_cliente_id,
                    'calle': None,
                    'colonia': None,
                    'numero_exterior': None,
                    'numero_interior': None,
                    'codigo_postal': None,
                }
            )
            db.session.commit()

            session.pop('verificacion', None)  

            usuario = db.session.query(Usuario).filter_by(
                Identificador=datos['identificador']
            ).first()

            if usuario:
                nueva_sesion = SesionUsuario(
                    IdUsuario = usuario.IdUsuario,
                    FechaInicio = datetime.now(),
                    FechaUltimaActividad = datetime.now(),
                    Activa = True
                )
                db.session.add(nueva_sesion)
                db.session.commit()
                login_user(usuario, remember=False)
                flash('¡Cuenta creada y correo verificado! Bienvenido.', 'success')
                return redirect(url_for('catalogo_cliente.catalogo'))

        except OperationalError as e:
            db.session.rollback()
            mensaje = str(e.orig.args[1]) if e.orig else 'Error al registrar la cuenta.'
            flash(mensaje, 'danger')

    return render_template('cliente/registrar.html', form=form)


def _enmascarar_correo(correo: str) -> str:
    if '@' not in correo:
        return correo
    usuario, dominio = correo.split('@', 1)
    if len(usuario) <= 2:
        return correo
    return usuario[:2] + '*' * (len(usuario) - 2) + '@' + dominio

@clientes_bp.route('/reenviar-codigo', methods=['POST'])
def reenviar_codigo():
    from flask import jsonify
    datos = session.get('verificacion')

    if not datos:
        return jsonify({'ok': False, 'mensaje': 'Sesión expirada. Vuelve a llenar el formulario.'})

    nuevo_codigo = _generar_codigo()
    datos['codigo'] = nuevo_codigo
    datos['expira'] = (datetime.now() + timedelta(minutes=10)).isoformat()
    session['verificacion'] = datos
    session.modified = True

    exito = _enviar_codigo_verificacion(datos['correo'], nuevo_codigo, datos['nombre'])

    if exito:
        return jsonify({'ok': True, 'mensaje': 'Código reenviado correctamente.'})
    return jsonify({'ok': False, 'mensaje': 'No se pudo reenviar el correo. Intenta de nuevo.'})

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
        abort(404)

    form = forms.ClienteForm(request.form)

    if request.method == 'GET':
        form.nombre.data = fila.Nombre
        form.apellidos.data = fila.Apellidos
        form.correo.data = fila.CorreoElectronico
        form.telefono.data = fila.Telefono
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
                'id': id,
                'nombre': form.nombre.data.strip(),
                'apellidos': form.apellidos.data.strip(),
                'telefono': form.telefono.data,
                'correo': form.correo.data.strip(),
                'foto': nueva_foto,
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
    return render_template('cliente/verPerfil.html', cliente=cliente, persona=persona, active='perfil')


@clientes_bp.route('/perfil/historial-compras', methods=['GET'])
@login_required
def historial_compras():
    cliente = db.session.query(Cliente).filter_by(
        IdPersona=current_user.IdPersona
    ).first_or_404()

    ventas = (
        db.session.query(Venta)
        .options(
            joinedload(Venta.detalles).joinedload(VentaDetalle.producto_terminado)
        )
        .filter(Venta.IdCliente == cliente.IdCliente)
        .order_by(Venta.FechaVenta.desc(), Venta.IdVenta.desc())
        .all()
    )

    total_gastado = sum((venta.TotalVenta for venta in ventas), Decimal("0.00"))
    total_productos = sum((sum(detalle.Cantidad for detalle in venta.detalles) for venta in ventas), 0)
    ultima_compra = ventas[0].FechaVenta if ventas else None

    return render_template(
        'cliente/historial_compras.html',
        cliente=cliente,
        ventas=ventas,
        total_gastado=total_gastado,
        total_compras=len(ventas),
        total_productos=total_productos,
        ultima_compra=ultima_compra,
        active='historial',
    )

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
                'telefono': form.telefono.data,
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