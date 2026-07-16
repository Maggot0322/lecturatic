# -*- coding: utf-8 -*-
"""
app.py
------------------------------------------------------------
Aplicación principal de LECTURATIC — Entorno Virtual de
Aprendizaje para fortalecer la comprensión lectora en
estudiantes de quinto grado de básica primaria.

Ejecutar con:  python app.py
------------------------------------------------------------
"""

import os
import io
import json
import time
from functools import wraps
from datetime import datetime

from flask import (Flask, render_template, request, redirect, url_for,
                    session, flash, jsonify, send_file, abort)
from werkzeug.security import generate_password_hash, check_password_hash

from database import (get_db, inicializar_todo, registrar_log, cargar_json_modulos,
                       hacer_backup, restaurar_backup, BACKUP_DIR, DB_PATH)
from logica import (calificar_actividad, guardar_intento, actualizar_progreso_modulo,
                     actualizar_gamificacion, generar_recomendacion, calcular_promedio_general,
                     retroalimentacion_personalizada, NOTA_MINIMA_APROBACION)
from reportes import generar_csv, generar_excel, generar_pdf, generar_certificado_pdf

app = Flask(__name__)
app.secret_key = "lecturatic_clave_secreta_investigacion_maestria_2026"  # cambiar en producción

# Inicializar la base de datos automáticamente la primera vez que se ejecuta la app
if not os.path.exists(DB_PATH):
    inicializar_todo(force=False)
else:
    inicializar_todo(force=False)  # sincroniza módulos/actividades sin borrar datos existentes


# =========================================================
# DECORADORES DE PROTECCIÓN DE RUTAS (control de sesiones)
# =========================================================

def login_requerido(f):
    """Exige que el usuario haya iniciado sesión."""
    @wraps(f)
    def decorado(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorado


def admin_requerido(f):
    """Exige que el usuario tenga rol de administrador."""
    @wraps(f)
    def decorado(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        if session.get("rol") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorado


def estudiante_requerido(f):
    """Exige que el usuario tenga rol de estudiante."""
    @wraps(f)
    def decorado(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        if session.get("rol") != "estudiante":
            abort(403)
        return f(*args, **kwargs)
    return decorado


# =========================================================
# AUTENTICACIÓN
# =========================================================

@app.route("/", methods=["GET"])
def index():
    if "usuario_id" in session:
        if session.get("rol") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("estudiante_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        fila = conn.execute("SELECT * FROM usuarios WHERE usuario = ? AND activo = 1",
                             (usuario,)).fetchone()
        conn.close()

        if fila and check_password_hash(fila["password_hash"], password):
            session["usuario_id"] = fila["id"]
            session["usuario"] = fila["usuario"]
            session["nombre_completo"] = fila["nombre_completo"]
            session["rol"] = fila["rol"]
            session["avatar"] = fila["avatar"]

            conn = get_db()
            conn.execute("UPDATE usuarios SET ultimo_acceso = ? WHERE id = ?",
                         (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), fila["id"]))
            conn.commit()
            conn.close()

            registrar_log(fila["id"], "inicio_sesion", f"Usuario {usuario} inició sesión")

            if fila["rol"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("estudiante_dashboard"))
        else:
            flash("Usuario o contraseña incorrectos. Inténtalo de nuevo.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    if "usuario_id" in session:
        registrar_log(session["usuario_id"], "cierre_sesion", "El usuario cerró sesión")
    session.clear()
    return redirect(url_for("login"))


# =========================================================
# ÁREA DEL ESTUDIANTE
# =========================================================

@app.route("/estudiante/dashboard")
@estudiante_requerido
def estudiante_dashboard():
    uid = session["usuario_id"]
    conn = get_db()
    modulos_db = conn.execute("SELECT * FROM modulos ORDER BY orden").fetchall()
    progreso_db = conn.execute("SELECT * FROM progreso WHERE usuario_id = ?", (uid,)).fetchall()
    progreso_map = {p["modulo_id"]: p for p in progreso_db}

    gam = conn.execute("SELECT * FROM gamificacion WHERE usuario_id = ?", (uid,)).fetchone()

    pretest = conn.execute("SELECT * FROM pretest_postest WHERE usuario_id = ? AND tipo='pretest'",
                            (uid,)).fetchone()
    postest = conn.execute("SELECT * FROM pretest_postest WHERE usuario_id = ? AND tipo='postest'",
                            (uid,)).fetchone()
    conn.close()

    total_modulos = len(modulos_db)
    modulos_aprobados = sum(1 for p in progreso_db if p["aprobado"] == 1)
    porcentaje_general = round((modulos_aprobados / total_modulos) * 100, 1) if total_modulos else 0
    promedio = calcular_promedio_general(uid)

    todos_aprobados = modulos_aprobados == total_modulos and total_modulos > 0

    modulos = []
    for m in modulos_db:
        p = progreso_map.get(m["id"])
        modulos.append({
            "id": m["id"], "orden": m["orden"], "titulo": m["titulo"], "nivel": m["nivel"],
            "descripcion": m["descripcion"],
            "desbloqueado": p["desbloqueado"] if p else 0,
            "aprobado": p["aprobado"] if p else 0,
            "mejor_nota": p["mejor_nota"] if p else 0,
            "porcentaje_avance": p["porcentaje_avance"] if p else 0,
            "estado": p["estado"] if p else "bloqueado",
        })

    insignias = json.loads(gam["insignias"]) if gam else []

    return render_template("student/dashboard.html",
                            modulos=modulos, porcentaje_general=porcentaje_general,
                            modulos_aprobados=modulos_aprobados, total_modulos=total_modulos,
                            promedio=promedio, gam=gam, insignias=insignias,
                            pretest=pretest, postest=postest, todos_aprobados=todos_aprobados)


@app.route("/estudiante/pretest", methods=["GET", "POST"])
@estudiante_requerido
def pretest():
    return _prueba_diagnostica("pretest")


@app.route("/estudiante/postest", methods=["GET", "POST"])
@estudiante_requerido
def postest():
    return _prueba_diagnostica("postest")


def _prueba_diagnostica(tipo):
    """Lógica compartida para el pretest y el postest."""
    data = cargar_json_modulos()
    prueba = data[tipo]

    if request.method == "POST":
        uid = session["usuario_id"]
        aciertos = 0
        total = len(prueba["preguntas"])
        for i, p in enumerate(prueba["preguntas"]):
            resp = request.form.get(f"pregunta_{i}")
            if resp is not None and int(resp) == p["correcta"]:
                aciertos += 1
        nota = round(1.0 + (aciertos / total) * 4.0, 1)

        conn = get_db()
        ahora = datetime.now()
        conn.execute("""
            INSERT INTO pretest_postest (usuario_id, tipo, aciertos, total_preguntas, nota, fecha, hora)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (uid, tipo, aciertos, total, nota, ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S")))
        conn.commit()
        conn.close()

        registrar_log(uid, f"{tipo}_completado", f"Nota obtenida: {nota}")
        flash(f"¡Prueba enviada! Obtuviste {aciertos} de {total} respuestas correctas (nota {nota}).", "success")
        return redirect(url_for("estudiante_dashboard"))

    return render_template("student/prueba_diagnostica.html", prueba=prueba, tipo=tipo)


@app.route("/estudiante/modulo/<int:modulo_id>")
@estudiante_requerido
def ver_modulo(modulo_id):
    uid = session["usuario_id"]
    data = cargar_json_modulos()
    modulo_json = next((m for m in data["modulos"] if m["id"] == modulo_id), None)
    if not modulo_json:
        abort(404)

    conn = get_db()
    progreso = conn.execute("SELECT * FROM progreso WHERE usuario_id = ? AND modulo_id = ?",
                             (uid, modulo_id)).fetchone()
    conn.close()

    if not progreso or progreso["desbloqueado"] == 0:
        flash("Este módulo todavía está bloqueado. ¡Completa los módulos anteriores primero!", "warning")
        return redirect(url_for("estudiante_dashboard"))

    registrar_log(uid, "ver_contenido_modulo", f"Módulo {modulo_id}: {modulo_json['titulo']}")
    return render_template("student/modulo.html", modulo=modulo_json, progreso=progreso)


@app.route("/estudiante/modulo/<int:modulo_id>/actividad/<int:actividad_indice>", methods=["GET", "POST"])
@estudiante_requerido
def ver_actividad(modulo_id, actividad_indice):
    uid = session["usuario_id"]
    data = cargar_json_modulos()
    modulo_json = next((m for m in data["modulos"] if m["id"] == modulo_id), None)
    if not modulo_json or actividad_indice >= len(modulo_json["actividades"]):
        abort(404)

    actividad = modulo_json["actividades"][actividad_indice]
    tipo = actividad["tipo"]

    conn = get_db()
    progreso = conn.execute("SELECT * FROM progreso WHERE usuario_id = ? AND modulo_id = ?",
                             (uid, modulo_id)).fetchone()
    conn.close()
    if not progreso or progreso["desbloqueado"] == 0:
        flash("Este módulo todavía está bloqueado.", "warning")
        return redirect(url_for("estudiante_dashboard"))

    if request.method == "POST":
        tiempo_segundos = int(request.form.get("tiempo_segundos", 0))
        respuestas_usuario = {}

        if tipo in ("opcion_multiple",):
            preguntas = actividad["preguntas"]
            for i in range(len(preguntas)):
                respuestas_usuario[str(i)] = request.form.get(f"pregunta_{i}")
            resultado = calificar_actividad(tipo, preguntas, respuestas_usuario)

        elif tipo == "verdadero_falso":
            preguntas = actividad["preguntas"]
            for i in range(len(preguntas)):
                respuestas_usuario[str(i)] = request.form.get(f"pregunta_{i}")
            resultado = calificar_actividad(tipo, preguntas, respuestas_usuario)

        elif tipo == "completar":
            preguntas = actividad["preguntas"]
            for i in range(len(preguntas)):
                respuestas_usuario[str(i)] = request.form.get(f"pregunta_{i}", "")
            resultado = calificar_actividad(tipo, preguntas, respuestas_usuario)

        elif tipo == "relacionar":
            pares = actividad["pares"]
            for i in range(len(pares)):
                respuestas_usuario[str(i)] = request.form.get(f"par_{i}", "")
            resultado = calificar_actividad(tipo, pares, respuestas_usuario)

        elif tipo == "ordenar":
            secuencia = actividad["secuencia_correcta"]
            for i in range(len(secuencia)):
                respuestas_usuario[str(i)] = request.form.get(f"orden_{i}", "")
            resultado = calificar_actividad(tipo, secuencia, respuestas_usuario)

        elif tipo == "pregunta_abierta":
            preguntas = actividad["preguntas"]
            for i in range(len(preguntas)):
                respuestas_usuario[str(i)] = request.form.get(f"pregunta_{i}", "")
            resultado = calificar_actividad(tipo, preguntas, respuestas_usuario)

        else:
            resultado = {"aciertos": 0, "errores": 0, "total": 0, "nota": 1.0, "detalle": ""}

        numero_intento = guardar_intento(uid, modulo_id, actividad_indice, tipo,
                                          respuestas_usuario, resultado, tiempo_segundos)
        actualizar_gamificacion(uid, resultado["nota"])
        promedio_modulo, aprobado, porcentaje = actualizar_progreso_modulo(uid, modulo_id)

        registrar_log(uid, "actividad_completada",
                      f"Módulo {modulo_id}, actividad {actividad_indice}, nota {resultado['nota']}")

        mensaje = retroalimentacion_personalizada(resultado["nota"], modulo_json["nivel"])
        recomendacion = generar_recomendacion(uid, modulo_id)

        return render_template("student/resultado_actividad.html",
                                modulo=modulo_json, actividad=actividad, resultado=resultado,
                                numero_intento=numero_intento, mensaje=mensaje,
                                recomendacion=recomendacion, promedio_modulo=promedio_modulo,
                                aprobado=aprobado, tiempo_segundos=tiempo_segundos)

    return render_template("student/actividad.html", modulo=modulo_json, actividad=actividad,
                            actividad_indice=actividad_indice, tipo=tipo)


@app.route("/estudiante/certificado")
@estudiante_requerido
def certificado():
    uid = session["usuario_id"]
    conn = get_db()
    total_modulos = conn.execute("SELECT COUNT(*) as n FROM modulos").fetchone()["n"]
    aprobados = conn.execute("SELECT COUNT(*) as n FROM progreso WHERE usuario_id = ? AND aprobado = 1",
                              (uid,)).fetchone()["n"]
    conn.close()

    if aprobados < total_modulos:
        flash("Debes aprobar todos los módulos para obtener tu certificado.", "warning")
        return redirect(url_for("estudiante_dashboard"))

    promedio = calcular_promedio_general(uid)
    pdf_bytes = generar_certificado_pdf(session["nombre_completo"], promedio)
    registrar_log(uid, "certificado_generado", f"Promedio: {promedio}")

    return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                      as_attachment=True,
                      download_name=f"Certificado_LECTURATIC_{session['usuario']}.pdf")


# =========================================================
# ACCESIBILIDAD (guardar preferencias simples en sesión)
# =========================================================

@app.route("/api/accesibilidad", methods=["POST"])
@login_requerido
def guardar_accesibilidad():
    datos = request.get_json(silent=True) or {}
    session["pref_fuente"] = datos.get("fuente", "normal")
    session["pref_tema"] = datos.get("tema", "claro")
    session["pref_contraste"] = datos.get("contraste", "normal")
    return jsonify({"ok": True})


# =========================================================
# PANEL DEL ADMINISTRADOR
# =========================================================

@app.route("/admin/dashboard")
@admin_requerido
def admin_dashboard():
    conn = get_db()
    total_estudiantes = conn.execute("SELECT COUNT(*) as n FROM usuarios WHERE rol='estudiante'").fetchone()["n"]
    total_intentos = conn.execute("SELECT COUNT(*) as n FROM intentos").fetchone()["n"]
    promedio_general = conn.execute("SELECT AVG(nota) as p FROM intentos").fetchone()["p"] or 0
    ingresos_hoy = conn.execute("""
        SELECT COUNT(*) as n FROM logs WHERE accion='inicio_sesion' AND fecha = ?
    """, (datetime.now().strftime("%Y-%m-%d"),)).fetchone()["n"]

    estudiantes_activos = conn.execute("""
        SELECT COUNT(DISTINCT usuario_id) as n FROM logs
        WHERE fecha >= date('now', '-7 day')
    """).fetchone()["n"]

    ultimos_logs = conn.execute("""
        SELECT logs.*, usuarios.nombre_completo FROM logs
        LEFT JOIN usuarios ON usuarios.id = logs.usuario_id
        ORDER BY logs.id DESC LIMIT 15
    """).fetchall()
    conn.close()

    return render_template("admin/dashboard.html",
                            total_estudiantes=total_estudiantes, total_intentos=total_intentos,
                            promedio_general=round(promedio_general, 1), ingresos_hoy=ingresos_hoy,
                            estudiantes_activos=estudiantes_activos, ultimos_logs=ultimos_logs)


@app.route("/admin/estudiantes")
@admin_requerido
def admin_estudiantes():
    busqueda = request.args.get("q", "").strip()
    conn = get_db()
    query = "SELECT * FROM usuarios WHERE rol='estudiante'"
    params = []
    if busqueda:
        query += " AND (usuario LIKE ? OR nombre_completo LIKE ?)"
        params.extend([f"%{busqueda}%", f"%{busqueda}%"])
    query += " ORDER BY nombre_completo"
    estudiantes = conn.execute(query, params).fetchall()

    resultado = []
    for e in estudiantes:
        promedio = calcular_promedio_general(e["id"])
        aprobados = conn.execute("SELECT COUNT(*) as n FROM progreso WHERE usuario_id=? AND aprobado=1",
                                  (e["id"],)).fetchone()["n"]
        total_modulos = conn.execute("SELECT COUNT(*) as n FROM modulos").fetchone()["n"]
        porcentaje = round((aprobados / total_modulos) * 100, 1) if total_modulos else 0
        resultado.append({"usuario": e, "promedio": promedio, "aprobados": aprobados,
                           "total_modulos": total_modulos, "porcentaje": porcentaje})
    conn.close()

    return render_template("admin/estudiantes.html", estudiantes=resultado, busqueda=busqueda)


@app.route("/admin/estudiantes/crear", methods=["POST"])
@admin_requerido
def admin_crear_estudiante():
    usuario = request.form.get("usuario", "").strip()
    nombre = request.form.get("nombre_completo", "").strip()
    password = request.form.get("password", "").strip()

    if not usuario or not nombre or not password:
        flash("Todos los campos son obligatorios.", "danger")
        return redirect(url_for("admin_estudiantes"))

    conn = get_db()
    existente = conn.execute("SELECT id FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
    if existente:
        flash("Ese nombre de usuario ya existe.", "danger")
        conn.close()
        return redirect(url_for("admin_estudiantes"))

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("""
        INSERT INTO usuarios (usuario, nombre_completo, password_hash, rol, fecha_creacion)
        VALUES (?, ?, ?, 'estudiante', ?)
    """, (usuario, nombre, generate_password_hash(password), ahora))
    nuevo_id = cur.lastrowid
    conn.execute("INSERT OR IGNORE INTO gamificacion (usuario_id) VALUES (?)", (nuevo_id,))

    modulos = conn.execute("SELECT * FROM modulos ORDER BY orden").fetchall()
    for m in modulos:
        desbloqueado = 1 if m["orden"] == 1 else 0
        estado = "disponible" if m["orden"] == 1 else "bloqueado"
        conn.execute("""
            INSERT INTO progreso (usuario_id, modulo_id, desbloqueado, estado)
            VALUES (?, ?, ?, ?)
        """, (nuevo_id, m["id"], desbloqueado, estado))

    conn.commit()
    conn.close()
    registrar_log(session["usuario_id"], "crear_estudiante", f"Se creó el usuario {usuario}")
    flash(f"Estudiante '{nombre}' creado correctamente.", "success")
    return redirect(url_for("admin_estudiantes"))


@app.route("/admin/estudiantes/<int:usuario_id>/editar", methods=["POST"])
@admin_requerido
def admin_editar_estudiante(usuario_id):
    nombre = request.form.get("nombre_completo", "").strip()
    conn = get_db()
    conn.execute("UPDATE usuarios SET nombre_completo = ? WHERE id = ?", (nombre, usuario_id))
    conn.commit()
    conn.close()
    registrar_log(session["usuario_id"], "editar_estudiante", f"Editado usuario id {usuario_id}")
    flash("Datos del estudiante actualizados.", "success")
    return redirect(url_for("admin_estudiantes"))


@app.route("/admin/estudiantes/<int:usuario_id>/resetear-clave", methods=["POST"])
@admin_requerido
def admin_resetear_clave(usuario_id):
    nueva_clave = request.form.get("nueva_clave", "12345").strip()
    conn = get_db()
    conn.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?",
                 (generate_password_hash(nueva_clave), usuario_id))
    conn.commit()
    conn.close()
    registrar_log(session["usuario_id"], "resetear_clave", f"Clave reiniciada para usuario id {usuario_id}")
    flash("Contraseña restablecida correctamente.", "success")
    return redirect(url_for("admin_estudiantes"))


@app.route("/admin/estudiantes/<int:usuario_id>/eliminar", methods=["POST"])
@admin_requerido
def admin_eliminar_estudiante(usuario_id):
    conn = get_db()
    conn.execute("UPDATE usuarios SET activo = 0 WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()
    registrar_log(session["usuario_id"], "eliminar_estudiante", f"Usuario id {usuario_id} desactivado")
    flash("Estudiante eliminado (desactivado) correctamente.", "success")
    return redirect(url_for("admin_estudiantes"))


@app.route("/admin/estudiantes/<int:usuario_id>/detalle")
@admin_requerido
def admin_detalle_estudiante(usuario_id):
    conn = get_db()
    estudiante = conn.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    if not estudiante:
        abort(404)

    progreso = conn.execute("""
        SELECT progreso.*, modulos.titulo, modulos.nivel, modulos.orden FROM progreso
        JOIN modulos ON modulos.id = progreso.modulo_id
        WHERE progreso.usuario_id = ? ORDER BY modulos.orden
    """, (usuario_id,)).fetchall()

    intentos = conn.execute("""
        SELECT intentos.*, modulos.titulo as modulo_titulo FROM intentos
        JOIN modulos ON modulos.id = intentos.modulo_id
        WHERE intentos.usuario_id = ? ORDER BY intentos.id DESC
    """, (usuario_id,)).fetchall()

    pretest = conn.execute("SELECT * FROM pretest_postest WHERE usuario_id=? AND tipo='pretest'",
                            (usuario_id,)).fetchone()
    postest = conn.execute("SELECT * FROM pretest_postest WHERE usuario_id=? AND tipo='postest'",
                            (usuario_id,)).fetchone()
    conn.close()

    promedio = calcular_promedio_general(usuario_id)
    return render_template("admin/detalle_estudiante.html", estudiante=estudiante,
                            progreso=progreso, intentos=intentos, promedio=promedio,
                            pretest=pretest, postest=postest)


@app.route("/admin/estadisticas")
@admin_requerido
def admin_estadisticas():
    conn = get_db()

    por_modulo = conn.execute("""
        SELECT modulos.titulo, AVG(intentos.nota) as promedio, COUNT(intentos.id) as cantidad
        FROM intentos JOIN modulos ON modulos.id = intentos.modulo_id
        GROUP BY modulos.id ORDER BY modulos.orden
    """).fetchall()

    tiempo_promedio = conn.execute("SELECT AVG(tiempo_segundos) as t FROM intentos").fetchone()["t"] or 0

    actividades_por_estudiante = conn.execute("""
        SELECT usuarios.nombre_completo, COUNT(intentos.id) as cantidad
        FROM intentos JOIN usuarios ON usuarios.id = intentos.usuario_id
        GROUP BY usuarios.id ORDER BY cantidad DESC
    """).fetchall()

    total_estudiantes = conn.execute("SELECT COUNT(*) as n FROM usuarios WHERE rol='estudiante'").fetchone()["n"]
    activos = conn.execute("""
        SELECT COUNT(DISTINCT usuario_id) as n FROM logs WHERE fecha >= date('now', '-7 day')
    """).fetchone()["n"]
    inactivos = max(total_estudiantes - activos, 0)

    niveles = conn.execute("""
        SELECT modulos.nivel, AVG(intentos.nota) as promedio
        FROM intentos JOIN modulos ON modulos.id = intentos.modulo_id
        GROUP BY modulos.nivel
    """).fetchall()

    conn.close()

    return render_template("admin/estadisticas.html",
                            por_modulo=[dict(r) for r in por_modulo],
                            tiempo_promedio=round(tiempo_promedio, 1),
                            actividades_por_estudiante=[dict(r) for r in actividades_por_estudiante],
                            activos=activos, inactivos=inactivos, niveles=[dict(r) for r in niveles])


@app.route("/admin/reportes")
@admin_requerido
def admin_reportes():
    return render_template("admin/reportes.html")


def _filas_reporte(fecha_inicio=None, fecha_fin=None, modulo_id=None):
    conn = get_db()
    estudiantes = conn.execute("SELECT * FROM usuarios WHERE rol='estudiante' AND activo=1").fetchall()
    filas = []
    for e in estudiantes:
        query = "SELECT COUNT(*) as n FROM intentos WHERE usuario_id = ?"
        params = [e["id"]]
        if fecha_inicio:
            query += " AND fecha >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND fecha <= ?"
            params.append(fecha_fin)
        if modulo_id:
            query += " AND modulo_id = ?"
            params.append(modulo_id)
        tiene_intentos = conn.execute(query, params).fetchone()["n"]
        if fecha_inicio or fecha_fin or modulo_id:
            if tiene_intentos == 0:
                continue

        promedio = calcular_promedio_general(e["id"])
        aprobados = conn.execute("SELECT COUNT(*) as n FROM progreso WHERE usuario_id=? AND aprobado=1",
                                  (e["id"],)).fetchone()["n"]
        total_modulos = conn.execute("SELECT COUNT(*) as n FROM modulos").fetchone()["n"]
        porcentaje = round((aprobados / total_modulos) * 100, 1) if total_modulos else 0
        ultimo = e["ultimo_acceso"] or "Sin ingresos"
        filas.append([e["nombre_completo"], e["usuario"], promedio, aprobados, f"{porcentaje}%", ultimo])
    conn.close()
    return filas


@app.route("/admin/reportes/descargar/<formato>")
@admin_requerido
def admin_descargar_reporte(formato):
    fecha_inicio = request.args.get("fecha_inicio") or None
    fecha_fin = request.args.get("fecha_fin") or None
    modulo_id = request.args.get("modulo_id") or None

    filas = _filas_reporte(fecha_inicio, fecha_fin, modulo_id)
    registrar_log(session["usuario_id"], "descarga_reporte", f"Formato: {formato}")

    if formato == "csv":
        contenido = generar_csv(filas)
        return send_file(io.BytesIO(contenido), mimetype="text/csv", as_attachment=True,
                          download_name="reporte_lecturatic.csv")
    elif formato == "excel":
        contenido = generar_excel(filas)
        return send_file(io.BytesIO(contenido),
                          mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          as_attachment=True, download_name="reporte_lecturatic.xlsx")
    elif formato == "pdf":
        contenido = generar_pdf(filas)
        return send_file(io.BytesIO(contenido), mimetype="application/pdf", as_attachment=True,
                          download_name="reporte_lecturatic.pdf")
    else:
        abort(400)


@app.route("/admin/respaldo/crear", methods=["POST"])
@admin_requerido
def admin_crear_respaldo():
    ruta = hacer_backup()
    registrar_log(session["usuario_id"], "respaldo_creado", ruta)
    flash(f"Respaldo creado correctamente: {os.path.basename(ruta)}", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/respaldo/lista")
@admin_requerido
def admin_lista_respaldos():
    archivos = []
    if os.path.exists(BACKUP_DIR):
        archivos = sorted(os.listdir(BACKUP_DIR), reverse=True)
    return render_template("admin/respaldos.html", archivos=archivos)


@app.route("/admin/respaldo/restaurar/<nombre_archivo>", methods=["POST"])
@admin_requerido
def admin_restaurar_respaldo(nombre_archivo):
    ok = restaurar_backup(nombre_archivo)
    if ok:
        registrar_log(session["usuario_id"], "respaldo_restaurado", nombre_archivo)
        flash("Base de datos restaurada correctamente.", "success")
    else:
        flash("No se pudo restaurar el respaldo indicado.", "danger")
    return redirect(url_for("admin_lista_respaldos"))


# =========================================================
# MANEJO DE ERRORES
# =========================================================

@app.errorhandler(403)
def prohibido(e):
    return render_template("error.html", codigo=403,
                            mensaje="No tienes permiso para acceder a esta página."), 403


@app.errorhandler(404)
def no_encontrado(e):
    return render_template("error.html", codigo=404, mensaje="Página no encontrada."), 404


# =========================================================
# PUNTO DE ENTRADA
# =========================================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
