"""Genera los PDF de ejemplo de la carpeta muestras/ (para probar la validación automática)."""
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "muestras")
os.makedirs(OUT, exist_ok=True)
W, H = letter


def membrete(c):
    c.setFillColorRGB(0.07, 0.21, 0.36); c.rect(0, H - 50, W, 50, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1); c.setFont("Helvetica-Bold", 11)
    c.drawString(40, H - 30, "Hoja membretada · Instituto Tecnológico de Matehuala (simulado)")
    c.setFillColorRGB(0, 0, 0)


def doc(nombre, titulo, secciones, membretada_en_todas=False):
    c = canvas.Canvas(os.path.join(OUT, nombre), pagesize=letter)
    membrete(c)
    c.setFont("Helvetica-Bold", 20); c.drawCentredString(W / 2, H / 2 + 40, titulo)
    c.setFont("Helvetica", 12); c.drawCentredString(W / 2, H / 2, "Alumno: Ana Sofía Ledezma (ficticia) · Ing. en Sistemas Computacionales")
    c.drawCentredString(W / 2, H / 2 - 20, "Documento de ejemplo para probar ResiTrack · datos simulados")
    c.showPage()
    for i in range(0, len(secciones), 3):
        if membretada_en_todas:
            membrete(c)
        y = H - 100
        for nom, txt in secciones[i:i + 3]:
            c.setFont("Helvetica-Bold", 14); c.drawString(60, y, nom); y -= 22
            c.setFont("Helvetica", 11)
            for linea in txt:
                c.drawString(60, y, linea); y -= 16
            y -= 18
        c.showPage()
    c.save()


L = ["Texto de ejemplo para esta sección del documento.", "Se describe de forma breve lo que corresponde."]
PRELIM = [("1. Nombre del proyecto", ["Sistema de inventario para almacén de refacciones"]), ("2. Objetivos", L), ("3. Justificación", L),
          ("4. Cronograma", ["Semanas 1–4: análisis · 5–10: desarrollo · 11–16: pruebas"]), ("5. Descripción de actividades", L)]
doc("reporte_preliminar_correcto.pdf", "Reporte preliminar", PRELIM)
doc("reporte_preliminar_sin_cronograma.pdf", "Reporte preliminar", [s for s in PRELIM if "Cronograma" not in s[0]])
doc("reporte_preliminar_membretada_en_todas.pdf", "Reporte preliminar", PRELIM, membretada_en_todas=True)
doc("reporte_final.pdf", "Reporte final de Residencia Profesional",
    [("Introducción", L), ("Problemas a resolver", L), ("Resultados", L), ("Conclusiones", L), ("Referencias", L)])
print("Muestras generadas en", OUT)
