"""Pruebas automáticas de la API y de las reglas de negocio (pytest).
Uso:  python -m pytest -q
Cada prueba usa una base de datos temporal con los datos simulados."""
import io, os, sys, tempfile, importlib, pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
M = lambda f: open(os.path.join(RAIZ, "muestras", f), "rb").read()


@pytest.fixture()
def c():
    os.environ["DATA_DIR"] = tempfile.mkdtemp()
    import app as modulo
    modulo = importlib.reload(modulo)
    modulo.app.config["TESTING"] = True
    cl = modulo.app.test_client()
    tok = cl.get("/api/sesion").get_json()["token"]
    cl.h = {"X-CSRF-Token": tok}
    cl.m = modulo
    return cl


def login(c, u, p, rol):
    return c.post("/api/login", json={"usuario": u, "clave": p, "rol": rol}, headers=c.h)


def solicitar(c, archivo, pid=1):
    return c.post("/api/alumno/solicitar", data={"proyecto_id": str(pid), "archivo": (io.BytesIO(M(archivo)), archivo)},
                  headers=c.h, content_type="multipart/form-data")


def test_csrf_obligatorio(c):
    assert c.post("/api/login", json={}).status_code == 403


def test_login_incorrecto_y_bloqueo(c):
    for i in range(5):
        r = login(c, "22000101", "mal", "alumno")
    assert r.status_code == 401
    assert login(c, "22000101", "Resi-2026", "alumno").status_code == 429


def test_requisitos_rn01(c):
    login(c, "22000102", "Resi-2026", "alumno")
    d = c.get("/api/alumno").get_json()
    assert d["req"]["cumple"] is False and d["proyectos"] == []
    assert solicitar(c, "reporte_preliminar_correcto.pdf", 1).status_code == 409


def test_validacion_reporte_preliminar(c):
    login(c, "22000101", "Resi-2026", "alumno")
    r = solicitar(c, "reporte_preliminar_sin_cronograma.pdf")
    assert r.status_code == 422 and "Cronograma" in r.get_json()["error"]
    r = solicitar(c, "reporte_preliminar_membretada_en_todas.pdf")
    assert r.status_code == 422 and "membretada" in r.get_json()["error"]
    r = c.post("/api/alumno/solicitar", data={"proyecto_id": "1", "archivo": (io.BytesIO(b"hola"), "a.docx")}, headers=c.h, content_type="multipart/form-data")
    assert r.status_code == 422 and "PDF" in r.get_json()["error"]


def test_flujo_completo_sin_personal(c):
    login(c, "22000101", "Resi-2026", "alumno")
    r = solicitar(c, "reporte_preliminar_correcto.pdf")
    assert r.status_code == 200
    s = c.get("/api/alumno").get_json()["solicitud"]
    assert s["etapa"] == "CARTA_EMITIDA" and s["asesor"]["nombre"] == "Ing. Paola Garza"  # menor carga (0 de 6)
    assert c.get("/api/alumno/carta.pdf").data[:4] == b"%PDF"
    with c.m.app.app_context():
        tok = c.m.db().execute("SELECT token FROM solicitudes WHERE control='22000101'").fetchone()[0]
    r = c.post(f"/api/empresa/{tok}/aceptar", json={"nombre": "Ing. Carlos Méndez", "cargo": "Jefe", "correo": "c@e.mx", "inicio": "2026-08-01"}, headers=c.h)
    assert r.status_code == 200
    seg = [9, 9, 9, 28, 23, 14]
    assert c.post(f"/api/empresa/{tok}/evaluar", json={"tipo": "s1", "puntos": seg}, headers=c.h).status_code == 200
    c.post("/api/logout", json={}, headers=c.h)
    login(c, "asesor.sistemas2", "Asesor-2026", "asesor")
    sid = c.get("/api/asesor").get_json()["residentes"][0]["id"]
    assert c.post("/api/asesor/evaluar", json={"id": sid, "tipo": "s1", "puntos": [10, 9, 9, 29, 24, 15]}, headers=c.h).status_code == 200
    assert c.post("/api/asesor/evaluar", json={"id": sid, "tipo": "s2", "puntos": [12, 9, 9, 29, 24, 15]}, headers=c.h).status_code == 400
    assert c.post("/api/asesor/evaluar", json={"id": sid, "tipo": "s2", "puntos": [9, 9, 8, 27, 22, 13]}, headers=c.h).status_code == 200
    assert c.post(f"/api/empresa/{tok}/evaluar", json={"tipo": "s2", "puntos": [9, 10, 9, 28, 23, 14]}, headers=c.h).status_code == 200
    c.post("/api/logout", json={}, headers=c.h)
    login(c, "22000101", "Resi-2026", "alumno")
    r = c.post("/api/alumno/reporte", data={"archivo": (io.BytesIO(M("reporte_final.pdf")), "final.pdf")}, headers=c.h, content_type="multipart/form-data")
    assert r.status_code == 200
    c.post("/api/logout", json={}, headers=c.h)
    login(c, "asesor.sistemas2", "Asesor-2026", "asesor")
    assert c.post("/api/asesor/evaluar", json={"id": sid, "tipo": "rep", "puntos": [9, 14, 13, 31, 13, 9]}, headers=c.h).status_code == 200
    c.post("/api/logout", json={}, headers=c.h)
    login(c, "dep", "Dep-2026", "consulta")
    d = c.get("/api/consulta").get_json()
    fila = [f for f in d["solicitudes"] if f["control"] == "22000101"][0]
    assert fila["etapa"] == "ACREDITADA" and fila["calificacion"] == 90   # 0.1·94 + 0.1·90.5 + 0.8·89 = 89.65
    assert any(a["control"] == "22000101" for a in d["actas"])              # acta en el SII sin captura
    assert d["kpi"]["tareas_personal"] == 0 and d["kpi"]["hojas"] == 0
    assert c.get("/api/consulta/excel").status_code == 200


def test_tope_de_asesor_rn07(c):
    with c.m.app.app_context():
        c.m.db().execute("UPDATE asesores SET tope=0 WHERE depto='Sistemas y Computación'")
        c.m.db().commit()
    login(c, "22000101", "Resi-2026", "alumno")
    assert solicitar(c, "reporte_preliminar_correcto.pdf").status_code == 200
    s = c.get("/api/alumno").get_json()["solicitud"]
    assert s["asesor"] is None and "cupo" in s["siguiente"]


def test_consulta_es_solo_lectura(c):
    login(c, "22000101", "Resi-2026", "alumno")
    assert c.get("/api/consulta").status_code == 401
    c.post("/api/logout", json={}, headers=c.h)
    login(c, "dep", "Dep-2026", "consulta")
    assert c.post("/api/asesor/evaluar", json={"id": 1, "tipo": "s1", "puntos": []}, headers=c.h).status_code == 401


def test_verificar_carta(c):
    with c.m.app.app_context():
        folio = c.m.db().execute("SELECT carta_folio FROM solicitudes WHERE carta_folio IS NOT NULL").fetchone()[0]
    assert c.get(f"/api/verificar/{folio}").get_json()["valido"] is True
    assert c.get("/api/verificar/RT-0000-0000").get_json()["valido"] is False


def test_recordatorios_con_reloj(c):
    antes = c.get("/api/demo").get_json()["correos"]
    c.post("/api/demo/reloj", json={"dias": 30}, headers=c.h)
    despues = c.get("/api/demo").get_json()["correos"]
    assert len(despues) > len(antes) and any("Recordatorio" in x["asunto"] for x in despues)
