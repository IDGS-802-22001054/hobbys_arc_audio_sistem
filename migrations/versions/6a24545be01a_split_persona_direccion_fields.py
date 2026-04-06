"""split persona direccion fields

Revision ID: 6a24545be01a
Revises: 3d93b5ae1ed3
Create Date: 2026-04-05 12:24:00.896730

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6a24545be01a'
down_revision = '3d93b5ae1ed3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("Persona", sa.Column("Calle", sa.String(length=120), nullable=True))
    op.add_column("Persona", sa.Column("Colonia", sa.String(length=120), nullable=True))
    op.add_column("Persona", sa.Column("NumeroExterior", sa.String(length=20), nullable=True))
    op.add_column("Persona", sa.Column("NumeroInterior", sa.String(length=20), nullable=True))
    op.add_column("Persona", sa.Column("CodigoPostal", sa.String(length=10), nullable=True))

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    persona_columns = {column["name"] for column in inspector.get_columns("Persona")}
    if "Direccion" in persona_columns:
        bind.execute(sa.text("UPDATE Persona SET Calle = Direccion WHERE Direccion IS NOT NULL AND Direccion <> ''"))
        op.drop_column("Persona", "Direccion")

    _recrear_procedimientos_nuevos(bind)


def downgrade():
    op.add_column("Persona", sa.Column("Direccion", sa.String(length=255), nullable=True))

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE Persona
            SET Direccion = NULLIF(
                CONCAT_WS(', ',
                    NULLIF(TRIM(CONCAT(
                        COALESCE(Calle, ''),
                        CASE
                            WHEN NumeroExterior IS NOT NULL AND NumeroExterior <> '' THEN CONCAT(' No. ', NumeroExterior)
                            ELSE ''
                        END,
                        CASE
                            WHEN NumeroInterior IS NOT NULL AND NumeroInterior <> '' THEN CONCAT(' Int. ', NumeroInterior)
                            ELSE ''
                        END
                    )), ''),
                    CASE
                        WHEN Colonia IS NOT NULL AND Colonia <> '' THEN CONCAT('Col. ', Colonia)
                        ELSE NULL
                    END,
                    CASE
                        WHEN CodigoPostal IS NOT NULL AND CodigoPostal <> '' THEN CONCAT('CP ', CodigoPostal)
                        ELSE NULL
                    END
                ),
                ''
            )
            """
        )
    )

    _recrear_procedimientos_anteriores(bind)

    op.drop_column("Persona", "CodigoPostal")
    op.drop_column("Persona", "NumeroInterior")
    op.drop_column("Persona", "NumeroExterior")
    op.drop_column("Persona", "Colonia")
    op.drop_column("Persona", "Calle")


def _drop_procedure(bind, name):
    bind.execute(sa.text(f"DROP PROCEDURE IF EXISTS {name}"))


def _crear_procedimiento(bind, sql):
    bind.execute(sa.text(sql))


def _recrear_procedimientos_nuevos(bind):
    for name in (
        "SP_Clientes_Registrar",
        "SP_Clientes_Ver",
        "SP_Clientes_Editar",
        "SP_Perfil_ActualizarCliente",
        "SP_Empleados_Registrar",
        "SP_Empleados_Ver",
        "SP_Empleados_Actualizar",
        "SP_Perfil_ActualizarPerfil",
    ):
        _drop_procedure(bind, name)

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Clientes_Registrar(
            IN p_Nombre VARCHAR(100),
            IN p_Apellidos VARCHAR(150),
            IN p_Correo VARCHAR(120),
            IN p_Identificador VARCHAR(50),
            IN p_PasswordHash VARCHAR(255),
            IN p_IdRol INT,
            IN p_Calle VARCHAR(120),
            IN p_Colonia VARCHAR(120),
            IN p_NumeroExterior VARCHAR(20),
            IN p_NumeroInterior VARCHAR(20),
            IN p_CodigoPostal VARCHAR(10),
            OUT p_IdCliente INT
        )
        BEGIN
            DECLARE v_IdPersona INT;

            IF EXISTS (SELECT 1 FROM Persona WHERE CorreoElectronico = p_Correo) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'El correo electrónico ya está registrado.';
            END IF;

            IF EXISTS (SELECT 1 FROM Usuario WHERE Identificador = p_Identificador) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'El nombre de usuario ya está en uso.';
            END IF;

            INSERT INTO Persona (
                Nombre, Apellidos, CorreoElectronico, Calle, Colonia,
                NumeroExterior, NumeroInterior, CodigoPostal, Activo
            )
            VALUES (
                p_Nombre, p_Apellidos, p_Correo, p_Calle, p_Colonia,
                p_NumeroExterior, p_NumeroInterior, p_CodigoPostal, 1
            );

            SET v_IdPersona = LAST_INSERT_ID();

            INSERT INTO Cliente (IdPersona, PermiteCompraOnline)
            VALUES (v_IdPersona, 1);

            SET p_IdCliente = LAST_INSERT_ID();

            INSERT INTO Usuario (IdPersona, Identificador, PasswordHash, IdRol, Activo)
            VALUES (v_IdPersona, p_Identificador, p_PasswordHash, p_IdRol, 1);
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Clientes_Ver(IN p_IdCliente INT)
        BEGIN
            SELECT
                c.IdCliente,
                c.PermiteCompraOnline,
                c.FechaRegistro,
                p.Nombre,
                p.Apellidos,
                p.CorreoElectronico,
                p.Telefono,
                p.Calle,
                p.Colonia,
                p.NumeroExterior,
                p.NumeroInterior,
                p.CodigoPostal,
                CONCAT_WS(', ',
                    NULLIF(TRIM(CONCAT(
                        COALESCE(p.Calle, ''),
                        CASE
                            WHEN p.NumeroExterior IS NOT NULL AND p.NumeroExterior <> '' THEN CONCAT(' No. ', p.NumeroExterior)
                            ELSE ''
                        END,
                        CASE
                            WHEN p.NumeroInterior IS NOT NULL AND p.NumeroInterior <> '' THEN CONCAT(' Int. ', p.NumeroInterior)
                            ELSE ''
                        END
                    )), ''),
                    CASE
                        WHEN p.Colonia IS NOT NULL AND p.Colonia <> '' THEN CONCAT('Col. ', p.Colonia)
                        ELSE NULL
                    END,
                    CASE
                        WHEN p.CodigoPostal IS NOT NULL AND p.CodigoPostal <> '' THEN CONCAT('CP ', p.CodigoPostal)
                        ELSE NULL
                    END
                ) AS DireccionFormateada,
                p.Foto,
                p.Activo,
                u.Identificador,
                r.Nombre AS NombreRol
            FROM Cliente c
            INNER JOIN Persona p ON p.IdPersona = c.IdPersona
            LEFT JOIN Usuario u ON u.IdPersona = c.IdPersona
            LEFT JOIN Rol r ON r.IdRol = u.IdRol
            WHERE c.IdCliente = p_IdCliente
            LIMIT 1;
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Clientes_Editar(
            IN p_IdCliente INT,
            IN p_Nombre VARCHAR(100),
            IN p_Apellidos VARCHAR(150),
            IN p_Telefono VARCHAR(30),
            IN p_Correo VARCHAR(120),
            IN p_Calle VARCHAR(120),
            IN p_Colonia VARCHAR(120),
            IN p_NumeroExterior VARCHAR(20),
            IN p_NumeroInterior VARCHAR(20),
            IN p_CodigoPostal VARCHAR(10),
            IN p_Foto TEXT
        )
        BEGIN
            UPDATE Persona
            SET
                Nombre = p_Nombre,
                Apellidos = p_Apellidos,
                Telefono = p_Telefono,
                CorreoElectronico = p_Correo,
                Calle = p_Calle,
                Colonia = p_Colonia,
                NumeroExterior = p_NumeroExterior,
                NumeroInterior = p_NumeroInterior,
                CodigoPostal = p_CodigoPostal,
                Foto = COALESCE(NULLIF(p_Foto, ''), Foto)
            WHERE IdPersona = (
                SELECT IdPersona FROM Cliente WHERE IdCliente = p_IdCliente
            );
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Perfil_ActualizarCliente(
            IN p_IdCliente INT,
            IN p_Nombre VARCHAR(100),
            IN p_Apellidos VARCHAR(150),
            IN p_Telefono VARCHAR(30),
            IN p_Correo VARCHAR(120),
            IN p_Calle VARCHAR(120),
            IN p_Colonia VARCHAR(120),
            IN p_NumeroExterior VARCHAR(20),
            IN p_NumeroInterior VARCHAR(20),
            IN p_CodigoPostal VARCHAR(10),
            IN p_Foto TEXT,
            IN p_Identificador VARCHAR(50),
            IN p_PasswordHash VARCHAR(255)
        )
        BEGIN
            UPDATE Persona
            SET
                Nombre = p_Nombre,
                Apellidos = p_Apellidos,
                Telefono = p_Telefono,
                CorreoElectronico = p_Correo,
                Calle = p_Calle,
                Colonia = p_Colonia,
                NumeroExterior = p_NumeroExterior,
                NumeroInterior = p_NumeroInterior,
                CodigoPostal = p_CodigoPostal,
                Foto = COALESCE(NULLIF(p_Foto, ''), Foto)
            WHERE IdPersona = (
                SELECT IdPersona FROM Cliente WHERE IdCliente = p_IdCliente
            );

            UPDATE Usuario
            SET
                Identificador = p_Identificador,
                PasswordHash = COALESCE(p_PasswordHash, PasswordHash)
            WHERE IdPersona = (
                SELECT IdPersona FROM Cliente WHERE IdCliente = p_IdCliente
            );
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Empleados_Registrar(
            IN p_Nombre VARCHAR(100),
            IN p_Apellidos VARCHAR(150),
            IN p_Telefono VARCHAR(20),
            IN p_CorreoElectronico VARCHAR(150),
            IN p_Calle VARCHAR(120),
            IN p_Colonia VARCHAR(120),
            IN p_NumeroExterior VARCHAR(20),
            IN p_NumeroInterior VARCHAR(20),
            IN p_CodigoPostal VARCHAR(10),
            IN p_Foto LONGTEXT,
            IN p_Puesto VARCHAR(100),
            IN p_FechaIngreso DATE,
            IN p_Salario DECIMAL(10,2),
            IN p_Identificador VARCHAR(100),
            IN p_PasswordHash VARCHAR(255),
            IN p_IdRol INT,
            OUT p_IdEmpleado INT
        )
        BEGIN
            DECLARE v_IdPersona INT;

            INSERT INTO Persona (
                Nombre, Apellidos, Telefono, CorreoElectronico, Calle, Colonia,
                NumeroExterior, NumeroInterior, CodigoPostal, Foto
            )
            VALUES (
                p_Nombre, p_Apellidos, p_Telefono, p_CorreoElectronico, p_Calle, p_Colonia,
                p_NumeroExterior, p_NumeroInterior, p_CodigoPostal, p_Foto
            );

            SET v_IdPersona = LAST_INSERT_ID();

            INSERT INTO Empleado (IdPersona, Puesto, FechaIngreso, Salario)
            VALUES (v_IdPersona, p_Puesto, p_FechaIngreso, p_Salario);

            SET p_IdEmpleado = LAST_INSERT_ID();

            IF p_Identificador IS NOT NULL AND p_Identificador <> '' THEN
                INSERT INTO Usuario (IdPersona, Identificador, PasswordHash, IdRol)
                VALUES (v_IdPersona, p_Identificador, p_PasswordHash, p_IdRol);
            END IF;
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Empleados_Ver(IN p_IdEmpleado INT)
        BEGIN
            SELECT
                e.IdEmpleado,
                e.Puesto,
                e.Salario,
                e.FechaIngreso,
                e.Activo,
                p.Nombre,
                p.Apellidos,
                p.CorreoElectronico,
                p.Telefono,
                p.Calle,
                p.Colonia,
                p.NumeroExterior,
                p.NumeroInterior,
                p.CodigoPostal,
                CONCAT_WS(', ',
                    NULLIF(TRIM(CONCAT(
                        COALESCE(p.Calle, ''),
                        CASE
                            WHEN p.NumeroExterior IS NOT NULL AND p.NumeroExterior <> '' THEN CONCAT(' No. ', p.NumeroExterior)
                            ELSE ''
                        END,
                        CASE
                            WHEN p.NumeroInterior IS NOT NULL AND p.NumeroInterior <> '' THEN CONCAT(' Int. ', p.NumeroInterior)
                            ELSE ''
                        END
                    )), ''),
                    CASE
                        WHEN p.Colonia IS NOT NULL AND p.Colonia <> '' THEN CONCAT('Col. ', p.Colonia)
                        ELSE NULL
                    END,
                    CASE
                        WHEN p.CodigoPostal IS NOT NULL AND p.CodigoPostal <> '' THEN CONCAT('CP ', p.CodigoPostal)
                        ELSE NULL
                    END
                ) AS DireccionFormateada,
                p.Foto,
                u.IdRol,
                u.Identificador,
                u.PasswordHash,
                r.Nombre AS NombreRol
            FROM Empleado e
            INNER JOIN Persona p ON p.IdPersona = e.IdPersona
            LEFT JOIN Usuario u ON u.IdPersona = e.IdPersona
            LEFT JOIN Rol r ON r.IdRol = u.IdRol
            WHERE e.IdEmpleado = p_IdEmpleado
            LIMIT 1;
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Empleados_Actualizar(
            IN p_IdEmpleado INT,
            IN p_Nombre VARCHAR(100),
            IN p_Apellidos VARCHAR(150),
            IN p_Telefono VARCHAR(20),
            IN p_CorreoElectronico VARCHAR(150),
            IN p_Calle VARCHAR(120),
            IN p_Colonia VARCHAR(120),
            IN p_NumeroExterior VARCHAR(20),
            IN p_NumeroInterior VARCHAR(20),
            IN p_CodigoPostal VARCHAR(10),
            IN p_Foto LONGTEXT,
            IN p_Puesto VARCHAR(100),
            IN p_Salario DECIMAL(10,2),
            IN p_Identificador VARCHAR(100),
            IN p_PasswordHash VARCHAR(255),
            IN p_IdRol INT
        )
        BEGIN
            DECLARE v_IdPersona INT;
            DECLARE v_UsuarioExiste INT DEFAULT 0;

            SELECT IdPersona INTO v_IdPersona
            FROM Empleado
            WHERE IdEmpleado = p_IdEmpleado;

            UPDATE Persona
            SET
                Nombre = p_Nombre,
                Apellidos = p_Apellidos,
                Telefono = p_Telefono,
                CorreoElectronico = p_CorreoElectronico,
                Calle = p_Calle,
                Colonia = p_Colonia,
                NumeroExterior = p_NumeroExterior,
                NumeroInterior = p_NumeroInterior,
                CodigoPostal = p_CodigoPostal,
                Foto = COALESCE(p_Foto, Foto)
            WHERE IdPersona = v_IdPersona;

            UPDATE Empleado
            SET
                Puesto = p_Puesto,
                Salario = p_Salario
            WHERE IdEmpleado = p_IdEmpleado;

            SELECT COUNT(*) INTO v_UsuarioExiste
            FROM Usuario
            WHERE IdPersona = v_IdPersona;

            IF v_UsuarioExiste > 0 THEN
                UPDATE Usuario
                SET
                    Identificador = p_Identificador,
                    IdRol = p_IdRol,
                    PasswordHash = COALESCE(p_PasswordHash, PasswordHash)
                WHERE IdPersona = v_IdPersona;

            ELSEIF p_Identificador IS NOT NULL AND p_Identificador <> '' THEN
                INSERT INTO Usuario (IdPersona, Identificador, PasswordHash, IdRol)
                VALUES (v_IdPersona, p_Identificador, p_PasswordHash, p_IdRol);
            END IF;
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Perfil_ActualizarPerfil(
            IN p_IdEmpleado INT,
            IN p_Nombre VARCHAR(100),
            IN p_Apellidos VARCHAR(150),
            IN p_Telefono VARCHAR(30),
            IN p_Correo VARCHAR(120),
            IN p_Calle VARCHAR(120),
            IN p_Colonia VARCHAR(120),
            IN p_NumeroExterior VARCHAR(20),
            IN p_NumeroInterior VARCHAR(20),
            IN p_CodigoPostal VARCHAR(10),
            IN p_Foto TEXT,
            IN p_Identificador VARCHAR(50),
            IN p_PasswordHash VARCHAR(255)
        )
        BEGIN
            UPDATE Persona
            SET
                Nombre = p_Nombre,
                Apellidos = p_Apellidos,
                Telefono = p_Telefono,
                CorreoElectronico = p_Correo,
                Calle = p_Calle,
                Colonia = p_Colonia,
                NumeroExterior = p_NumeroExterior,
                NumeroInterior = p_NumeroInterior,
                CodigoPostal = p_CodigoPostal,
                Foto = COALESCE(NULLIF(p_Foto, ''), Foto)
            WHERE IdPersona = (
                SELECT IdPersona
                FROM Empleado
                WHERE IdEmpleado = p_IdEmpleado
            );

            UPDATE Usuario
            SET
                Identificador = p_Identificador,
                PasswordHash = COALESCE(p_PasswordHash, PasswordHash)
            WHERE IdPersona = (
                SELECT IdPersona
                FROM Empleado
                WHERE IdEmpleado = p_IdEmpleado
            );
        END
        """,
    )


def _recrear_procedimientos_anteriores(bind):
    for name in (
        "SP_Clientes_Registrar",
        "SP_Clientes_Ver",
        "SP_Clientes_Editar",
        "SP_Perfil_ActualizarCliente",
        "SP_Empleados_Registrar",
        "SP_Empleados_Ver",
        "SP_Empleados_Actualizar",
        "SP_Perfil_ActualizarPerfil",
    ):
        _drop_procedure(bind, name)

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Clientes_Registrar(
            IN p_Nombre VARCHAR(100),
            IN p_Apellidos VARCHAR(150),
            IN p_Correo VARCHAR(120),
            IN p_Identificador VARCHAR(50),
            IN p_PasswordHash VARCHAR(255),
            IN p_IdRol INT,
            OUT p_IdCliente INT
        )
        BEGIN
            DECLARE v_IdPersona INT;

            IF EXISTS (SELECT 1 FROM Persona WHERE CorreoElectronico = p_Correo) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'El correo electrónico ya está registrado.';
            END IF;

            IF EXISTS (SELECT 1 FROM Usuario WHERE Identificador = p_Identificador) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'El nombre de usuario ya está en uso.';
            END IF;

            INSERT INTO Persona (Nombre, Apellidos, CorreoElectronico, Direccion, Activo)
            VALUES (p_Nombre, p_Apellidos, p_Correo, NULL, 1);

            SET v_IdPersona = LAST_INSERT_ID();

            INSERT INTO Cliente (IdPersona, PermiteCompraOnline)
            VALUES (v_IdPersona, 1);

            SET p_IdCliente = LAST_INSERT_ID();

            INSERT INTO Usuario (IdPersona, Identificador, PasswordHash, IdRol, Activo)
            VALUES (v_IdPersona, p_Identificador, p_PasswordHash, p_IdRol, 1);
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Clientes_Ver(IN p_IdCliente INT)
        BEGIN
            SELECT
                c.IdCliente,
                c.PermiteCompraOnline,
                c.FechaRegistro,
                p.Nombre,
                p.Apellidos,
                p.CorreoElectronico,
                p.Telefono,
                p.Direccion,
                p.Foto,
                p.Activo,
                u.Identificador,
                r.Nombre AS NombreRol
            FROM Cliente c
            INNER JOIN Persona p ON p.IdPersona = c.IdPersona
            LEFT JOIN Usuario u ON u.IdPersona = c.IdPersona
            LEFT JOIN Rol r ON r.IdRol = u.IdRol
            WHERE c.IdCliente = p_IdCliente
            LIMIT 1;
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Perfil_ActualizarCliente(
            IN p_IdCliente INT,
            IN p_Nombre VARCHAR(100),
            IN p_Apellidos VARCHAR(150),
            IN p_Telefono VARCHAR(30),
            IN p_Correo VARCHAR(120),
            IN p_Direccion VARCHAR(255),
            IN p_Foto TEXT,
            IN p_Identificador VARCHAR(50),
            IN p_PasswordHash VARCHAR(255)
        )
        BEGIN
            UPDATE Persona
            SET
                Nombre = p_Nombre,
                Apellidos = p_Apellidos,
                Telefono = p_Telefono,
                CorreoElectronico = p_Correo,
                Direccion = p_Direccion,
                Foto = COALESCE(NULLIF(p_Foto, ''), Foto)
            WHERE IdPersona = (
                SELECT IdPersona FROM Cliente WHERE IdCliente = p_IdCliente
            );

            UPDATE Usuario
            SET
                Identificador = p_Identificador,
                PasswordHash = COALESCE(p_PasswordHash, PasswordHash)
            WHERE IdPersona = (
                SELECT IdPersona FROM Cliente WHERE IdCliente = p_IdCliente
            );
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Empleados_Registrar(
            IN p_Nombre VARCHAR(100),
            IN p_Apellidos VARCHAR(150),
            IN p_Telefono VARCHAR(20),
            IN p_CorreoElectronico VARCHAR(150),
            IN p_Direccion VARCHAR(250),
            IN p_Foto LONGTEXT,
            IN p_Puesto VARCHAR(100),
            IN p_FechaIngreso DATE,
            IN p_Salario DECIMAL(10,2),
            IN p_Identificador VARCHAR(100),
            IN p_PasswordHash VARCHAR(255),
            IN p_IdRol INT,
            OUT p_IdEmpleado INT
        )
        BEGIN
            DECLARE v_IdPersona INT;

            INSERT INTO Persona (Nombre, Apellidos, Telefono, CorreoElectronico, Direccion, Foto)
            VALUES (p_Nombre, p_Apellidos, p_Telefono, p_CorreoElectronico, p_Direccion, p_Foto);

            SET v_IdPersona = LAST_INSERT_ID();

            INSERT INTO Empleado (IdPersona, Puesto, FechaIngreso, Salario)
            VALUES (v_IdPersona, p_Puesto, p_FechaIngreso, p_Salario);

            SET p_IdEmpleado = LAST_INSERT_ID();

            IF p_Identificador IS NOT NULL AND p_Identificador <> '' THEN
                INSERT INTO Usuario (IdPersona, Identificador, PasswordHash, IdRol)
                VALUES (v_IdPersona, p_Identificador, p_PasswordHash, p_IdRol);
            END IF;
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Empleados_Ver(IN p_IdEmpleado INT)
        BEGIN
            SELECT
                e.IdEmpleado,
                e.Puesto,
                e.Salario,
                e.FechaIngreso,
                e.Activo,
                p.Nombre,
                p.Apellidos,
                p.CorreoElectronico,
                p.Telefono,
                p.Direccion,
                p.Foto,
                u.IdRol,
                u.Identificador,
                u.PasswordHash,
                r.Nombre AS NombreRol
            FROM Empleado e
            INNER JOIN Persona p ON p.IdPersona = e.IdPersona
            LEFT JOIN Usuario u ON u.IdPersona = e.IdPersona
            LEFT JOIN Rol r ON r.IdRol = u.IdRol
            WHERE e.IdEmpleado = p_IdEmpleado
            LIMIT 1;
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Empleados_Actualizar(
            IN p_IdEmpleado INT,
            IN p_Nombre VARCHAR(100),
            IN p_Apellidos VARCHAR(150),
            IN p_Telefono VARCHAR(20),
            IN p_CorreoElectronico VARCHAR(150),
            IN p_Direccion VARCHAR(250),
            IN p_Foto LONGTEXT,
            IN p_Puesto VARCHAR(100),
            IN p_Salario DECIMAL(10,2),
            IN p_Identificador VARCHAR(100),
            IN p_PasswordHash VARCHAR(255),
            IN p_IdRol INT
        )
        BEGIN
            DECLARE v_IdPersona INT;
            DECLARE v_UsuarioExiste INT DEFAULT 0;

            SELECT IdPersona INTO v_IdPersona
            FROM Empleado
            WHERE IdEmpleado = p_IdEmpleado;

            UPDATE Persona
            SET
                Nombre = p_Nombre,
                Apellidos = p_Apellidos,
                Telefono = p_Telefono,
                CorreoElectronico = p_CorreoElectronico,
                Direccion = p_Direccion,
                Foto = COALESCE(p_Foto, Foto)
            WHERE IdPersona = v_IdPersona;

            UPDATE Empleado
            SET
                Puesto = p_Puesto,
                Salario = p_Salario
            WHERE IdEmpleado = p_IdEmpleado;

            SELECT COUNT(*) INTO v_UsuarioExiste
            FROM Usuario
            WHERE IdPersona = v_IdPersona;

            IF v_UsuarioExiste > 0 THEN
                UPDATE Usuario
                SET
                    Identificador = p_Identificador,
                    IdRol = p_IdRol,
                    PasswordHash = COALESCE(p_PasswordHash, PasswordHash)
                WHERE IdPersona = v_IdPersona;

            ELSEIF p_Identificador IS NOT NULL AND p_Identificador <> '' THEN
                INSERT INTO Usuario (IdPersona, Identificador, PasswordHash, IdRol)
                VALUES (v_IdPersona, p_Identificador, p_PasswordHash, p_IdRol);
            END IF;
        END
        """,
    )

    _crear_procedimiento(
        bind,
        """
        CREATE PROCEDURE SP_Perfil_ActualizarPerfil(
            IN p_IdEmpleado INT,
            IN p_Nombre VARCHAR(100),
            IN p_Apellidos VARCHAR(150),
            IN p_Telefono VARCHAR(30),
            IN p_Correo VARCHAR(120),
            IN p_Direccion VARCHAR(255),
            IN p_Foto TEXT,
            IN p_Identificador VARCHAR(50),
            IN p_PasswordHash VARCHAR(255)
        )
        BEGIN
            UPDATE Persona
            SET
                Nombre = p_Nombre,
                Apellidos = p_Apellidos,
                Telefono = p_Telefono,
                CorreoElectronico = p_Correo,
                Direccion = p_Direccion,
                Foto = COALESCE(NULLIF(p_Foto, ''), Foto)
            WHERE IdPersona = (
                SELECT IdPersona
                FROM Empleado
                WHERE IdEmpleado = p_IdEmpleado
            );

            UPDATE Usuario
            SET
                Identificador = p_Identificador,
                PasswordHash = COALESCE(p_PasswordHash, PasswordHash)
            WHERE IdPersona = (
                SELECT IdPersona
                FROM Empleado
                WHERE IdEmpleado = p_IdEmpleado
            );
        END
        """,
    )
