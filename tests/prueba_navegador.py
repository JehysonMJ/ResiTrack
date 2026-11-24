"""Prueba de punta a punta en el navegador (Playwright).
Uso:  1) python app.py   (en otra terminal)
      2) pip install playwright && python -m playwright install chromium
      3) python tests/prueba_navegador.py [http://localhost:5000] [carpeta_capturas]
Recorre el trámite completo: alumno → empresa → asesores → reporte final → acta → reportes."""
import sys, os, datetime as dt
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else None
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = lambda f: os.path.join(BASE, "muestras", f)
resultados, errores = [], []


def ok(nombre, cond, detalle=""):
    resultados.append((nombre, bool(cond), detalle))
    print(("  OK  " if cond else "FALLA ") + nombre + (f"  ({detalle})" if detalle else ""))


def shot(pg, nombre, full=True):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        pg.evaluate("document.getElementById('toast').classList.remove('on')")
        pg.wait_for_timeout(350)
        pg.screenshot(path=os.path.join(SHOTS, nombre + ".png"), full_page=full)


def login(pg, ruta, u, p):
    pg.goto(URL + "/#/" + ruta)
    pg.wait_for_selector("#lf")
    pg.fill("#u", u); pg.fill("#p", p); pg.click("#lf button.pri")
    pg.wait_for_selector("#salir")


def salir(pg):
    pg.click("#salir"); pg.wait_for_timeout(400)


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errores.append(str(e)))
    # reinicia datos
    pg.goto(URL + "/#/demo"); pg.wait_for_selector("#rs"); pg.click("#rs"); pg.wait_for_timeout(800)

    pg.goto(URL + "/#/"); pg.wait_for_selector(".hero"); pg.wait_for_timeout(900)
    ok("UI-01 La página de inicio carga", pg.locator("h1").first.is_visible())
    shot(pg, "01_inicio", full=False)

    # requisito faltante
    login(pg, "alumno", "22000102", "Resi-2026")
    ok("UI-02 Alumno con 4/5 créditos ve el requisito en rojo y no ve el banco", pg.locator(".ico.no").count() == 1 and pg.locator("[data-pid]").count() == 0)
    salir(pg)

    # contraseña incorrecta
    pg.goto(URL + "/#/alumno"); pg.wait_for_selector("#lf"); pg.fill("#u", "22000101"); pg.fill("#p", "mal"); pg.click("#lf button.pri")
    pg.wait_for_selector(".err-box"); ok("UI-03 Contraseña incorrecta muestra mensaje claro", "incorrectos" in pg.inner_text(".err-box"))

    login(pg, "alumno", "22000101", "Resi-2026")
    shot(pg, "02_alumno_banco")
    pg.click("[data-pid]")
    pg.set_input_files("#f-rp", M("reporte_preliminar_sin_cronograma.pdf")); pg.wait_for_selector("#rpm .err-box")
    ok("UI-04 Reporte preliminar sin cronograma se rechaza antes de enviar", "Cronograma" in pg.inner_text("#rpm"))
    pg.set_input_files("#f-rp", M("reporte_preliminar_membretada_en_todas.pdf")); pg.wait_for_timeout(700)
    ok("UI-05 Hoja membretada en todas las páginas se rechaza", "membretada" in pg.inner_text("#rpm"))
    shot(pg, "03_validacion_error", full=False)
    pg.set_input_files("#f-rp", M("reporte_preliminar_correcto.pdf")); pg.wait_for_selector(".tl", timeout=8000)
    txt = pg.inner_text("#app")
    ok("UI-06 Solicitud válida: asesor asignado y carta emitida al instante", "Asesor interno asignado" in txt and "Carta de presentación emitida" in txt and "Paola Garza" in txt, "se asigna a quien tiene menor carga")
    pg.wait_for_timeout(2800)
    shot(pg, "04_alumno_tramite")
    with pg.expect_download() as dl:
        pg.click("a[href='/api/alumno/carta.pdf']")
    ok("UI-07 La carta se descarga en PDF", dl.value.suggested_filename.endswith(".pdf"), dl.value.suggested_filename)
    folio_carta = dl.value.suggested_filename[:-4]
    salir(pg)

    # empresa acepta con el enlace (desde la bandeja simulada)
    pg.goto(URL + "/#/demo"); pg.wait_for_selector("text=Enlaces de empresa")
    enlace = pg.locator("a:has-text('Abrir como empresa')").last.get_attribute("href")
    pg.goto(URL + "/" + enlace); pg.wait_for_selector("#af")
    shot(pg, "05_empresa_aceptar", full=False)
    pg.fill("#n", "Ing. Carlos Méndez"); pg.fill("#c", "Jefe de Sistemas"); pg.fill("#m", "malcorreo")
    pg.fill("#i", (dt.date.today() - dt.timedelta(days=110)).isoformat()); pg.click("#af button.pri")
    pg.wait_for_timeout(400)
    ok("UI-08 Correo inválido del asesor externo se rechaza", pg.locator("#ae .err-box").count() == 1 or not pg.evaluate("document.getElementById('m').checkValidity()"))
    pg.fill("#m", "carlos@empresa.ejemplo.mx"); pg.click("#af button.pri"); pg.wait_for_selector("#evb")
    ok("UI-09 La empresa acepta sin crear cuenta y queda lista la evaluación", True)

    def eval_modal(valores):
        ins = pg.locator("#modal-card input")
        for i, v in enumerate(valores):
            ins.nth(i).fill(str(v))
        pg.click("#ok")

    pg.click("#evb"); eval_modal([9, 9, 9, 28, 23, 14])
    pg.wait_for_timeout(600)

    login(pg, "asesor", "asesor.sistemas2", "Asesor-2026")
    shot(pg, "06_asesor")
    btn = pg.locator("button[data-t='s1']").last; btn.click()
    eval_modal([10, 9, 9, 29, 24, 15]); pg.wait_for_timeout(300)
    ins = pg.locator("[data-t='s2']")
    ok("UI-10 Con las dos evaluaciones del seguimiento 1 la etapa avanza", ins.count() >= 1)
    # calificación fuera de rango
    ins.last.click(); pg.locator("#modal-card input").first.fill("12"); pg.click("#ok"); pg.wait_for_selector("#em .err-box")
    ok("UI-11 Puntos fuera de rango se rechazan", "entre 0 y 10" in pg.inner_text("#em"))
    shot(pg, "07_evaluacion", full=False)
    for i, v in enumerate([9, 9, 8, 27, 22, 13]):
        pg.locator("#modal-card input").nth(i).fill(str(v))
    pg.click("#ok"); pg.wait_for_timeout(500)
    salir(pg)
    pg.goto(URL + "/" + enlace); pg.wait_for_selector("#evb"); pg.click("#evb"); eval_modal([9, 10, 9, 28, 23, 14]); pg.wait_for_timeout(600)

    login(pg, "alumno", "22000101", "Resi-2026")
    ok("UI-12 Tras el seguimiento 2 el alumno puede subir su reporte final", pg.locator("#dz-rf").count() == 1)
    pg.set_input_files("#f-rf", M("reporte_preliminar_correcto.pdf")); pg.wait_for_selector("#rfm .err-box")
    ok("UI-13 Un reporte final sin Conclusiones se rechaza", "Conclusiones" in pg.inner_text("#rfm"))
    pg.set_input_files("#f-rf", M("reporte_final.pdf")); pg.wait_for_timeout(1200)
    ok("UI-14 Reporte final entregado", "Reporte final entregado" in pg.inner_text("#app"))
    salir(pg)

    login(pg, "asesor", "asesor.sistemas2", "Asesor-2026")
    pg.locator("button[data-t='rep']").last.click(); eval_modal([9, 14, 13, 31, 13, 9]); pg.wait_for_timeout(900)
    salir(pg)
    login(pg, "alumno", "22000101", "Resi-2026")
    txt = pg.inner_text("#app")
    # s1=(96+92)/2=94 ; s2=(88+93)/2=90.5 ; rep=89 → 0.1*94 + 0.1*90.5 + 0.8*89 = 89.65 → 90
    ok("UI-15 Calificación final 10/10/80 calculada y acreditada", "90" in txt and "Acreditada" in txt)
    with pg.expect_download() as dl:
        pg.click("a[href='/api/alumno/acta.pdf']")
    ok("UI-16 El acta se descarga en PDF", dl.value.suggested_filename.endswith(".pdf"))
    shot(pg, "08_alumno_acreditada")
    salir(pg)

    login(pg, "reportes", "dep", "Dep-2026")
    txt = pg.inner_text("#app")
    ok("UI-17 Reportes de solo lectura con indicadores", "solo lectura" in txt and "hojas impresas" in txt and pg.locator("button:has-text('Autorizar')").count() == 0)
    shot(pg, "09_reportes")
    with pg.expect_download() as dl:
        pg.click("a[href='/api/consulta/excel']")
    ok("UI-18 Reporte en Excel", dl.value.suggested_filename.endswith(".xlsx"))
    salir(pg)

    pg.goto(URL + "/#/verificar/" + folio_carta); pg.wait_for_selector(".seal")
    ok("UI-19 El QR de la carta verifica su autenticidad", "auténtica" in pg.inner_text("#app"))
    shot(pg, "10_verificar", full=False)
    pg.goto(URL + "/#/verificar/RT-0000-9999"); pg.wait_for_selector(".seal.bad")
    ok("UI-20 Un folio falso se marca como no encontrado", True)

    # reloj y recordatorios
    pg.goto(URL + "/#/demo"); pg.wait_for_selector("[data-d='7']"); pg.click("[data-d='7']"); pg.wait_for_timeout(900)
    ok("UI-21 Al avanzar el reloj se envían recordatorios", "Recordatorio" in pg.inner_text("#app"))
    shot(pg, "11_demo", full=False)
    pg.click("#r0"); pg.wait_for_timeout(500)

    # tema oscuro y celular
    pg.goto(URL + "/#/"); pg.wait_for_selector(".hero"); pg.click("#theme"); pg.wait_for_timeout(700)
    shot(pg, "12_inicio_oscuro", full=False)
    pg.click("#theme")
    m = b.new_page(viewport={"width": 390, "height": 844})
    m.goto(URL + "/#/"); m.wait_for_selector(".hero"); m.wait_for_timeout(600)
    sw = m.evaluate("document.documentElement.scrollWidth")
    ok("UI-22 Se usa en celular sin desplazamiento horizontal", sw <= 392, f"{sw}px")
    if SHOTS:
        m.screenshot(path=os.path.join(SHOTS, "13_celular.png"))
    ok("UI-23 Sin errores de JavaScript", not errores, "; ".join(errores)[:200])
    b.close()

fallas = [r for r in resultados if not r[1]]
print(f"\n{len(resultados) - len(fallas)} de {len(resultados)} pruebas de interfaz aprobadas")
sys.exit(1 if fallas else 0)
