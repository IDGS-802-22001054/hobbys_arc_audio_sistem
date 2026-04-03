from flask_sqlalchemy import SQLAlchemy
import datetime

db = SQLAlchemy()

class Rol(db.Model):
    __tablename__ = 'Rol'
    IdRol = db.Column(db.Integer, primary_key=True)
    Nombre = db.Column(db.String(50), nullable=False, unique=True)
    Activo = db.Column(db.Boolean, default=True)

class Persona(db.Model):
    __tablename__ = 'Persona'
    IdPersona = db.Column(db.Integer, primary_key=True)
    Nombre = db.Column(db.String(100), nullable=False)
    Apellidos = db.Column(db.String(150), nullable=False)
    Telefono = db.Column(db.String(20))
    CorreoElectronico = db.Column(db.String(150), unique=True)
    Foto = db.Column(db.String(255))
    FechaRegistro = db.Column(db.DateTime, default=datetime.datetime.now)

    cuenta_usuario = db.relationship('Usuario', backref='datos_personales', uselist=False)

class Usuario(db.Model):
    __tablename__ = 'Usuario'
    IdUsuario = db.Column(db.Integer, primary_key=True)
    IdPersona = db.Column(db.Integer, db.ForeignKey('Persona.IdPersona'), nullable=False, unique=True)
    Identificador = db.Column(db.String(50), nullable=False, unique=True) 
    PasswordHash = db.Column(db.String(255), nullable=False)
    IdRol = db.Column(db.Integer, db.ForeignKey('Rol.IdRol'), nullable=False)
    Activo = db.Column(db.Boolean, default=True)
    FechaRegistro = db.Column(db.DateTime, default=datetime.datetime.now)
    FechaUltimoAcceso = db.Column(db.DateTime)

    rol = db.relationship('Rol', backref='usuarios')

class Proveedor(db.Model):
    __tablename__ = 'Proveedor'
    IdProveedor = db.Column(db.Integer, primary_key=True, autoincrement=True)
    NombreEmpresa = db.Column(db.String(150), nullable=False)
    RFC = db.Column(db.String(15), nullable=False, unique=True)
    Telefono = db.Column(db.String(30))
    CorreoElectronico = db.Column(db.String(120))
    Direccion = db.Column(db.String(255))
    Activo = db.Column(db.Boolean, default=True, nullable=False)
    FechaRegistro = db.Column(db.DateTime, default=datetime.datetime.now)

class UnidadMedida(db.Model):
    __tablename__ = 'UnidadMedida'
    IdUnidadMedida = db.Column(db.Integer, primary_key=True)
    Nombre = db.Column(db.String(50), nullable=False, unique=True)
    Abreviatura = db.Column(db.String(20), nullable=False, unique=True)
    Activo = db.Column(db.Boolean, default=True)

class MateriaPrima(db.Model):
    __tablename__ = 'MateriaPrima'
    IdMateriaPrima = db.Column(db.Integer, primary_key=True)
    Nombre = db.Column(db.String(150), nullable=False)
    Descripcion = db.Column(db.String(255))
    Marca = db.Column(db.String(100))
    IdProveedor = db.Column(db.Integer, db.ForeignKey('Proveedor.IdProveedor'))
    IdUnidadMedida = db.Column(db.Integer, db.ForeignKey('UnidadMedida.IdUnidadMedida'), nullable=False)
    PrecioUnitario = db.Column(db.Numeric(18, 2), default=0)
    StockActual = db.Column(db.Numeric(18, 2), default=0)
    StockMinimo = db.Column(db.Numeric(18, 2), default=0)
    Activo = db.Column(db.Boolean, default=True)
    FechaRegistro = db.Column(db.DateTime, default=datetime.datetime.now)

    unidad = db.relationship('UnidadMedida', backref='materiales')
    proveedor = db.relationship('Proveedor', backref='materiales')

class MovimientoMateriaPrima(db.Model):
    __tablename__ = 'MovimientoMateriaPrima'
    IdMovimientoMateriaPrima = db.Column(db.Integer, primary_key=True)
    IdMateriaPrima = db.Column(db.Integer, db.ForeignKey('MateriaPrima.IdMateriaPrima'), nullable=False)
    TipoMovimiento = db.Column(db.String(20), nullable=False) 
    Cantidad = db.Column(db.Numeric(18, 2), nullable=False)
    CostoUnitario = db.Column(db.Numeric(18, 2), default=0)
    FechaMovimiento = db.Column(db.DateTime, default=datetime.datetime.now)
    Motivo = db.Column(db.String(255))
    IdUsuario = db.Column(db.Integer, db.ForeignKey('Usuario.IdUsuario'), nullable=False)

    usuario = db.relationship('Usuario', backref='movimientos_realizados')
    material = db.relationship('MateriaPrima', backref='movimientos')

class CompraMateriaPrima(db.Model):
    __tablename__ = 'compramateriaprima'
    IdCompraMateriaPrima = db.Column(db.Integer, primary_key=True, autoincrement=True)
    FechaCompra = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now)
    IdProveedor = db.Column(db.Integer, db.ForeignKey('Proveedor.IdProveedor'))
    TotalCompra = db.Column(db.Numeric(18, 2), nullable=False, default=0.00)
    Observaciones = db.Column(db.String(255))
    IdUsuarioRegistro = db.Column(db.Integer, db.ForeignKey('Usuario.IdUsuario'), nullable=False)

    proveedor = db.relationship('Proveedor', backref='compras')
    usuario = db.relationship('Usuario', backref='compras_registradas')
    detalles = db.relationship('CompraMateriaPrimaDetalle', backref='compra', cascade="all, delete-orphan")

class CompraMateriaPrimaDetalle(db.Model):
    __tablename__ = 'compramateriaprimadetalle'
    IdCompraMateriaPrimaDetalle = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdCompraMateriaPrima = db.Column(db.Integer, db.ForeignKey('compramateriaprima.IdCompraMateriaPrima'), nullable=False)
    IdMateriaPrima = db.Column(db.Integer, db.ForeignKey('MateriaPrima.IdMateriaPrima'), nullable=False)
    Cantidad = db.Column(db.Numeric(18, 2), nullable=False)
    CostoUnitario = db.Column(db.Numeric(18, 2), nullable=False)
    Subtotal = db.Column(db.Numeric(18, 2), nullable=False)

    materia_prima = db.relationship('MateriaPrima', backref='detalles_compra')