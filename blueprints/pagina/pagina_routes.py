from flask import Blueprint, render_template, request, flash, redirect, url_for
from models import db, ProductoTerminado
from base64 import b64encode

publico_bp = Blueprint('publico', __name__)

def _mime_imagen(contenido):
    if contenido.startswith(b"\x89PNG"):
        return "image/png"
    if contenido.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return "application/octet-stream"

def _imagen_a_data_url(contenido):
    if not contenido:
        return None
    mime = _mime_imagen(contenido)
    return f"data:{mime};base64,{b64encode(contenido).decode('ascii')}"

def obtener_productos_publico():
    productos_db = ProductoTerminado.query.filter_by(Activo=True).limit(4).all()

    productos = []
    for p in productos_db:
        productos.append({
            "id": p.IdProductoTerminado,
            "nombre": p.Nombre,
            "descripcion": p.Descripcion or "Sin descripción disponible",
            "precio": float(p.PrecioVenta or 0),
            "stock": int(p.StockActual or 0),
            "imagen": _imagen_a_data_url(p.Foto)
        })

    return productos

@publico_bp.route('/')
def index():
    productos = obtener_productos_publico()
    return render_template('index.html', productos=productos)


@publico_bp.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        email  = request.form.get('email', '').strip()
        mensaje = request.form.get('mensaje', '').strip()

        if not nombre or not email or not mensaje:
            flash('Por favor completa los campos obligatorios.', 'danger')
            return redirect(url_for('publico.contacto'))

        flash('¡Mensaje enviado correctamente! Te contactaremos pronto.', 'success')
        return redirect(url_for('publico.contacto'))

    return render_template('index.html')