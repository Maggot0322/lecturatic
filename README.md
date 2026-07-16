# LECTURATIC

**Entorno Virtual de Aprendizaje (EVA) para fortalecer la comprensión lectora en estudiantes de quinto grado de básica primaria.**

Proyecto desarrollado en el marco de una investigación de maestría sobre diseño e implementación de Entornos Virtuales de Aprendizaje.

---

## 1. Tecnologías utilizadas

| Capa | Tecnología |
|---|---|
| Backend | Python 3 + Flask |
| Base de datos | SQLite (archivo `lecturatic.db`, se crea automáticamente) |
| Frontend | HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons |
| Gráficos | Chart.js |
| Reportes | ReportLab (PDF), OpenPyXL (Excel), csv (CSV) |
| Contraseñas | Werkzeug (hash seguro, nunca texto plano) |

---

## 2. Estructura del proyecto

```
lecturatic/
├── app.py                 # Aplicación Flask: todas las rutas
├── database.py             # Creación de tablas y utilidades de BD
├── logica.py                # Calificación automática, progreso, gamificación
├── reportes.py               # Generación de PDF / Excel / CSV / certificados
├── requirements.txt
├── data/
│   └── modules.json          # Contenido y actividades de los 5 módulos (editable sin tocar código)
├── static/
│   ├── css/style.css
│   └── js/ (main.js, accesibilidad.js)
├── templates/
│   ├── base.html, login.html, error.html
│   ├── student/  (dashboard, módulo, actividad, resultado, pretest/postest)
│   └── admin/    (dashboard, estudiantes, detalle, estadísticas, reportes, respaldos)
├── backups/                  # Aquí se guardan los respaldos de la base de datos
└── lecturatic.db             # Se genera automáticamente al iniciar la app
```

---

## 3. Instalación paso a paso

### Requisitos previos
- Tener instalado **Python 3.9 o superior**.

### Paso 1: Descomprimir el proyecto
Descomprime la carpeta `lecturatic` en el computador donde vas a trabajar.

### Paso 2: Abrir una terminal en la carpeta del proyecto
```bash
cd lecturatic
```

### Paso 3: (Recomendado) Crear un entorno virtual
```bash
python -m venv venv

# Activar en Windows:
venv\Scripts\activate

# Activar en Mac/Linux:
source venv/bin/activate
```

### Paso 4: Instalar las dependencias
```bash
pip install -r requirements.txt
```

---

## 4. Cómo iniciar la plataforma

```bash
python app.py
```

Al ejecutarlo por primera vez, la aplicación:
1. Crea automáticamente el archivo `lecturatic.db`.
2. Crea todas las tablas necesarias.
3. Inserta el usuario administrador y los cinco estudiantes de prueba.
4. Carga los 5 módulos y sus actividades desde `data/modules.json`.

Verás un mensaje similar a:
```
* Running on http://0.0.0.0:5000
```

---

## 5. Cómo acceder

Abre tu navegador en: **http://localhost:5000**

### Usuarios de prueba

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador / Docente | `admin` | `admin123` |
| Estudiante 1 | `estudiante1` | `12345` |
| Estudiante 2 | `estudiante2` | `12345` |
| Estudiante 3 | `estudiante3` | `12345` |
| Estudiante 4 | `estudiante4` | `12345` |
| Estudiante 5 | `estudiante5` | `12345` |

> Se recomienda cambiar estas contraseñas antes de usar la plataforma en un entorno real de investigación (el administrador puede restablecer contraseñas desde el panel).

---

## 6. Cómo crear nuevos usuarios

Como **administrador**, ve a **Estudiantes → Nuevo estudiante**, diligencia nombre, usuario y contraseña. El sistema:
- Crea el usuario con la contraseña cifrada.
- Inicializa su progreso (módulo 1 desbloqueado, los demás bloqueados).
- Crea su perfil de gamificación (0 puntos, nivel 1).

También puedes **editar el nombre**, **restablecer la contraseña** o **eliminar (desactivar)** un estudiante desde la misma pantalla.

---

## 7. Cómo modificar los contenidos y actividades (sin tocar el código)

Todo el contenido pedagógico —textos, ejemplos, preguntas, glosario, videos, pretest y postest— está en:

```
data/modules.json
```

Puedes editar este archivo con cualquier editor de texto. Cada módulo tiene esta estructura general:

```json
{
  "id": 1,
  "titulo": "...",
  "texto_lectura": "...",
  "video_youtube": "https://www.youtube.com/embed/XXXXXXXX",
  "glosario": [...],
  "actividades": [ { "tipo": "opcion_multiple", "preguntas": [...] }, ... ]
}
```

Tipos de actividad soportados: `opcion_multiple`, `verdadero_falso`, `completar`, `relacionar`, `ordenar`, `pregunta_abierta`.

Después de editar el archivo, simplemente **reinicia la aplicación** (`Ctrl+C` y `python app.py` de nuevo) para que los cambios se sincronicen con la base de datos.

> Importante: no cambies el campo `"id"` de un módulo existente si ya hay estudiantes con progreso registrado, porque el progreso está vinculado a ese identificador.

---

## 8. Funcionalidades incluidas

### Estudiante
- Login seguro y sesión protegida.
- Dashboard con bienvenida, avatar, barra de progreso, nivel, puntos, promedio.
- 5 módulos (literal, inferencial, crítico) con contenido interactivo: texto, video de YouTube, datos curiosos, palabras nuevas, glosario, resumen y mapa conceptual.
- 2 actividades calificables automáticamente por módulo (excepto las de pregunta abierta).
- Calificación en escala colombiana 1.0 a 5.0, con aciertos, errores, tiempo e intentos.
- Retroalimentación automática y recomendaciones personalizadas según el desempeño.
- Desbloqueo progresivo: el siguiente módulo se habilita solo si el actual se aprueba con nota ≥ 3.5.
- Pretest y postest con comparación de resultados.
- Certificado de logro en PDF al aprobar todos los módulos.
- Gamificación: puntos, experiencia, niveles, insignias y celebración animada al aprobar.
- Accesibilidad: aumentar letra, modo oscuro, alto contraste y lectura en voz alta (Text-to-Speech).

### Administrador / Docente
- Ver, crear, editar, eliminar y restablecer contraseña de estudiantes.
- Buscar estudiantes por nombre o usuario.
- Ver progreso, promedio, historial completo de intentos y tiempos por estudiante.
- Estadísticas con gráficos (Chart.js): promedio por módulo, nivel de comprensión, actividades por estudiante, estudiantes activos/inactivos.
- Descarga de reportes en **PDF, Excel y CSV**, con filtros por fecha y módulo.
- Bitácora (logs) de toda la actividad de la plataforma, útil como evidencia para la investigación.
- Respaldo y restauración de la base de datos desde el panel.

---

## 9. Notas sobre seguridad

- Las contraseñas se almacenan cifradas con `werkzeug.security` (nunca en texto plano).
- Todas las rutas del estudiante y del administrador están protegidas: si no has iniciado sesión, te redirige al login; si intentas entrar a una sección que no te corresponde, se bloquea el acceso.
- Existe cierre de sesión explícito (`Cerrar sesión`).
- Antes de un despliegue real, cambia el valor de `app.secret_key` en `app.py` por una clave propia y secreta.

---

## 10. Solución de problemas comunes

| Problema | Solución |
|---|---|
| `ModuleNotFoundError: flask` | Ejecuta `pip install -r requirements.txt` |
| Quiero reiniciar todos los datos desde cero | Borra el archivo `lecturatic.db` y vuelve a ejecutar `python app.py` |
| Cambié `modules.json` y no veo los cambios | Reinicia la aplicación (los módulos se sincronizan al arrancar) |
| Necesito otro puerto | Cambia `port=5000` en la última línea de `app.py` |

---

## 11. Arquitectura pensada para escalar

- El número de módulos, actividades y preguntas no está limitado por el código: basta con agregar nuevos objetos en `data/modules.json`.
- Los tipos de actividad están implementados como funciones independientes en `logica.py`, por lo que se pueden agregar nuevos tipos sin afectar los existentes.
- La base de datos SQLite puede migrarse a PostgreSQL o MySQL cambiando únicamente `database.py`, ya que el resto del código usa SQL estándar.
- El registro de logs permite analizar el uso real de la plataforma durante la investigación (frecuencia de ingreso, tiempo de estudio, evolución de calificaciones, etc.).
