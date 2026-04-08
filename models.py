from flask_sqlalchemy import SQLAlchemy
from decimal import Decimal
from sqlalchemy import UniqueConstraint, text as sql_text
from sqlalchemy.dialects.mysql import LONGTEXT, MEDIUMBLOB
from flask_login import UserMixin

db = SQLAlchemy()


def _decimal_modelo(valor):
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


def _costo_unitario_materia(materia_prima):
    if materia_prima is None:
        return Decimal("0.00")

    precio_unitario = _decimal_modelo(materia_prima.PrecioUnitario)
    abreviatura = ""
    if materia_prima.unidad_medida:
        abreviatura = (materia_prima.unidad_medida.Abreviatura or "").strip().lower()

    if abreviatura in {"g", "ml"}:
        return (precio_unitario / Decimal("1000")).quantize(Decimal("0.0001"))

    return precio_unitario


class BaseModel(db.Model):
    __abstract__ = True
    __table_args__ = {"mysql_engine": "InnoDB"}


class Rol(BaseModel):
    __tablename__ = "Rol"

    IdRol = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Nombre = db.Column(db.String(50), nullable=False, unique=True)
    Descripcion = db.Column(db.String(200))
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    usuarios = db.relationship("Usuario", back_populates="rol", lazy=True)


class Persona(BaseModel):
    __tablename__ = "Persona"

    IdPersona = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Nombre = db.Column(db.String(100), nullable=False)
    Apellidos = db.Column(db.String(150), nullable=False)
    Telefono = db.Column(db.String(30))
    CorreoElectronico = db.Column(db.String(120), nullable=False, unique=True)
    Calle = db.Column(db.String(120))
    Colonia = db.Column(db.String(120))
    NumeroExterior = db.Column(db.String(20))
    NumeroInterior = db.Column(db.String(20))
    CodigoPostal = db.Column(db.String(10))
    Foto = db.Column(LONGTEXT)
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )

    cliente = db.relationship("Cliente", back_populates="persona", uselist=False)
    empleado = db.relationship("Empleado", back_populates="persona", uselist=False)
    usuario = db.relationship("Usuario", back_populates="persona", uselist=False)

    @property
    def direccion_formateada(self):
        partes = []
        calle = (self.Calle or "").strip()
        numero_exterior = (self.NumeroExterior or "").strip()
        numero_interior = (self.NumeroInterior or "").strip()
        colonia = (self.Colonia or "").strip()
        codigo_postal = (self.CodigoPostal or "").strip()

        primera_linea = " ".join(
            parte for parte in [calle, f"No. {numero_exterior}" if numero_exterior else ""] if parte
        ).strip()
        if numero_interior:
            primera_linea = " ".join(
                parte for parte in [primera_linea, f"Int. {numero_interior}"] if parte
            ).strip()

        if primera_linea:
            partes.append(primera_linea)
        if colonia:
            partes.append(f"Col. {colonia}")
        if codigo_postal:
            partes.append(f"CP {codigo_postal}")

        return ", ".join(partes)


class Cliente(BaseModel):
    __tablename__ = "Cliente"

    IdCliente = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdPersona = db.Column(db.Integer, db.ForeignKey("Persona.IdPersona"), nullable=False, unique=True)
    PermiteCompraOnline = db.Column(
        db.Boolean, nullable=False, server_default=sql_text("1")
    )
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )

    persona = db.relationship("Persona", back_populates="cliente", uselist=False)
    ventas = db.relationship("Venta", back_populates="cliente", lazy=True)
    tarjetas = db.relationship("TarjetaCliente", back_populates="cliente", lazy=True)


class TarjetaCliente(BaseModel):
    __tablename__ = "TarjetaCliente"

    IdTarjetaCliente = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdCliente = db.Column(db.Integer, db.ForeignKey("Cliente.IdCliente"), nullable=False)
    Alias = db.Column(db.String(100))
    Titular = db.Column(db.String(150), nullable=False)
    Marca = db.Column(db.String(50), nullable=False)
    Ultimos4 = db.Column(db.String(4), nullable=False)
    MesExpiracion = db.Column(db.Integer, nullable=False)
    AnioExpiracion = db.Column(db.Integer, nullable=False)
    TokenPasarela = db.Column(db.String(255), nullable=False, unique=True)
    EsPredeterminada = db.Column(
        db.Boolean, nullable=False, server_default=sql_text("0")
    )
    Activa = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )

    cliente = db.relationship("Cliente", back_populates="tarjetas", uselist=False)


class Empleado(BaseModel):
    __tablename__ = "Empleado"

    IdEmpleado = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdPersona = db.Column(db.Integer, db.ForeignKey("Persona.IdPersona"), nullable=False, unique=True)
    Puesto = db.Column(db.String(100))
    FechaIngreso = db.Column(db.Date)
    Salario = db.Column(db.Numeric(18, 2))
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )

    persona = db.relationship("Persona", back_populates="empleado", uselist=False)


class Usuario(UserMixin, BaseModel):
    __tablename__ = "Usuario"

    IdUsuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdPersona = db.Column(db.Integer, db.ForeignKey("Persona.IdPersona"), nullable=False, unique=True)
    Identificador = db.Column(db.String(50), nullable=False, unique=True)
    PasswordHash = db.Column(db.String(255), nullable=False)
    IdRol = db.Column(db.Integer, db.ForeignKey("Rol.IdRol"), nullable=False)
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    FechaUltimoAcceso = db.Column(db.DateTime)

    def get_id(self):
        return str(self.IdUsuario)

    persona = db.relationship("Persona", back_populates="usuario", uselist=False)
    rol = db.relationship("Rol", back_populates="usuarios", uselist=False)
    configuraciones_actualizadas = db.relationship(
        "ConfiguracionSistema",
        back_populates="usuario_actualiza",
        foreign_keys=lambda: [ConfiguracionSistema.IdUsuarioActualiza], lazy=True
    )
    movimientos_materia_prima = db.relationship(
        "MovimientoMateriaPrima",
        back_populates="usuario",
        foreign_keys=lambda: [MovimientoMateriaPrima.IdUsuario], lazy=True
    )
    compras_materia_prima_registradas = db.relationship(
        "CompraMateriaPrima",
        back_populates="usuario_registro",
        foreign_keys=lambda: [CompraMateriaPrima.IdUsuarioRegistro], lazy=True
    )
    recetas_registradas = db.relationship(
        "Receta",
        back_populates="usuario_registro",
        foreign_keys=lambda: [Receta.IdUsuarioRegistro], lazy=True
    )
    recetas_aprobadas = db.relationship(
        "Receta",
        back_populates="usuario_aprueba",
        foreign_keys=lambda: [Receta.IdUsuarioAprueba], lazy=True
    )
    solicitudes_realizadas = db.relationship(
        "SolicitudProduccion",
        back_populates="usuario_solicita",
        foreign_keys=lambda: [SolicitudProduccion.IdUsuarioSolicita], lazy=True
    )
    solicitudes_aprobadas = db.relationship(
        "SolicitudProduccion",
        back_populates="usuario_aprueba",
        foreign_keys=lambda: [SolicitudProduccion.IdUsuarioAprueba], lazy=True
    )
    producciones_registradas = db.relationship(
        "Produccion",
        back_populates="usuario_registro",
        foreign_keys=lambda: [Produccion.IdUsuarioRegistro], lazy=True
    )
    movimientos_producto_terminado = db.relationship(
        "MovimientoProductoTerminado",
        back_populates="usuario",
        foreign_keys=lambda: [MovimientoProductoTerminado.IdUsuario], lazy=True
    )
    ventas_registradas = db.relationship(
        "Venta",
        back_populates="usuario_registro",
        foreign_keys=lambda: [Venta.IdUsuarioRegistro], lazy=True
    )
    cortes_venta_diario_registrados = db.relationship(
        "CorteVentaDiario",
        back_populates="usuario_registro",
        foreign_keys=lambda: [CorteVentaDiario.IdUsuarioRegistro], lazy=True
    )
    alertas_destino = db.relationship(
        "AlertaSistema",
        back_populates="usuario_destino",
        foreign_keys=lambda: [AlertaSistema.IdUsuarioDestino], lazy=True
    )
    sesiones = db.relationship("SesionUsuario", back_populates="usuario", lazy=True)

    def get_id(self):
        return str(self.IdUsuario)


class ConfiguracionSistema(BaseModel):
    __tablename__ = "ConfiguracionSistema"

    IdConfiguracion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    CantidadMinimaMateriaPrima = db.Column(
        db.Integer, nullable=False, server_default=sql_text("0")
    )
    CantidadMinimaProductoTerminado = db.Column(
        db.Integer, nullable=False, server_default=sql_text("0")
    )
    HorasInactividadCierreSesion = db.Column(
        db.Integer, nullable=False, server_default=sql_text("2")
    )
    AlertarPocasPiezasTerminadas = db.Column(
        db.Boolean, nullable=False, server_default=sql_text("1")
    )
    AlertarMateriaPrimaMinima = db.Column(
        db.Boolean, nullable=False, server_default=sql_text("1")
    )
    FechaActualizacion = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    IdUsuarioActualiza = db.Column(db.Integer, db.ForeignKey("Usuario.IdUsuario"))

    usuario_actualiza = db.relationship(
        "Usuario",
        back_populates="configuraciones_actualizadas",
        foreign_keys=[IdUsuarioActualiza],
        uselist=False,
    )


class Proveedor(BaseModel):
    __tablename__ = "Proveedor"

    IdProveedor = db.Column(db.Integer, primary_key=True, autoincrement=True)
    NombreEmpresa = db.Column(db.String(150), nullable=False)
    Telefono = db.Column(db.String(30))
    CorreoElectronico = db.Column(db.String(120))
    Direccion = db.Column(db.String(255))
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    RFC = db.Column(db.String(13), nullable=False, unique=True)

    materias_primas = db.relationship("MateriaPrima", back_populates="proveedor", lazy=True)
    compras_materia_prima = db.relationship(
        "CompraMateriaPrima", back_populates="proveedor", lazy=True
    )


class UnidadMedida(BaseModel):
    __tablename__ = "UnidadMedida"

    IdUnidadMedida = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Nombre = db.Column(db.String(50), nullable=False, unique=True)
    Abreviatura = db.Column(db.String(20), nullable=False, unique=True)
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))

    materias_primas = db.relationship("MateriaPrima", back_populates="unidad_medida", lazy=True)


class MateriaPrima(BaseModel):
    __tablename__ = "MateriaPrima"

    IdMateriaPrima = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Nombre = db.Column(db.String(150), nullable=False)
    Descripcion = db.Column(db.String(255))
    Marca = db.Column(db.String(100))
    IdProveedor = db.Column(db.Integer, db.ForeignKey("Proveedor.IdProveedor"))
    IdUnidadMedida = db.Column(
        db.Integer, db.ForeignKey("UnidadMedida.IdUnidadMedida"), nullable=False
    )
    PrecioUnitario = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    StockActual = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    StockMinimo = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )

    proveedor = db.relationship("Proveedor", back_populates="materias_primas", uselist=False)
    unidad_medida = db.relationship("UnidadMedida", back_populates="materias_primas", uselist=False)
    movimientos = db.relationship(
        "MovimientoMateriaPrima", back_populates="materia_prima", lazy=True
    )
    detalles_compra = db.relationship(
        "CompraMateriaPrimaDetalle", back_populates="materia_prima", lazy=True
    )
    recetas_detalle = db.relationship("RecetaDetalle", back_populates="materia_prima", lazy=True)


class MovimientoMateriaPrima(BaseModel):
    __tablename__ = "MovimientoMateriaPrima"

    IdMovimientoMateriaPrima = db.Column(
        db.Integer, primary_key=True, autoincrement=True
    )
    IdMateriaPrima = db.Column(
        db.Integer, db.ForeignKey("MateriaPrima.IdMateriaPrima"), nullable=False
    )
    TipoMovimiento = db.Column(db.String(20), nullable=False)
    Cantidad = db.Column(db.Numeric(18, 2), nullable=False)
    CostoUnitario = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    FechaMovimiento = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    Motivo = db.Column(db.String(255))
    IdUsuario = db.Column(db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False)

    materia_prima = db.relationship("MateriaPrima", back_populates="movimientos", uselist=False)
    usuario = db.relationship(
        "Usuario",
        back_populates="movimientos_materia_prima",
        foreign_keys=[IdUsuario], uselist=False
    )


class CompraMateriaPrima(BaseModel):
    __tablename__ = "CompraMateriaPrima"

    IdCompraMateriaPrima = db.Column(db.Integer, primary_key=True, autoincrement=True)
    FechaCompra = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    IdProveedor = db.Column(db.Integer, db.ForeignKey("Proveedor.IdProveedor"))
    Observaciones = db.Column(db.String(255))
    IdUsuarioRegistro = db.Column(
        db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False
    )

    proveedor = db.relationship("Proveedor", back_populates="compras_materia_prima", uselist=False)
    usuario_registro = db.relationship(
        "Usuario",
        back_populates="compras_materia_prima_registradas",
        foreign_keys=[IdUsuarioRegistro], uselist=False,
    )
    detalles = db.relationship("CompraMateriaPrimaDetalle", back_populates="compra", lazy=True)

    @property
    def TotalCompra(self):
        total = sum(
            (_decimal_modelo(detalle.Cantidad) * _decimal_modelo(detalle.CostoUnitario))
            for detalle in self.detalles
        )
        return total.quantize(Decimal("0.01"))


class CompraMateriaPrimaDetalle(BaseModel):
    __tablename__ = "CompraMateriaPrimaDetalle"

    IdCompraMateriaPrimaDetalle = db.Column(
        db.Integer, primary_key=True, autoincrement=True
    )
    IdCompraMateriaPrima = db.Column(
        db.Integer,
        db.ForeignKey("CompraMateriaPrima.IdCompraMateriaPrima"),
        nullable=False,
    )
    IdMateriaPrima = db.Column(
        db.Integer, db.ForeignKey("MateriaPrima.IdMateriaPrima"), nullable=False
    )
    Cantidad = db.Column(db.Numeric(18, 2), nullable=False)
    CostoUnitario = db.Column(db.Numeric(18, 2), nullable=False)

    compra = db.relationship("CompraMateriaPrima", back_populates="detalles", uselist=False)
    materia_prima = db.relationship("MateriaPrima", back_populates="detalles_compra", uselist=False)

    @property
    def Subtotal(self):
        return (_decimal_modelo(self.Cantidad) * _decimal_modelo(self.CostoUnitario)).quantize(
            Decimal("0.01")
        )


class ProductoTerminado(BaseModel):
    __tablename__ = "ProductoTerminado"

    IdProductoTerminado = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Nombre = db.Column(db.String(150), nullable=False)
    Descripcion = db.Column(db.String(255))
    Foto = db.Column(MEDIUMBLOB)
    PrecioVenta = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    StockActual = db.Column(db.Integer, nullable=False, server_default=sql_text("0"))
    StockMinimo = db.Column(db.Integer, nullable=False, server_default=sql_text("0"))
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )

    receta = db.relationship("Receta", back_populates="producto_terminado", uselist=False)
    solicitudes_produccion = db.relationship(
        "SolicitudProduccion", back_populates="producto_terminado", lazy=True
    )
    producciones = db.relationship("Produccion", back_populates="producto_terminado", lazy=True)
    movimientos = db.relationship(
        "MovimientoProductoTerminado", back_populates="producto_terminado", lazy=True
    )
    ventas_detalle = db.relationship("VentaDetalle", back_populates="producto_terminado", lazy=True)

    @property
    def CostoProduccion(self):
        receta = self.receta
        if receta is None:
            return Decimal("0.00")

        total = Decimal("0.00")
        for detalle in receta.detalles:
            precio_unitario = _costo_unitario_materia(detalle.materia_prima)
            consumo_total = _decimal_modelo(detalle.CantidadRequerida) + _decimal_modelo(detalle.Merma)
            total += consumo_total * precio_unitario

        return total.quantize(Decimal("0.01"))
    
    @property
    def UtilidadPorPieza(self):
        return (_decimal_modelo(self.PrecioVenta) - self.CostoProduccion).quantize(Decimal("0.01"))

    @property
    def TotalDefectuosos(self):
        return sum((p.CantidadDefectuosa for p in self.producciones), 0)


class Receta(BaseModel):
    __tablename__ = "Receta"

    IdProductoTerminado = db.Column(
        db.Integer,
        db.ForeignKey("ProductoTerminado.IdProductoTerminado"),
        primary_key=True,
    )
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    IdUsuarioRegistro = db.Column(
        db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False
    )
    RequiereAprobacion = db.Column(
        db.Boolean, nullable=False, server_default=sql_text("0")
    )
    Aprobada = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    IdUsuarioAprueba = db.Column(db.Integer, db.ForeignKey("Usuario.IdUsuario"))
    FechaAprobacion = db.Column(db.DateTime)
    Activa = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))

    producto_terminado = db.relationship(
        "ProductoTerminado", back_populates="receta", uselist=False
    )
    usuario_registro = db.relationship(
        "Usuario",
        back_populates="recetas_registradas",
        foreign_keys=[IdUsuarioRegistro], uselist=False,
    )
    usuario_aprueba = db.relationship(
        "Usuario",
        back_populates="recetas_aprobadas",
        foreign_keys=[IdUsuarioAprueba], uselist=False,
    )
    detalles = db.relationship("RecetaDetalle", back_populates="receta", lazy=True)


class RecetaDetalle(BaseModel):
    __tablename__ = "RecetaDetalle"
    __table_args__ = (
        UniqueConstraint(
            "IdProductoTerminado",
            "IdMateriaPrima",
            name="uq_receta_detalle_producto_materia",
        ),
        {"mysql_engine": "InnoDB"},
    )

    IdRecetaDetalle = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdProductoTerminado = db.Column(
        db.Integer, db.ForeignKey("Receta.IdProductoTerminado"), nullable=False
    )
    IdMateriaPrima = db.Column(
        db.Integer, db.ForeignKey("MateriaPrima.IdMateriaPrima"), nullable=False
    )
    CantidadRequerida = db.Column(db.Numeric(18, 2), nullable=False)
    Merma = db.Column(db.Numeric(18, 2), nullable=False, server_default=sql_text("0"))

    receta = db.relationship("Receta", back_populates="detalles", uselist=False)
    materia_prima = db.relationship("MateriaPrima", back_populates="recetas_detalle", uselist=False)


class SolicitudProduccion(BaseModel):
    __tablename__ = "SolicitudProduccion"

    IdSolicitudProduccion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdProductoTerminado = db.Column(
        db.Integer, db.ForeignKey("ProductoTerminado.IdProductoTerminado"), nullable=False
    )
    CantidadSolicitada = db.Column(db.Integer, nullable=False)
    Motivo = db.Column(db.String(255))
    Estado = db.Column(db.String(20), nullable=False, server_default=sql_text("'PENDIENTE'"))
    FechaSolicitud = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    IdUsuarioSolicita = db.Column(
        db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False
    )
    IdUsuarioAprueba = db.Column(db.Integer, db.ForeignKey("Usuario.IdUsuario"))
    FechaAprobacion = db.Column(db.DateTime)
    ObservacionesAprobacion = db.Column(db.String(255))

    producto_terminado = db.relationship(
        "ProductoTerminado", back_populates="solicitudes_produccion", uselist=False
    )
    usuario_solicita = db.relationship(
        "Usuario",
        back_populates="solicitudes_realizadas",
        foreign_keys=[IdUsuarioSolicita], uselist=False,
    )
    usuario_aprueba = db.relationship(
        "Usuario",
        back_populates="solicitudes_aprobadas",
        foreign_keys=[IdUsuarioAprueba], uselist=False,
    )
    producciones = db.relationship("Produccion", back_populates="solicitud_produccion", lazy=True)


class Produccion(BaseModel):
    __tablename__ = "Produccion"

    IdProduccion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdSolicitudProduccion = db.Column(
        db.Integer, db.ForeignKey("SolicitudProduccion.IdSolicitudProduccion")
    )
    IdProductoTerminado = db.Column(
        db.Integer, db.ForeignKey("ProductoTerminado.IdProductoTerminado"), nullable=False
    )
    CantidadPlaneada = db.Column(db.Integer, nullable=False)
    CantidadFabricada = db.Column(
        db.Integer, nullable=False, server_default=sql_text("0")
    )
    CantidadDefectuosa = db.Column(
        db.Integer, nullable=False, server_default=sql_text("0")
    )
    FechaInicio = db.Column(db.DateTime)
    FechaFin = db.Column(db.DateTime)
    Estado = db.Column(db.String(20), nullable=False, server_default=sql_text("'PENDIENTE'"))
    IdUsuarioRegistro = db.Column(
        db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False
    )

    solicitud_produccion = db.relationship(
        "SolicitudProduccion", back_populates="producciones", uselist=False
    )
    producto_terminado = db.relationship(
        "ProductoTerminado", back_populates="producciones", uselist=False
    )
    usuario_registro = db.relationship(
        "Usuario",
        back_populates="producciones_registradas",
        foreign_keys=[IdUsuarioRegistro], uselist=False,
    )
    defectos = db.relationship("ProduccionDefectuosa", back_populates="produccion", lazy=True)


class ProduccionDefectuosa(BaseModel):
    __tablename__ = "ProduccionDefectuosa"

    IdProduccionDefectuosa = db.Column(
        db.Integer, primary_key=True, autoincrement=True
    )
    IdProduccion = db.Column(
        db.Integer, db.ForeignKey("Produccion.IdProduccion"), nullable=False
    )
    CantidadDefectuosa = db.Column(db.Integer, nullable=False)
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    Descripcion = db.Column(db.String(255))

    produccion = db.relationship("Produccion", back_populates="defectos", uselist=False)


class MovimientoProductoTerminado(BaseModel):
    __tablename__ = "MovimientoProductoTerminado"

    IdMovimientoProductoTerminado = db.Column(
        db.Integer, primary_key=True, autoincrement=True
    )
    IdProductoTerminado = db.Column(
        db.Integer, db.ForeignKey("ProductoTerminado.IdProductoTerminado"), nullable=False
    )
    TipoMovimiento = db.Column(db.String(20), nullable=False)
    Cantidad = db.Column(db.Integer, nullable=False)
    FechaMovimiento = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    Motivo = db.Column(db.String(255))
    CostoUnitario = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    IdUsuario = db.Column(db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False)

    producto_terminado = db.relationship(
        "ProductoTerminado", back_populates="movimientos", uselist=False
    )
    usuario = db.relationship(
        "Usuario",
        back_populates="movimientos_producto_terminado",
        foreign_keys=[IdUsuario], uselist=False,
    )


class Venta(BaseModel):
    __tablename__ = "Venta"

    IdVenta = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdCliente = db.Column(db.Integer, db.ForeignKey("Cliente.IdCliente"))
    FechaVenta = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    MetodoPago = db.Column(
        db.String(20), nullable=False, server_default=sql_text("'EFECTIVO'")
    )
    IdUsuarioRegistro = db.Column(
        db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False
    )

    cliente = db.relationship("Cliente", back_populates="ventas", uselist=False)
    usuario_registro = db.relationship(
        "Usuario",
        back_populates="ventas_registradas",
        foreign_keys=[IdUsuarioRegistro], uselist=False,
    )
    detalles = db.relationship("VentaDetalle", back_populates="venta", lazy=True)

    @property
    def TotalVenta(self):
        total = sum((_decimal_modelo(detalle.Subtotal) for detalle in self.detalles), Decimal("0.00"))
        return total.quantize(Decimal("0.01"))


class VentaDetalle(BaseModel):
    __tablename__ = "VentaDetalle"

    IdVentaDetalle = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdVenta = db.Column(db.Integer, db.ForeignKey("Venta.IdVenta"), nullable=False)
    IdProductoTerminado = db.Column(
        db.Integer, db.ForeignKey("ProductoTerminado.IdProductoTerminado"), nullable=False
    )
    Cantidad = db.Column(db.Integer, nullable=False)
    PrecioUnitario = db.Column(db.Numeric(18, 2), nullable=False)

    venta = db.relationship("Venta", back_populates="detalles", uselist=False)
    producto_terminado = db.relationship(
        "ProductoTerminado", back_populates="ventas_detalle", uselist=False
    )

    @property
    def Subtotal(self):
        return (_decimal_modelo(self.Cantidad) * _decimal_modelo(self.PrecioUnitario)).quantize(
            Decimal("0.01")
        )


class CorteVentaDiario(BaseModel):
    __tablename__ = "CorteVentaDiario"

    IdCorteVentaDiario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    FechaCorte = db.Column(db.Date, nullable=False, unique=True)
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    IdUsuarioRegistro = db.Column(
        db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False
    )

    usuario_registro = db.relationship(
        "Usuario",
        back_populates="cortes_venta_diario_registrados",
        foreign_keys=[IdUsuarioRegistro], uselist=False,
    )

    @property
    def TotalVentas(self):
        total = Decimal("0.00")
        for venta in Venta.query.filter(db.func.date(Venta.FechaVenta) == self.FechaCorte).all():
            total += venta.TotalVenta
        return total.quantize(Decimal("0.01"))

    @property
    def TotalCosto(self):
        total = Decimal("0.00")
        ventas = Venta.query.filter(db.func.date(Venta.FechaVenta) == self.FechaCorte).all()
        for venta in ventas:
            for detalle in venta.detalles:
                costo_unitario = (
                    detalle.producto_terminado.CostoProduccion if detalle.producto_terminado else Decimal("0.00")
                )
                total += _decimal_modelo(detalle.Cantidad) * _decimal_modelo(costo_unitario)
        return total.quantize(Decimal("0.01"))

    @property
    def UtilidadDiaria(self):
        return (self.TotalVentas - self.TotalCosto).quantize(Decimal("0.01"))


class AlertaSistema(BaseModel):
    __tablename__ = "AlertaSistema"

    IdAlertaSistema = db.Column(db.Integer, primary_key=True, autoincrement=True)
    TipoAlerta = db.Column(db.String(50), nullable=False)
    ReferenciaId = db.Column(db.Integer)
    Mensaje = db.Column(db.String(255), nullable=False)
    Leida = db.Column(db.Boolean, nullable=False, server_default=sql_text("0"))
    FechaGeneracion = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    FechaLectura = db.Column(db.DateTime)
    IdUsuarioDestino = db.Column(db.Integer, db.ForeignKey("Usuario.IdUsuario"))

    usuario_destino = db.relationship(
        "Usuario",
        back_populates="alertas_destino",
        foreign_keys=[IdUsuarioDestino], uselist=False,
    )


class SesionUsuario(BaseModel):
    __tablename__ = "SesionUsuario"

    IdSesionUsuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdUsuario = db.Column(db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False)
    FechaInicio = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    FechaUltimaActividad = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    FechaCierre = db.Column(db.DateTime)
    Activa = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    MotivoCierre = db.Column(db.String(100))

    usuario = db.relationship("Usuario", back_populates="sesiones", uselist=False)
