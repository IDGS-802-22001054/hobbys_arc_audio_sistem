from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import or_, text
from models import db, Usuario, SesionUsuario
from extensions import mail
from flask_mail import Message
import random, string
from forms import LoginForm

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

DESTINOS_POR_ROL = {
    'administrador': 'dashboard.dashboard',
    'vendedor': 'ventas.ventas',
    'almacenista': 'dashboard.dashboard',
    'producción': 'produccion.produccion',
    'consulta': 'dashboard.dashboard',
    'cliente': 'catalogo_cliente.catalogo',
}

def _obtener_destino_por_rol(usuario):
    if usuario and usuario.persona and usuario.persona.cliente:
        return 'catalogo_cliente.catalogo'

    rol = (usuario.rol.Nombre if usuario and usuario.rol else '').lower().strip()
    return DESTINOS_POR_ROL.get(rol)

def _generar_codigo() -> str:
    return ''.join(random.choices(string.digits, k=6))

def _enmascarar_correo(correo: str) -> str:
    if '@' not in correo:
        return correo
    usuario, dominio = correo.split('@', 1)
    if len(usuario) <= 2:
        return correo
    return usuario[:2] + '*' * (len(usuario) - 2) + '@' + dominio

def _enviar_codigo_recuperacion(correo: str, codigo: str) -> bool:
    try:
        msg = Message(
            subject='Código de recuperación — Hobbys Car Audio',
            recipients=[correo],
            body=(
                f"Tu código de recuperación es: {codigo}\n\n"
                f"Este código expira en 10 minutos. "
                f"Si no solicitaste restablecer tu contraseña, ignora este mensaje.\n\n"
                f"— Hobbys Car Audio"
            )
        )
        mail.send(msg)
        return True
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Error al enviar código de recuperación a {correo}: {e}')
        return False

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        destino = _obtener_destino_por_rol(current_user)
        return redirect(url_for(destino or 'auth.login'))

    form = LoginForm(request.form)

    if request.method == 'POST' and form.validate():
        identificador = form.identificador.data.strip()
        password = form.password.data

        usuario = db.session.query(Usuario).filter_by(
            Identificador=identificador
        ).first()

        if not usuario or not check_password_hash(usuario.PasswordHash, password):
            flash('Nombre de usuario o contraseña incorrectos', 'danger')
            return render_template('index.html', form=form)

        if not usuario.Activo:
            flash('Tu cuenta está desactivada, contacta al administrador', 'warning')
            return render_template('index.html', form=form)

        destino = _obtener_destino_por_rol(usuario)

        if not destino:
            flash('Rol no reconocido, contacta al administrador', 'danger')
            return render_template('index.html', form=form)

        usuario.FechaUltimoAcceso = datetime.now()

        nueva_sesion = SesionUsuario(
            IdUsuario = usuario.IdUsuario,
            FechaInicio = datetime.now(),
            FechaUltimaActividad = datetime.now(),
            Activa = True
        )
        db.session.add(nueva_sesion)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('Error interno al iniciar sesión, intenta de nuevo', 'danger')
            return render_template('index.html', form=form)

        login_user(usuario, remember=False)
        return redirect(url_for(destino))

    return render_template('index.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    sesion_activa = db.session.query(SesionUsuario).filter_by(
        IdUsuario=current_user.IdUsuario,
        Activa=True
    ).order_by(SesionUsuario.FechaInicio.desc()).first()

    if sesion_activa:
        sesion_activa.Activa = False
        sesion_activa.FechaCierre  = datetime.now()
        sesion_activa.MotivoCierre = 'logout'
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/recuperar', methods=['GET', 'POST'])
def recuperar_paso1():

    if request.method == 'POST':
        identificador = request.form.get('identificador', '').strip()
 
        if not identificador:
            flash('Ingresa tu usuario o correo electrónico.', 'danger')
            return render_template('auth/recuperar.html')
 
        usuario = db.session.execute(
            text("""
                SELECT u.IdUsuario, u.Identificador, u.Activo,
                       p.CorreoElectronico, p.Nombre,
                       r.Nombre AS NombreRol,
                       cl.IdCliente
                FROM Usuario u
                JOIN Persona p ON u.IdPersona = p.IdPersona
                LEFT JOIN Rol r ON u.IdRol = r.IdRol
                LEFT JOIN Cliente cl ON cl.IdPersona = p.IdPersona
                WHERE u.Identificador = :id
                   OR p.CorreoElectronico = :id
                LIMIT 1
            """),
            {'id': identificador}
        ).fetchone()
 
        if not usuario:
            flash('No se encontró ninguna cuenta con ese usuario o correo.', 'danger')
            return render_template('auth/recuperar.html')
 
        if not usuario.Activo:
            flash('Tu cuenta está desactivada. Contacta al administrador.', 'warning')
            return render_template('auth/recuperar.html')
 
        es_cliente = usuario.IdCliente is not None
        rol = (usuario.NombreRol or '').lower().strip()
 
        codigo = _generar_codigo()
        session['recuperacion'] = {
            'codigo': codigo,
            'expira': (datetime.now() + timedelta(minutes=10)).isoformat(),
            'correo': usuario.CorreoElectronico,
            'nombre': usuario.Nombre,
            'id_usuario': usuario.IdUsuario,
            'es_cliente': es_cliente,
            'rol': rol,
        }
        session.modified = True
 
        exito = _enviar_codigo_recuperacion(usuario.CorreoElectronico, codigo)
        if not exito:
            flash('No se pudo enviar el correo. Intenta de nuevo.', 'danger')
            return render_template('auth/recuperar.html')
 
        correo_enmascarado = _enmascarar_correo(usuario.CorreoElectronico)
        return render_template(
            'auth/recuperar.html',
            mostrar_modal=True,
            correo_enmascarado=correo_enmascarado,
        )
 
    return render_template('auth/recuperar.html')

@auth_bp.route('/recuperar/reenviar', methods=['POST'])
@login_required
def recuperar_reenviar():
    from flask import jsonify
    datos = session.get('recuperacion')
    if not datos:
        return jsonify({'ok': False, 'mensaje': 'Sesión expirada. Vuelve a empezar.'})
 
    nuevo_codigo = _generar_codigo()
    datos['codigo'] = nuevo_codigo
    datos['expira'] = (datetime.now() + timedelta(minutes=10)).isoformat()
    session['recuperacion'] = datos
    session.modified = True
 
    exito = _enviar_codigo_recuperacion(datos['correo'], nuevo_codigo)
    if exito:
        return jsonify({'ok': True, 'mensaje': 'Código reenviado correctamente.'})
    return jsonify({'ok': False, 'mensaje': 'No se pudo reenviar el correo.'})

@auth_bp.route('/recuperar/verificar', methods=['POST'])
@login_required
def recuperar_verificar():
    """Valida el código ingresado en el modal y redirige al formulario de nueva contraseña."""
    codigo_ingresado = request.form.get('codigo_verificacion', '').strip()
    datos = session.get('recuperacion')
 
    if not datos:
        flash('La sesión expiró. Vuelve a intentarlo.', 'danger')
        return redirect(url_for('auth.recuperar_paso1'))
 
    if datetime.now() > datetime.fromisoformat(datos['expira']):
        session.pop('recuperacion', None)
        flash('El código expiró. Vuelve a intentarlo.', 'danger')
        return redirect(url_for('auth.recuperar_paso1'))
 
    if codigo_ingresado != datos['codigo']:
        correo_enmascarado = _enmascarar_correo(datos['correo'])
        return render_template(
            'auth/recuperar.html',
            mostrar_modal=True,
            error_codigo=True,
            correo_enmascarado=correo_enmascarado,
        )

    datos['verificado'] = True
    session['recuperacion'] = datos
    session.modified = True
 
    return redirect(url_for('auth.recuperar_nueva_pass'))

@auth_bp.route('/recuperar/nueva', methods=['GET', 'POST'])
@login_required
def recuperar_nueva_pass():
    datos = session.get('recuperacion')
 
    if not datos or not datos.get('verificado'):
        flash('Debes verificar tu identidad primero.', 'danger')
        return redirect(url_for('auth.recuperar_paso1'))
 
    correo_enmascarado = _enmascarar_correo(datos['correo'])
    es_cliente = datos.get('es_cliente', False)
 
    if request.method == 'POST':
        nueva_pass = request.form.get('password', '')
        confirmar  = request.form.get('password_confirm', '')
 
        if len(nueva_pass) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'danger')
            return render_template(
                'auth/recuperar_nueva.html',
                correo_enmascarado=correo_enmascarado,
                es_cliente=es_cliente,
            )
 
        if nueva_pass != confirmar:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template(
                'auth/recuperar_nueva.html',
                correo_enmascarado=correo_enmascarado,
                es_cliente=es_cliente,
            )
 
        nuevo_hash = generate_password_hash(nueva_pass)
        db.session.execute(
            text('UPDATE Usuario SET PasswordHash = :hash WHERE IdUsuario = :id'),
            {'hash': nuevo_hash, 'id': datos['id_usuario']}
        )
        db.session.commit()
 
        session.pop('recuperacion', None)
        flash('Contraseña actualizada correctamente. Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
 
    return render_template(
        'auth/recuperar_nueva.html',
        correo_enmascarado=correo_enmascarado,
        es_cliente=es_cliente,
    )