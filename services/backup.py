from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine.url import make_url


class BackupError(Exception):
    pass


def _ruta_documentos() -> Path:
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        documentos = Path(user_profile) / "Documents"
        if documentos.exists():
            return documentos

    return Path.home() / "Documents"


def _resolver_mysqldump() -> str:
    ejecutable = shutil.which("mysqldump")
    if ejecutable:
        return ejecutable

    posibles = [
        Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"),
        Path(r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe"),
        Path(r"C:\Program Files\MariaDB 11.4\bin\mysqldump.exe"),
        Path(r"C:\Program Files\MariaDB 11.3\bin\mysqldump.exe"),
    ]

    for ruta in posibles:
        if ruta.exists():
            return str(ruta)

    raise BackupError(
        "No se encontro mysqldump en el PATH ni en las rutas comunes de MySQL/MariaDB."
    )


def _resolver_mysqlbinlog() -> str:
    ejecutable = shutil.which("mysqlbinlog")
    if ejecutable:
        return ejecutable

    posibles = [
        Path(r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqlbinlog.exe"),
        Path(r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqlbinlog.exe"),
        Path(r"C:\Program Files\MariaDB 11.4\bin\mysqlbinlog.exe"),
        Path(r"C:\Program Files\MariaDB 11.3\bin\mysqlbinlog.exe"),
    ]

    for ruta in posibles:
        if ruta.exists():
            return str(ruta)

    raise BackupError(
        "No se encontro mysqlbinlog en el PATH ni en las rutas comunes de MySQL/MariaDB."
    )


def _normalizar_base_datos(database_uri: str) -> dict:
    url = make_url(database_uri)
    if not url.drivername.startswith("mysql"):
        raise BackupError("El respaldo automatico solo esta soportado para bases de datos MySQL.")

    if not url.database:
        raise BackupError("No se pudo determinar el nombre de la base de datos a respaldar.")

    return {
        "host": url.host or "localhost",
        "port": str(url.port or 3306),
        "user": url.username or "",
        "password": url.password or "",
        "database": url.database,
    }


def _entorno_mysql(conexion: dict) -> dict:
    entorno = os.environ.copy()
    if conexion["password"]:
        entorno["MYSQL_PWD"] = conexion["password"]
    return entorno


def _obtener_variable_mysql(engine, nombre: str):
    with engine.connect() as conexion:
        fila = conexion.execute(
            text("SHOW VARIABLES LIKE :nombre"),
            {"nombre": nombre},
        ).fetchone()
    return fila[1] if fila else None


def _binlog_habilitado(engine) -> bool:
    valor = (_obtener_variable_mysql(engine, "log_bin") or "").strip().upper()
    return valor in {"ON", "1"}


def _obtener_master_status(engine) -> dict:
    with engine.connect() as conexion:
        fila = conexion.execute(text("SHOW MASTER STATUS")).mappings().first()

    if not fila:
        raise BackupError("No fue posible obtener la posicion actual del binary log.")

    return {
        "archivo": fila.get("File"),
        "posicion": int(fila.get("Position") or 0),
    }


def _obtener_binlogs_disponibles(engine) -> list[str]:
    with engine.connect() as conexion:
        filas = conexion.execute(text("SHOW BINARY LOGS")).fetchall()

    return [fila[0] for fila in filas]


def _extraer_posicion_desde_dump(archivo: Path) -> tuple[str | None, int | None]:
    patron = re.compile(
        r"MASTER_LOG_FILE='([^']+)'.*MASTER_LOG_POS=(\d+)",
        re.IGNORECASE,
    )

    with archivo.open("r", encoding="utf-8", errors="ignore") as descriptor:
        for linea in descriptor:
            coincidencia = patron.search(linea)
            if coincidencia:
                return coincidencia.group(1), int(coincidencia.group(2))

    return None, None


def crear_backup_completo(database_uri: str, engine) -> dict:
    conexion = _normalizar_base_datos(database_uri)
    destino = _ruta_documentos() / "backupsH"
    destino.mkdir(parents=True, exist_ok=True)

    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = destino / f"{conexion['database']}_backup_completo_{marca_tiempo}.sql"

    comando = [
        _resolver_mysqldump(),
        f"--host={conexion['host']}",
        f"--port={conexion['port']}",
        f"--user={conexion['user']}",
        "--default-character-set=utf8mb4",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--events",
        f"--result-file={archivo}",
        conexion["database"],
    ]

    if _binlog_habilitado(engine):
        comando.insert(-2, "--master-data=2")

    entorno = _entorno_mysql(conexion)

    try:
        resultado = subprocess.run(
            comando,
            check=False,
            capture_output=True,
            text=True,
            env=entorno,
        )
    except OSError as error:
        raise BackupError(f"No se pudo ejecutar mysqldump: {error}") from error

    if resultado.returncode != 0:
        mensaje = (resultado.stderr or resultado.stdout or "Error desconocido.").strip()
        raise BackupError(f"mysqldump termino con error: {mensaje}")

    if not archivo.exists():
        raise BackupError("El respaldo se ejecuto pero no se encontro el archivo de salida.")

    archivo_binlog, posicion_binlog = _extraer_posicion_desde_dump(archivo)

    return {
        "archivo": archivo,
        "tipo": "COMPLETO",
        "binlog_archivo_inicio": archivo_binlog,
        "binlog_posicion_inicio": posicion_binlog,
        "binlog_archivo_fin": archivo_binlog,
        "binlog_posicion_fin": posicion_binlog,
    }


def crear_backup_incremental(
    database_uri: str,
    engine,
    archivo_inicio: str,
    posicion_inicio: int,
) -> dict:
    conexion = _normalizar_base_datos(database_uri)
    if not _binlog_habilitado(engine):
        raise BackupError(
            "El servidor MySQL no tiene binary logging habilitado; no es posible generar un backup incremental."
        )

    if not archivo_inicio or not posicion_inicio:
        raise BackupError(
            "No existe una posicion inicial valida de binlog. Genera primero un backup completo nuevo."
        )

    estado_actual = _obtener_master_status(engine)
    archivo_fin = estado_actual["archivo"]
    posicion_fin = estado_actual["posicion"]

    destino = _ruta_documentos() / "backupsH"
    destino.mkdir(parents=True, exist_ok=True)
    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo_salida = destino / f"{conexion['database']}_backup_incremental_{marca_tiempo}.sql"

    if archivo_inicio == archivo_fin and int(posicion_inicio) == int(posicion_fin):
        archivo_salida.write_text(
            "-- No hay cambios nuevos en los binlogs para generar un backup incremental.\n",
            encoding="utf-8",
        )
        return {
            "archivo": archivo_salida,
            "tipo": "INCREMENTAL",
            "binlog_archivo_inicio": archivo_inicio,
            "binlog_posicion_inicio": int(posicion_inicio),
            "binlog_archivo_fin": archivo_fin,
            "binlog_posicion_fin": int(posicion_fin),
        }

    binlogs_disponibles = _obtener_binlogs_disponibles(engine)
    if archivo_inicio not in binlogs_disponibles:
        raise BackupError(
            "El binlog de inicio ya no esta disponible en el servidor. Genera un backup completo nuevo."
        )

    if archivo_fin not in binlogs_disponibles:
        raise BackupError("No se encontro el binlog final actual en el servidor.")

    indice_inicio = binlogs_disponibles.index(archivo_inicio)
    indice_fin = binlogs_disponibles.index(archivo_fin)
    if indice_inicio > indice_fin:
        raise BackupError("La posicion de binlog inicial es posterior a la actual.")

    binlogs_a_exportar = binlogs_disponibles[indice_inicio : indice_fin + 1]
    comando = [
        _resolver_mysqlbinlog(),
        "--read-from-remote-server",
        f"--host={conexion['host']}",
        f"--port={conexion['port']}",
        f"--user={conexion['user']}",
        f"--database={conexion['database']}",
        f"--start-position={int(posicion_inicio)}",
        f"--result-file={archivo_salida}",
    ]

    if archivo_inicio == archivo_fin:
        comando.append(f"--stop-position={int(posicion_fin)}")
    else:
        comando.append(f"--stop-position={int(posicion_fin)}")

    comando.extend(binlogs_a_exportar)

    entorno = _entorno_mysql(conexion)

    try:
        resultado = subprocess.run(
            comando,
            check=False,
            capture_output=True,
            text=True,
            env=entorno,
        )
    except OSError as error:
        raise BackupError(f"No se pudo ejecutar mysqlbinlog: {error}") from error

    if resultado.returncode != 0:
        mensaje = (resultado.stderr or resultado.stdout or "Error desconocido.").strip()
        raise BackupError(f"mysqlbinlog termino con error: {mensaje}")

    if not archivo_salida.exists():
        raise BackupError(
            "El backup incremental se ejecuto pero no se encontro el archivo de salida."
        )

    return {
        "archivo": archivo_salida,
        "tipo": "INCREMENTAL",
        "binlog_archivo_inicio": archivo_inicio,
        "binlog_posicion_inicio": int(posicion_inicio),
        "binlog_archivo_fin": archivo_fin,
        "binlog_posicion_fin": int(posicion_fin),
    }
