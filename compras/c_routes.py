from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import db, CompraMateriaPrima, CompraMateriaPrimaDetalle, MateriaPrima, Proveedor
from sqlalchemy import text
from . import compras_bp

@compras_bp.route('/compras')
def listar():
    #if session.get('rol') not in ['Administrador', 'Almacenista']:
        #return redirect(url_for('login'))

    compras = CompraMateriaPrima.query.order_by(CompraMateriaPrima.FechaCompra.desc()).all()
    
    return render_template('compras/index.html', compras=compras)