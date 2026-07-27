# -*- coding: utf-8 -*-
"""
database.py
------------------------------------------------------------
Módulo encargado de la creación, conexión y administración
de la base de datos SQLite de la plataforma LECTURATIC.

Contiene:
    - Función para obtener una conexión a la base de datos.
    - Función para inicializar (crear) todas las tablas.
    - Función para insertar los usuarios iniciales (seed).
    - Función para cargar el contenido de los módulos desde
      data/modules.json e insertarlos en la base de datos.
    - Funciones de respaldo (backup) y restauración.
------------------------------------------------------------
"""

import sqlite3
import json
import os
import shutil
from datetime import datetime
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lecturatic.db")
MODULES_JSON_PATH = os.path.join(BASE_DIR, "data", "modules.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")


def get_db():
    """
    Retorna una conexión a la base de datos SQLite con
    row_factory configurado para devolver filas tipo diccionario
    (más fáciles de usar en las plantillas Jinja2).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(force=False):
    """
    Crea todas las tablas necesarias para la plataforma si no
    existen todavía. Si force=True, elimina la base de datos
    existente y la vuelve a crear desde cero (útil para reiniciar
    el entorno de pruebas de la investigación).
    """
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = get_db()
    cur = conn.cursor()

    # Tabla de usuarios (administrador y estudiantes)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            nombre_completo TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL CHECK(rol IN ('admin', 'estudiante')),
            avatar TEXT DEFAULT 'avatar1.png',
            fecha_creacion TEXT NOT NULL,
            ultimo_acceso TEXT,
            activo INTEGER DEFAULT 1
        )
    """)

    # Tabla de módulos (se sincroniza con data/modules.json)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS modulos (
            id INTEGER PRIMARY KEY,
            orden INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            nivel TEXT,
            descripcion TEXT,
            nota_minima REAL DEFAULT 3.5
        )
    """)

    # Tabla de actividades (2 por módulo, calificables)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS actividades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            modulo_id INTEGER NOT NULL,
            indice INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            FOREIGN KEY (modulo_id) REFERENCES modulos(id)
        )
    """)

    # Tabla de intentos de actividades (guarda cada intento del estudiante)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS intentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            modulo_id INTEGER NOT NULL,
            actividad_indice INTEGER NOT NULL,
            tipo_actividad TEXT,
            respuestas TEXT,
            aciertos INTEGER DEFAULT 0,
            errores INTEGER DEFAULT 0,
            total_preguntas INTEGER DEFAULT 0,
            nota REAL DEFAULT 0,
            tiempo_segundos INTEGER DEFAULT 0,
            numero_intento INTEGER DEFAULT 1,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY (modulo_id) REFERENCES modulos(id)
        )
    """)

    # Tabla de progreso por estudiante y módulo
    cur.execute("""
        CREATE TABLE IF NOT EXISTS progreso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            modulo_id INTEGER NOT NULL,
            desbloqueado INTEGER DEFAULT 0,
            aprobado INTEGER DEFAULT 0,
            mejor_nota REAL DEFAULT 0,
            porcentaje_avance REAL DEFAULT 0,
            tiempo_total_segundos INTEGER DEFAULT 0,
            estado TEXT DEFAULT 'bloqueado',
            UNIQUE(usuario_id, modulo_id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY (modulo_id) REFERENCES modulos(id)
        )
    """)

    # Tabla de pretest / postest
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pretest_postest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('pretest','postest')),
            aciertos INTEGER,
            total_preguntas INTEGER,
            nota REAL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)

    # Tabla de gamificación (puntos, insignias, nivel)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gamificacion (
            usuario_id INTEGER PRIMARY KEY,
            puntos INTEGER DEFAULT 0,
            experiencia INTEGER DEFAULT 0,
            nivel INTEGER DEFAULT 1,
            insignias TEXT DEFAULT '[]',
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)

    # Tabla de logs / bitácora de actividad (para evidenciar uso en la investigación)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            accion TEXT NOT NULL,
            detalle TEXT,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def registrar_log(usuario_id, accion, detalle=""):
    """Inserta un registro en la bitácora de actividad (logs)."""
    conn = get_db()
    ahora = datetime.now()
    conn.execute(
        "INSERT INTO logs (usuario_id, accion, detalle, fecha, hora) VALUES (?, ?, ?, ?, ?)",
        (usuario_id, accion, detalle, ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S"))
    )
    conn.commit()
    conn.close()


def seed_usuarios():
    """
    Inserta el administrador y los cinco estudiantes iniciales
    definidos en los requisitos del proyecto, solo si aún no existen.
    """
    conn = get_db()
    cur = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    usuarios_iniciales = [
        ("admin", "Administrador General", "admin123", "admin"),
        ("estudiante1", "Estudiante Uno", "12345", "estudiante"),
    ]

    for usuario, nombre, password, rol in usuarios_iniciales:
        cur.execute("SELECT id FROM usuarios WHERE usuario = ?", (usuario,))
        if cur.fetchone() is None:
            cur.execute("""
                INSERT INTO usuarios (usuario, nombre_completo, password_hash, rol, fecha_creacion)
                VALUES (?, ?, ?, ?, ?)
            """, (usuario, nombre, generate_password_hash(password), rol, ahora))
            nuevo_id = cur.lastrowid
            cur.execute("INSERT OR IGNORE INTO gamificacion (usuario_id) VALUES (?)", (nuevo_id,))

    conn.commit()
    conn.close()


def seed_modulos_y_actividades():
    """
    Lee data/modules.json y sincroniza los módulos y actividades
    en la base de datos. También crea/actualiza los registros de
    progreso (bloqueado/desbloqueado) para cada estudiante.
    El primer módulo siempre queda desbloqueado por defecto.
    """
    with open(MODULES_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    conn = get_db()
    cur = conn.cursor()

    for modulo in data["modulos"]:
        cur.execute("""
            INSERT INTO modulos (id, orden, titulo, nivel, descripcion, nota_minima)
            VALUES (?, ?, ?, ?, ?, 3.5)
            ON CONFLICT(id) DO UPDATE SET
                orden=excluded.orden, titulo=excluded.titulo,
                nivel=excluded.nivel, descripcion=excluded.descripcion
        """, (modulo["id"], modulo["orden"], modulo["titulo"], modulo["nivel"], modulo["descripcion"]))

        cur.execute("DELETE FROM actividades WHERE modulo_id = ?", (modulo["id"],))
        for idx, act in enumerate(modulo["actividades"]):
            cur.execute("""
                INSERT INTO actividades (modulo_id, indice, tipo, titulo)
                VALUES (?, ?, ?, ?)
            """, (modulo["id"], idx, act["tipo"], act["titulo"]))

    # Crear registros de progreso para cada estudiante existente
    cur.execute("SELECT id FROM usuarios WHERE rol = 'estudiante'")
    estudiantes = cur.fetchall()
    for est in estudiantes:
        for modulo in data["modulos"]:
            cur.execute("SELECT id FROM progreso WHERE usuario_id = ? AND modulo_id = ?",
                        (est["id"], modulo["id"]))
            if cur.fetchone() is None:
                desbloqueado = 1 if modulo["orden"] == 1 else 0
                estado = "disponible" if modulo["orden"] == 1 else "bloqueado"
                cur.execute("""
                    INSERT INTO progreso (usuario_id, modulo_id, desbloqueado, estado)
                    VALUES (?, ?, ?, ?)
                """, (est["id"], modulo["id"], desbloqueado, estado))

    conn.commit()
    conn.close()


def cargar_json_modulos():
    """Retorna el contenido completo de data/modules.json como diccionario."""
    with open(MODULES_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def hacer_backup():
    """
    Copia el archivo de la base de datos actual a la carpeta backups/
    con una marca de tiempo, para preservar la información de la
    investigación ante cualquier eventualidad.
    """
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(BACKUP_DIR, f"lecturatic_backup_{marca}.db")
    shutil.copy2(DB_PATH, destino)
    return destino


def restaurar_backup(nombre_archivo):
    """
    Restaura la base de datos a partir de un archivo de respaldo
    ubicado en la carpeta backups/.
    """
    origen = os.path.join(BACKUP_DIR, nombre_archivo)
    if os.path.exists(origen):
        shutil.copy2(origen, DB_PATH)
        return True
    return False


def inicializar_todo(force=False):
    """Punto de entrada único: crea tablas y siembra datos iniciales."""
    init_db(force=force)
    seed_usuarios()
    seed_modulos_y_actividades()


if __name__ == "__main__":
    # Permite ejecutar `python database.py` para inicializar la BD manualmente.
    inicializar_todo(force=False)
    print("Base de datos inicializada correctamente en:", DB_PATH)
