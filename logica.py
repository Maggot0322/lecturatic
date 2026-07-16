# -*- coding: utf-8 -*-
"""
logica.py
------------------------------------------------------------
Contiene la lógica de negocio de la plataforma:
    - Calificación automática de actividades (escala 1.0 - 5.0).
    - Actualización de progreso y desbloqueo de módulos.
    - Sistema de gamificación (puntos, experiencia, nivel, insignias).
    - Recomendaciones automáticas según los errores del estudiante.
------------------------------------------------------------
"""

import json
from datetime import datetime
from database import get_db, registrar_log, cargar_json_modulos

NOTA_MINIMA_APROBACION = 3.5


def calificar_actividad(tipo, preguntas_json, respuestas_usuario):
    """
    Compara las respuestas del estudiante contra las respuestas
    correctas definidas en modules.json y calcula:
        aciertos, errores, total, nota (escala 1.0 a 5.0)

    Las actividades de tipo 'pregunta_abierta' no se califican
    automáticamente: se marcan como entregadas, con nota informativa 5.0
    (evaluación cualitativa queda a criterio docente).
    """
    if tipo == "pregunta_abierta":
        total = len(preguntas_json)
        return {
            "aciertos": total,
            "errores": 0,
            "total": total,
            "nota": 5.0,
            "detalle": "Actividad de respuesta abierta. Revisión cualitativa por el docente."
        }

    aciertos = 0
    total = 0

    if tipo == "opcion_multiple":
        total = len(preguntas_json)
        for i, p in enumerate(preguntas_json):
            resp = respuestas_usuario.get(str(i))
            if resp is not None and int(resp) == p["correcta"]:
                aciertos += 1

    elif tipo == "verdadero_falso":
        total = len(preguntas_json)
        for i, p in enumerate(preguntas_json):
            resp = respuestas_usuario.get(str(i))
            correcta_str = "true" if p["correcta"] else "false"
            if resp is not None and str(resp).lower() == correcta_str:
                aciertos += 1

    elif tipo == "completar":
        total = len(preguntas_json)
        for i, p in enumerate(preguntas_json):
            resp = respuestas_usuario.get(str(i), "")
            if resp.strip().lower() == p["respuesta"].strip().lower():
                aciertos += 1

    elif tipo == "relacionar":
        total = len(preguntas_json)
        for i, par in enumerate(preguntas_json):
            resp = respuestas_usuario.get(str(i), "")
            if resp.strip().lower() == par["derecha"].strip().lower():
                aciertos += 1

    elif tipo == "ordenar":
        secuencia_correcta = preguntas_json  # lista de strings en orden correcto
        total = len(secuencia_correcta)
        for i, item in enumerate(secuencia_correcta):
            resp = respuestas_usuario.get(str(i), "")
            if resp.strip() == item.strip():
                aciertos += 1

    else:
        total = len(preguntas_json) if isinstance(preguntas_json, list) else 1

    errores = total - aciertos
    # Escala colombiana 1.0 a 5.0
    if total == 0:
        nota = 1.0
    else:
        nota = round(1.0 + (aciertos / total) * 4.0, 1)

    return {"aciertos": aciertos, "errores": errores, "total": total, "nota": nota, "detalle": ""}


def retroalimentacion_personalizada(nota, nivel_texto):
    """Genera un mensaje de retroalimentación según la nota obtenida."""
    if nota >= 4.5:
        return f"¡Excelente trabajo! Dominas muy bien el nivel de {nivel_texto}."
    elif nota >= 3.5:
        return f"¡Buen trabajo! Aprobaste el nivel de {nivel_texto}. Sigue practicando para mejorar aún más."
    elif nota >= 2.5:
        return f"Vas por buen camino, pero necesitas repasar un poco más el nivel de {nivel_texto}. ¡Tú puedes!"
    else:
        return f"No te desanimes. Te recomendamos leer el contenido nuevamente y volver a intentarlo en el nivel de {nivel_texto}."


def guardar_intento(usuario_id, modulo_id, actividad_indice, tipo_actividad,
                     respuestas_usuario, resultado, tiempo_segundos):
    """Guarda un intento de actividad en la base de datos."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) as n FROM intentos
        WHERE usuario_id = ? AND modulo_id = ? AND actividad_indice = ?
    """, (usuario_id, modulo_id, actividad_indice))
    numero_intento = cur.fetchone()["n"] + 1

    ahora = datetime.now()
    cur.execute("""
        INSERT INTO intentos (usuario_id, modulo_id, actividad_indice, tipo_actividad,
                               respuestas, aciertos, errores, total_preguntas, nota,
                               tiempo_segundos, numero_intento, fecha, hora)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (usuario_id, modulo_id, actividad_indice, tipo_actividad,
          json.dumps(respuestas_usuario, ensure_ascii=False),
          resultado["aciertos"], resultado["errores"], resultado["total"], resultado["nota"],
          tiempo_segundos, numero_intento, ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S")))

    conn.commit()
    conn.close()
    return numero_intento


def actualizar_progreso_modulo(usuario_id, modulo_id):
    """
    Recalcula el progreso del módulo para un estudiante:
    - mejor nota obtenida (promedio de las 2 actividades, mejor intento de cada una)
    - si aprueba (nota >= 3.5), desbloquea el siguiente módulo
    - actualiza tiempo total invertido
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT indice FROM actividades WHERE modulo_id = ? ORDER BY indice", (modulo_id,))
    indices_actividades = [r["indice"] for r in cur.fetchall()]

    mejores_notas = []
    tiempo_total = 0
    for idx in indices_actividades:
        cur.execute("""
            SELECT nota, tiempo_segundos FROM intentos
            WHERE usuario_id = ? AND modulo_id = ? AND actividad_indice = ?
            ORDER BY nota DESC LIMIT 1
        """, (usuario_id, modulo_id, idx))
        row = cur.fetchone()
        if row:
            mejores_notas.append(row["nota"])
        cur.execute("""
            SELECT SUM(tiempo_segundos) as total FROM intentos
            WHERE usuario_id = ? AND modulo_id = ? AND actividad_indice = ?
        """, (usuario_id, modulo_id, idx))
        t = cur.fetchone()["total"]
        tiempo_total += t or 0

    if mejores_notas:
        promedio_modulo = round(sum(mejores_notas) / len(mejores_notas), 1)
    else:
        promedio_modulo = 0

    total_actividades = len(indices_actividades)
    actividades_completadas = len(mejores_notas)
    porcentaje = round((actividades_completadas / total_actividades) * 100, 1) if total_actividades else 0

    aprobado = 1 if promedio_modulo >= NOTA_MINIMA_APROBACION and actividades_completadas == total_actividades else 0
    estado = "aprobado" if aprobado else ("en progreso" if actividades_completadas > 0 else "disponible")

    cur.execute("""
        UPDATE progreso SET mejor_nota = ?, porcentaje_avance = ?,
               tiempo_total_segundos = tiempo_total_segundos + ?, aprobado = ?, estado = ?
        WHERE usuario_id = ? AND modulo_id = ?
    """, (promedio_modulo, porcentaje, tiempo_total, aprobado, estado, usuario_id, modulo_id))

    # Desbloquear el siguiente módulo si se aprobó este
    if aprobado:
        cur.execute("SELECT orden FROM modulos WHERE id = ?", (modulo_id,))
        orden_actual = cur.fetchone()["orden"]
        cur.execute("SELECT id FROM modulos WHERE orden = ?", (orden_actual + 1,))
        siguiente = cur.fetchone()
        if siguiente:
            cur.execute("""
                UPDATE progreso SET desbloqueado = 1,
                       estado = CASE WHEN estado = 'bloqueado' THEN 'disponible' ELSE estado END
                WHERE usuario_id = ? AND modulo_id = ?
            """, (usuario_id, siguiente["id"]))

    conn.commit()
    conn.close()
    return promedio_modulo, aprobado, porcentaje


def actualizar_gamificacion(usuario_id, nota_obtenida):
    """
    Otorga puntos y experiencia según la nota obtenida en una actividad,
    sube de nivel cada 100 puntos de experiencia y otorga insignias
    por hitos alcanzados.
    """
    conn = get_db()
    cur = conn.cursor()

    puntos_ganados = int(nota_obtenida * 10)  # hasta 50 puntos por actividad perfecta
    cur.execute("SELECT * FROM gamificacion WHERE usuario_id = ?", (usuario_id,))
    g = cur.fetchone()
    if not g:
        cur.execute("INSERT INTO gamificacion (usuario_id) VALUES (?)", (usuario_id,))
        conn.commit()
        cur.execute("SELECT * FROM gamificacion WHERE usuario_id = ?", (usuario_id,))
        g = cur.fetchone()

    nueva_exp = g["experiencia"] + puntos_ganados
    nuevos_puntos = g["puntos"] + puntos_ganados
    nuevo_nivel = 1 + (nueva_exp // 100)

    insignias = json.loads(g["insignias"])
    if nota_obtenida == 5.0 and "Perfeccionista" not in insignias:
        insignias.append("Perfeccionista")
    if nuevo_nivel >= 3 and "Lector Avanzado" not in insignias:
        insignias.append("Lector Avanzado")

    cur.execute("""
        UPDATE gamificacion SET puntos = ?, experiencia = ?, nivel = ?, insignias = ?
        WHERE usuario_id = ?
    """, (nuevos_puntos, nueva_exp, nuevo_nivel, json.dumps(insignias, ensure_ascii=False), usuario_id))

    conn.commit()
    conn.close()


def generar_recomendacion(usuario_id, modulo_id):
    """
    Analiza los intentos recientes del estudiante en un módulo y genera
    una recomendación automática basada en la cantidad de errores.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT AVG(errores) as prom_errores, AVG(nota) as prom_nota FROM intentos
        WHERE usuario_id = ? AND modulo_id = ?
    """, (usuario_id, modulo_id))
    row = cur.fetchone()
    conn.close()

    if not row or row["prom_nota"] is None:
        return "Aún no tienes intentos registrados en este módulo. ¡Comienza cuando quieras!"

    if row["prom_nota"] >= 4.5:
        return "Tu comprensión en este nivel es excelente. Te invitamos a ayudar a un compañero explicándole el tema."
    elif row["prom_nota"] >= 3.5:
        return "Buen desempeño. Te recomendamos repasar el glosario antes de avanzar al siguiente módulo."
    else:
        return "Te recomendamos volver a leer el texto completo, revisar las palabras nuevas y ver el video explicativo antes de intentar de nuevo."


def calcular_promedio_general(usuario_id):
    """Calcula el promedio general del estudiante entre todos los módulos con nota."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT AVG(mejor_nota) as promedio FROM progreso
        WHERE usuario_id = ? AND mejor_nota > 0
    """, (usuario_id,))
    row = cur.fetchone()
    conn.close()
    return round(row["promedio"], 1) if row and row["promedio"] else 0.0
