from wtforms import Form
from wtforms import StringField, IntegerField, DecimalField, PasswordField, SelectField, BooleanField
from wtforms import EmailField, DateField, FileField
from wtforms import validators

class LoginForm(Form):
    identificador = StringField('Usuario', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Length(min=3, max=50, message='Ingrese un usuario válido')
    ])
    password = PasswordField('Contraseña', [
        validators.DataRequired(message='El campo es requerido')
    ])


class EmpleadoForm(Form):
    nombre = StringField('Nombre', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Length(min=2, max=100, message='Ingrese un nombre válido')
    ])
    apellidos = StringField('Apellidos', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Length(min=2, max=150, message='Ingrese apellidos válidos')
    ])
    correo = EmailField('Correo Electrónico', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Email(message='Ingrese un correo válido')
    ])
    telefono = StringField('Teléfono', [
        validators.Optional(),
        validators.Length(max=30, message='Teléfono demasiado largo')
    ])
    calle = StringField('Calle', [
        validators.Optional(),
        validators.Length(max=120, message='La calle es demasiado larga')
    ])
    colonia = StringField('Colonia', [
        validators.Optional(),
        validators.Length(max=120, message='La colonia es demasiado larga')
    ])
    numero_exterior = StringField('Número Exterior', [
        validators.Optional(),
        validators.Length(max=20, message='El número exterior es demasiado largo')
    ])
    numero_interior = StringField('Número Interior', [
        validators.Optional(),
        validators.Length(max=20, message='El número interior es demasiado largo')
    ])
    codigo_postal = StringField('Código Postal', [
        validators.Optional(),
        validators.Length(max=10, message='El código postal es demasiado largo')
    ])
    foto = FileField('Foto', [validators.Optional()])

    puesto = StringField('Puesto', [
        validators.Optional(),
        validators.Length(max=100, message='Puesto demasiado largo')
    ])
    salario = DecimalField('Salario', [
        validators.Optional()
    ], places=2, rounding=None)
    fecha_ingreso = DateField('Fecha de Ingreso', [
        validators.Optional()
    ])
    activo = BooleanField('Activo')

    identificador = StringField('Usuario', [
        validators.Optional(),
        validators.Length(min=3, max=50, message='El usuario debe tener entre 3 y 50 caracteres')
    ])
    password = PasswordField('Contraseña', [
        validators.Optional(),
        validators.Length(min=6, message='La contraseña debe tener al menos 6 caracteres')
    ])
    id_rol = SelectField('Rol', [
        validators.Optional()
    ], coerce=int, choices=[])


class ClienteForm(Form):
    nombre = StringField('Nombre', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Length(min=2, max=100, message='Ingrese un nombre válido')
    ])
    apellidos = StringField('Apellidos', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Length(min=2, max=150, message='Ingrese apellidos válidos')
    ])
    correo = EmailField('Correo Electrónico', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Email(message='Ingrese un correo válido')
    ])
    telefono = StringField('Teléfono', [
        validators.Optional(),
        validators.Length(max=30, message='Teléfono demasiado largo')
    ])
    calle = StringField('Calle', [
        validators.Optional(),
        validators.Length(max=120, message='La calle es demasiado larga')
    ])
    colonia = StringField('Colonia', [
        validators.Optional(),
        validators.Length(max=120, message='La colonia es demasiado larga')
    ])
    numero_exterior = StringField('Número Exterior', [
        validators.Optional(),
        validators.Length(max=20, message='El número exterior es demasiado largo')
    ])
    numero_interior = StringField('Número Interior', [
        validators.Optional(),
        validators.Length(max=20, message='El número interior es demasiado largo')
    ])
    codigo_postal = StringField('Código Postal', [
        validators.Optional(),
        validators.Length(max=10, message='El código postal es demasiado largo')
    ])
    foto = FileField('Foto', [validators.Optional()])

    permite_compra_online = BooleanField('Permite Compra Online')

class ClientePerfilForm(Form):
    nombre = StringField('Nombre', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Length(min=2, max=100, message='Ingrese un nombre válido')
    ])
    apellidos = StringField('Apellidos', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Length(min=2, max=150, message='Ingrese apellidos válidos')
    ])
    correo = EmailField('Correo Electrónico', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Email(message='Ingrese un correo válido')
    ])
    telefono = StringField('Teléfono', [
        validators.Optional(),
        validators.Length(max=30, message='Teléfono demasiado largo')
    ])
    calle = StringField('Calle', [
        validators.Optional(),
        validators.Length(max=120, message='La calle es demasiado larga')
    ])
    colonia = StringField('Colonia', [
        validators.Optional(),
        validators.Length(max=120, message='La colonia es demasiado larga')
    ])
    numero_exterior = StringField('Número Exterior', [
        validators.Optional(),
        validators.Length(max=20, message='El número exterior es demasiado largo')
    ])
    numero_interior = StringField('Número Interior', [
        validators.Optional(),
        validators.Length(max=20, message='El número interior es demasiado largo')
    ])
    codigo_postal = StringField('Código Postal', [
        validators.Optional(),
        validators.Length(max=10, message='El código postal es demasiado largo')
    ])
    foto = FileField('Foto', [validators.Optional()])
    identificador = StringField('Usuario', [
        validators.Optional(),
        validators.Length(min=3, max=50, message='El usuario debe tener entre 3 y 50 caracteres')
    ])
    password = PasswordField('Contraseña', [
        validators.Optional(),
        validators.Length(min=6, message='La contraseña debe tener al menos 6 caracteres')
    ])

class ProductoTerminadoForm(Form):
    nombre = StringField('Nombre', [
        validators.DataRequired(message='El campo es requerido'),
        validators.Length(min=2, max=150, message='Nombre demasiado largo')
    ])
    descripcion = StringField('Descripción', [
        validators.Optional(),
        validators.Length(max=255)
    ])
    precio_venta = DecimalField('Precio de Venta', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0, message='El precio no puede ser negativo')
    ], places=2, rounding=None)
    costo_produccion = DecimalField('Costo de Producción', [
        validators.Optional(),
        validators.NumberRange(min=0, message='El costo no puede ser negativo')
    ], places=2, rounding=None)
    stock_minimo = IntegerField('Stock Mínimo', [
        validators.Optional(),
        validators.NumberRange(min=0, message='El stock mínimo no puede ser negativo')
    ])
    foto = FileField('Foto', [validators.Optional()])
    activo = BooleanField('Activo')

class RecetaForm(Form):
    merma = DecimalField('Merma', [
        validators.Optional(),
        validators.NumberRange(min=0, message='La merma no puede ser negativa')
    ], places=2, rounding=None)
    requiere_aprobacion = BooleanField('Requiere Aprobación')
    activa = BooleanField('Activa')


class RecetaDetalleForm(Form):
    id_materia_prima = SelectField('Materia Prima', [
        validators.DataRequired(message='Seleccione una materia prima')
    ], coerce=int, choices=[])
    cantidad_requerida = DecimalField('Cantidad Requerida', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0.01, message='La cantidad debe ser mayor a 0')
    ], places=2, rounding=None)


class SolicitudProduccionForm(Form):
    id_producto_terminado = SelectField('Producto', [
        validators.DataRequired(message='Seleccione un producto')
    ], coerce=int, choices=[])
    cantidad_solicitada = IntegerField('Cantidad Solicitada', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=1, message='La cantidad debe ser al menos 1')
    ])
    motivo = StringField('Motivo', [
        validators.Optional(),
        validators.Length(max=255)
    ])


class AprobarSolicitudForm(Form):
    observaciones = StringField('Observaciones', [
        validators.Optional(),
        validators.Length(max=255)
    ])

class ProduccionForm(Form):
    id_solicitud_produccion = SelectField('Solicitud', [
        validators.Optional()
    ], coerce=int, choices=[])
    id_producto_terminado = SelectField('Producto', [
        validators.DataRequired(message='Seleccione un producto')
    ], coerce=int, choices=[])
    cantidad_planeada = IntegerField('Cantidad Planeada', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=1, message='La cantidad debe ser al menos 1')
    ])
    fecha_inicio = DateField('Fecha Inicio', [validators.Optional()])
    fecha_fin    = DateField('Fecha Fin',    [validators.Optional()])


class RegistrarProduccionForm(Form):
    cantidad_fabricada   = IntegerField('Cantidad Fabricada', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=0)
    ])
    cantidad_defectuosa  = IntegerField('Cantidad Defectuosa', [
        validators.Optional(),
        validators.NumberRange(min=0)
    ])


class ProduccionDefectuosaForm(Form):
    cantidad_defectuosa = IntegerField('Cantidad Defectuosa', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=1, message='Debe registrar al menos 1 pieza defectuosa')
    ])
    descripcion = StringField('Descripción', [
        validators.Optional(),
        validators.Length(max=255)
    ])

class ConfiguracionSistemaForm(Form):
    cantidad_minima_materia_prima = IntegerField('Stock Mínimo Materia Prima', [
        validators.Optional(),
        validators.NumberRange(min=0, message='No puede ser negativo')
    ])
    cantidad_minima_producto_terminado = IntegerField('Stock Mínimo Producto Terminado', [
        validators.Optional(),
        validators.NumberRange(min=0, message='No puede ser negativo')
    ])
    horas_inactividad_cierre_sesion = IntegerField('Tiempo de Inactividad para Cerrar Sesión', [
        validators.DataRequired(message='El campo es requerido'),
        validators.NumberRange(min=1, max=1440, message='Ingresa un tiempo de inactividad valido')
    ])
    unidad_inactividad_cierre_sesion = SelectField('Unidad de Tiempo', [
        validators.DataRequired(message='Selecciona una unidad de tiempo')
    ], choices=[('HORAS', 'Horas'), ('MINUTOS', 'Minutos')])
    alertar_pocas_piezas_terminadas = BooleanField('Alertar Pocas Piezas Terminadas')
    alertar_materia_prima_minima    = BooleanField('Alertar Materia Prima Mínima')
