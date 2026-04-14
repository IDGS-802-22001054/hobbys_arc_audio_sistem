from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime
from models import db, Usuario, SesionUsuario
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

        session['id_sesion_usuario'] = nueva_sesion.IdSesionUsuario
        login_user(usuario, remember=False)
        return redirect(url_for(destino))

    return render_template('index.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    id_sesion = session.get('id_sesion_usuario')
    sesion_activa = None

    if id_sesion:
        sesion_activa = db.session.get(SesionUsuario, id_sesion)
        if sesion_activa and (
            sesion_activa.IdUsuario != current_user.IdUsuario or not sesion_activa.Activa
        ):
            sesion_activa = None

    if sesion_activa is None:
        sesion_activa = db.session.query(SesionUsuario).filter_by(
            IdUsuario=current_user.IdUsuario,
            Activa=True
        ).order_by(SesionUsuario.FechaInicio.desc()).first()

    if sesion_activa:
        sesion_activa.Activa       = False
        sesion_activa.FechaCierre  = datetime.now()
        sesion_activa.MotivoCierre = 'logout'
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    session.pop('id_sesion_usuario', None)
    logout_user()
    return redirect(url_for('auth.login'))
