from flask import Flask, render_template
from config import DevelopmentConfig
from models import db
from proveedores import proveedores_bp
from materia_prima import materia_prima_bp
from compras import compras_bp
from flask import session
from sqlalchemy import text

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

db.init_app(app)

app.register_blueprint(proveedores_bp)
app.register_blueprint(materia_prima_bp)
app.register_blueprint(compras_bp)

@app.route("/")
def index():
    return render_template("index.html", active='dashboard')

@app.context_processor
def inject_notifications():
    es_autorizado = True
    #es_autorizado = session.get('rol') in ['Administrador', 'Almacenista']
    alertas = []
    
    if es_autorizado:
        query = text("""
            SELECT IdAlertaSistema, Mensaje, ReferenciaId 
            FROM alertasistema 
            WHERE Leida = 0 AND TipoAlerta = 'STOCK_BAJO'
            ORDER BY FechaGeneracion DESC
        """)
        alertas = db.session.execute(query).fetchall()
        
    return dict(alertas_criticas=alertas, total_alertas=len(alertas), puede_ver_alertas=es_autorizado)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)