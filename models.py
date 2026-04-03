from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, text as sql_text
from sqlalchemy.dialects.mysql import LONGBLOB, MEDIUMBLOB

db = SQLAlchemy()


class BaseModel(db.Model):
    __abstract__ = True
    __table_args__ = {"mysql_engine": "InnoDB"}


class Rol(BaseModel):
    __tablename__ = "Rol"

    IdRol = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Nombre = db.Column(db.String(50), nullable=False, unique=True)
    Descripcion = db.Column(db.String(200))
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))

    usuarios = db.relationship("Usuario", back_populates="rol")


class Persona(BaseModel):
    __tablename__ = "Persona"

    IdPersona = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Nombre = db.Column(db.String(100), nullable=False)
    Apellidos = db.Column(db.String(150), nullable=False)
    Telefono = db.Column(db.String(30))
    CorreoElectronico = db.Column(db.String(120), nullable=False, unique=True)
    Direccion = db.Column(db.String(255))
    Foto = db.Column(LONGBLOB)
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )

    cliente = db.relationship("Cliente", back_populates="persona", uselist=False)
    empleado = db.relationship("Empleado", back_populates="persona", uselist=False)
    usuario = db.relationship("Usuario", back_populates="persona", uselist=False)


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

    persona = db.relationship("Persona", back_populates="cliente")
    ventas = db.relationship("Venta", back_populates="cliente")


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

    persona = db.relationship("Persona", back_populates="empleado")


class Usuario(BaseModel):
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

    persona = db.relationship("Persona", back_populates="usuario")
    rol = db.relationship("Rol", back_populates="usuarios")
    configuraciones_actualizadas = db.relationship(
        "ConfiguracionSistema",
        back_populates="usuario_actualiza",
        foreign_keys=lambda: [ConfiguracionSistema.IdUsuarioActualiza],
    )
    movimientos_materia_prima = db.relationship(
        "MovimientoMateriaPrima",
        back_populates="usuario",
        foreign_keys=lambda: [MovimientoMateriaPrima.IdUsuario],
    )
    compras_materia_prima_registradas = db.relationship(
        "CompraMateriaPrima",
        back_populates="usuario_registro",
        foreign_keys=lambda: [CompraMateriaPrima.IdUsuarioRegistro],
    )
    recetas_registradas = db.relationship(
        "Receta",
        back_populates="usuario_registro",
        foreign_keys=lambda: [Receta.IdUsuarioRegistro],
    )
    recetas_aprobadas = db.relationship(
        "Receta",
        back_populates="usuario_aprueba",
        foreign_keys=lambda: [Receta.IdUsuarioAprueba],
    )
    solicitudes_realizadas = db.relationship(
        "SolicitudProduccion",
        back_populates="usuario_solicita",
        foreign_keys=lambda: [SolicitudProduccion.IdUsuarioSolicita],
    )
    solicitudes_aprobadas = db.relationship(
        "SolicitudProduccion",
        back_populates="usuario_aprueba",
        foreign_keys=lambda: [SolicitudProduccion.IdUsuarioAprueba],
    )
    producciones_registradas = db.relationship(
        "Produccion",
        back_populates="usuario_registro",
        foreign_keys=lambda: [Produccion.IdUsuarioRegistro],
    )
    movimientos_producto_terminado = db.relationship(
        "MovimientoProductoTerminado",
        back_populates="usuario",
        foreign_keys=lambda: [MovimientoProductoTerminado.IdUsuario],
    )
    ventas_registradas = db.relationship(
        "Venta",
        back_populates="usuario_registro",
        foreign_keys=lambda: [Venta.IdUsuarioRegistro],
    )
    cortes_venta_diario_registrados = db.relationship(
        "CorteVentaDiario",
        back_populates="usuario_registro",
        foreign_keys=lambda: [CorteVentaDiario.IdUsuarioRegistro],
    )
    alertas_destino = db.relationship(
        "AlertaSistema",
        back_populates="usuario_destino",
        foreign_keys=lambda: [AlertaSistema.IdUsuarioDestino],
    )
    sesiones = db.relationship("SesionUsuario", back_populates="usuario")


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
    )


class Proveedor(BaseModel):
    __tablename__ = "Proveedor"

    IdProveedor = db.Column(db.Integer, primary_key=True, autoincrement=True)
    NombreEmpresa = db.Column(db.String(150), nullable=False)
    Telefono = db.Column(db.String(30))
    CorreoElectronico = db.Column(db.String(120))
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    RFC = db.Column(db.String(13), nullable=False, unique=True)

    materias_primas = db.relationship("MateriaPrima", back_populates="proveedor")
    compras_materia_prima = db.relationship(
        "CompraMateriaPrima", back_populates="proveedor"
    )


class UnidadMedida(BaseModel):
    __tablename__ = "UnidadMedida"

    IdUnidadMedida = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Nombre = db.Column(db.String(50), nullable=False, unique=True)
    Abreviatura = db.Column(db.String(20), nullable=False, unique=True)
    Activo = db.Column(db.Boolean, nullable=False, server_default=sql_text("1"))

    materias_primas = db.relationship("MateriaPrima", back_populates="unidad_medida")


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

    proveedor = db.relationship("Proveedor", back_populates="materias_primas")
    unidad_medida = db.relationship("UnidadMedida", back_populates="materias_primas")
    movimientos = db.relationship(
        "MovimientoMateriaPrima", back_populates="materia_prima"
    )
    detalles_compra = db.relationship(
        "CompraMateriaPrimaDetalle", back_populates="materia_prima"
    )
    recetas_detalle = db.relationship("RecetaDetalle", back_populates="materia_prima")


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

    materia_prima = db.relationship("MateriaPrima", back_populates="movimientos")
    usuario = db.relationship(
        "Usuario",
        back_populates="movimientos_materia_prima",
        foreign_keys=[IdUsuario],
    )


class CompraMateriaPrima(BaseModel):
    __tablename__ = "CompraMateriaPrima"

    IdCompraMateriaPrima = db.Column(db.Integer, primary_key=True, autoincrement=True)
    FechaCompra = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    IdProveedor = db.Column(db.Integer, db.ForeignKey("Proveedor.IdProveedor"))
    TotalCompra = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    Observaciones = db.Column(db.String(255))
    IdUsuarioRegistro = db.Column(
        db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False
    )

    proveedor = db.relationship("Proveedor", back_populates="compras_materia_prima")
    usuario_registro = db.relationship(
        "Usuario",
        back_populates="compras_materia_prima_registradas",
        foreign_keys=[IdUsuarioRegistro],
    )
    detalles = db.relationship("CompraMateriaPrimaDetalle", back_populates="compra")


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
    Subtotal = db.Column(db.Numeric(18, 2), nullable=False)

    compra = db.relationship("CompraMateriaPrima", back_populates="detalles")
    materia_prima = db.relationship("MateriaPrima", back_populates="detalles_compra")


class ProductoTerminado(BaseModel):
    __tablename__ = "ProductoTerminado"

    IdProductoTerminado = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Nombre = db.Column(db.String(150), nullable=False)
    Descripcion = db.Column(db.String(255))
    Foto = db.Column(MEDIUMBLOB)
    PrecioVenta = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    CostoProduccion = db.Column(
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
        "SolicitudProduccion", back_populates="producto_terminado"
    )
    producciones = db.relationship("Produccion", back_populates="producto_terminado")
    movimientos = db.relationship(
        "MovimientoProductoTerminado", back_populates="producto_terminado"
    )
    ventas_detalle = db.relationship("VentaDetalle", back_populates="producto_terminado")


class Receta(BaseModel):
    __tablename__ = "Receta"

    IdProductoTerminado = db.Column(
        db.Integer,
        db.ForeignKey("ProductoTerminado.IdProductoTerminado"),
        primary_key=True,
    )
    Merma = db.Column(db.Numeric(18, 2), nullable=False, server_default=sql_text("0"))
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
        foreign_keys=[IdUsuarioRegistro],
    )
    usuario_aprueba = db.relationship(
        "Usuario",
        back_populates="recetas_aprobadas",
        foreign_keys=[IdUsuarioAprueba],
    )
    detalles = db.relationship("RecetaDetalle", back_populates="receta")


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

    receta = db.relationship("Receta", back_populates="detalles")
    materia_prima = db.relationship("MateriaPrima", back_populates="recetas_detalle")


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
        "ProductoTerminado", back_populates="solicitudes_produccion"
    )
    usuario_solicita = db.relationship(
        "Usuario",
        back_populates="solicitudes_realizadas",
        foreign_keys=[IdUsuarioSolicita],
    )
    usuario_aprueba = db.relationship(
        "Usuario",
        back_populates="solicitudes_aprobadas",
        foreign_keys=[IdUsuarioAprueba],
    )
    producciones = db.relationship("Produccion", back_populates="solicitud_produccion")


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
        "SolicitudProduccion", back_populates="producciones"
    )
    producto_terminado = db.relationship(
        "ProductoTerminado", back_populates="producciones"
    )
    usuario_registro = db.relationship(
        "Usuario",
        back_populates="producciones_registradas",
        foreign_keys=[IdUsuarioRegistro],
    )
    defectos = db.relationship("ProduccionDefectuosa", back_populates="produccion")


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

    produccion = db.relationship("Produccion", back_populates="defectos")


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
        "ProductoTerminado", back_populates="movimientos"
    )
    usuario = db.relationship(
        "Usuario",
        back_populates="movimientos_producto_terminado",
        foreign_keys=[IdUsuario],
    )


class Venta(BaseModel):
    __tablename__ = "Venta"

    IdVenta = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdCliente = db.Column(db.Integer, db.ForeignKey("Cliente.IdCliente"))
    FechaVenta = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    TotalVenta = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    IdUsuarioRegistro = db.Column(
        db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False
    )

    cliente = db.relationship("Cliente", back_populates="ventas")
    usuario_registro = db.relationship(
        "Usuario",
        back_populates="ventas_registradas",
        foreign_keys=[IdUsuarioRegistro],
    )
    detalles = db.relationship("VentaDetalle", back_populates="venta")


class VentaDetalle(BaseModel):
    __tablename__ = "VentaDetalle"

    IdVentaDetalle = db.Column(db.Integer, primary_key=True, autoincrement=True)
    IdVenta = db.Column(db.Integer, db.ForeignKey("Venta.IdVenta"), nullable=False)
    IdProductoTerminado = db.Column(
        db.Integer, db.ForeignKey("ProductoTerminado.IdProductoTerminado"), nullable=False
    )
    Cantidad = db.Column(db.Integer, nullable=False)
    PrecioUnitario = db.Column(db.Numeric(18, 2), nullable=False)
    Subtotal = db.Column(db.Numeric(18, 2), nullable=False)

    venta = db.relationship("Venta", back_populates="detalles")
    producto_terminado = db.relationship(
        "ProductoTerminado", back_populates="ventas_detalle"
    )


class CorteVentaDiario(BaseModel):
    __tablename__ = "CorteVentaDiario"

    IdCorteVentaDiario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    FechaCorte = db.Column(db.Date, nullable=False, unique=True)
    TotalVentas = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    TotalCosto = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    UtilidadDiaria = db.Column(
        db.Numeric(18, 2), nullable=False, server_default=sql_text("0")
    )
    FechaRegistro = db.Column(
        db.DateTime, nullable=False, server_default=sql_text("CURRENT_TIMESTAMP")
    )
    IdUsuarioRegistro = db.Column(
        db.Integer, db.ForeignKey("Usuario.IdUsuario"), nullable=False
    )

    usuario_registro = db.relationship(
        "Usuario",
        back_populates="cortes_venta_diario_registrados",
        foreign_keys=[IdUsuarioRegistro],
    )


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
        foreign_keys=[IdUsuarioDestino],
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

    usuario = db.relationship("Usuario", back_populates="sesiones")
