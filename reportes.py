# -*- coding: utf-8 -*-
"""
reportes.py
------------------------------------------------------------
Genera reportes descargables para el panel del administrador
(PDF, Excel, CSV) y certificados en PDF para los estudiantes
que completan la plataforma.
------------------------------------------------------------
"""

import csv
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER


ENCABEZADOS = ["Nombre", "Usuario", "Promedio General", "Módulos Aprobados",
               "Porcentaje de Avance", "Último Acceso"]


def generar_csv(filas):
    """Genera un archivo CSV en memoria a partir de una lista de estudiantes."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(ENCABEZADOS)
    for f in filas:
        writer.writerow(f)
    return output.getvalue().encode("utf-8-sig")


def generar_excel(filas):
    """Genera un archivo Excel (.xlsx) en memoria a partir de una lista de estudiantes."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte LECTURATIC"

    ws.append(ENCABEZADOS)
    header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for f in filas:
        ws.append(f)

    for col in ws.columns:
        longitud = max(len(str(c.value)) for c in col if c.value is not None) if col else 10
        ws.column_dimensions[col[0].column_letter].width = max(15, longitud + 2)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def generar_pdf(filas, titulo="Reporte General de Estudiantes - LECTURATIC"):
    """Genera un reporte en PDF con tabla de estudiantes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                             topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle("titulo", parent=styles["Title"], alignment=TA_CENTER, fontSize=16)
    subtitulo_style = ParagraphStyle("subtitulo", parent=styles["Normal"], alignment=TA_CENTER, fontSize=10)

    elementos = [
        Paragraph(titulo, titulo_style),
        Paragraph(f"Generado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", subtitulo_style),
        Spacer(1, 0.6 * cm),
    ]

    data = [ENCABEZADOS] + [[str(x) for x in f] for f in filas]
    tabla = Table(data, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D32")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F8E9")]),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    elementos.append(tabla)
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()


def generar_certificado_pdf(nombre_estudiante, promedio_general):
    """
    Genera un certificado de finalización en PDF para un estudiante
    que aprobó todos los módulos de LECTURATIC.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle("titulo_cert", parent=styles["Title"], fontSize=32,
                                    alignment=TA_CENTER, textColor=colors.HexColor("#2E7D32"))
    estilo_sub = ParagraphStyle("sub_cert", parent=styles["Normal"], fontSize=16,
                                 alignment=TA_CENTER, spaceAfter=20)
    estilo_nombre = ParagraphStyle("nombre_cert", parent=styles["Title"], fontSize=26,
                                    alignment=TA_CENTER, textColor=colors.HexColor("#1565C0"))
    estilo_texto = ParagraphStyle("texto_cert", parent=styles["Normal"], fontSize=13,
                                   alignment=TA_CENTER, spaceAfter=10)

    elementos = [
        Spacer(1, 1.5 * cm),
        Paragraph("CERTIFICADO DE LOGRO", estilo_titulo),
        Paragraph("Plataforma LECTURATIC — Entorno Virtual de Aprendizaje", estilo_sub),
        Spacer(1, 1 * cm),
        Paragraph("Se otorga el presente certificado a:", estilo_texto),
        Spacer(1, 0.3 * cm),
        Paragraph(nombre_estudiante, estilo_nombre),
        Spacer(1, 0.6 * cm),
        Paragraph("por haber completado satisfactoriamente los cinco módulos de comprensión "
                  "lectora (nivel literal, inferencial y crítico) de la plataforma LECTURATIC, "
                  f"con un promedio general de {promedio_general}.", estilo_texto),
        Spacer(1, 1.2 * cm),
        Paragraph(f"Fecha de emisión: {datetime.now().strftime('%d de %B de %Y')}", estilo_texto),
    ]

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()
