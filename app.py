"""ResiTrack · Gestión automatizada de Residencias Profesionales (TecNM Campus Matehuala).
Prototipo funcional de Altiplano Labs con DATOS SIMULADOS: todos los nombres, números de
control, empresas y calificaciones son inventados.

Principio de diseño: el alumno, la empresa y los asesores hacen su parte en línea y el sistema
hace todo lo administrativo. La DEP, la Jefatura y Servicios Escolares solo consultan reportes.
"""
import os, io, re, json, secrets, sqlite3, unicodedata, datetime as dt
from flask import Flask, g, request, session, jsonify, send_file, render_template, abort, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE, "data"))
UPLOADS = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOADS, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "resitrack.db")
HASH = "pbkdf2:sha256:100000"
MAX_INTENTOS, BLOQUEO_MIN = 5, 10
MB = 1024 * 1024


def _secret():
    k = os.environ.get("SECRET_KEY")
    if k:
        return k
    p = os.path.join(DATA_DIR, "secret.key")
    if not os.path.exists(p):
        with open(p, "w") as f:
            f.write(secrets.token_hex(32))
    return open(p).read().strip()


app = Flask(__name__)
app.secret_key = _secret()
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("FORCE_HTTPS") == "1",
                  MAX_CONTENT_LENGTH=20 * MB)

# ------------------------------------------------------------------ catálogos
ETAPAS = [
    ("SOLICITADA", "Solicitud registrada"),
    ("ASESOR_ASIGNADO", "Asesor interno asignado"),
    ("CARTA_EMITIDA", "Carta de presentación emitida"),
    ("EN_RESIDENCIA", "Aceptada por la empresa"),
    ("SEGUIMIENTO_1", "Seguimiento 1 registrado"),
    ("SEGUIMIENTO_2", "Seguimiento 2 registrado"),
    ("REPORTE_ENTREGADO", "Reporte final entregado"),
    ("ACREDITADA", "Residencia acreditada"),
]
ETAPA_IDX = {k: i for i, (k, _) in enumerate(ETAPAS)}
ETAPA_TXT = dict(ETAPAS) | {"NO_ACREDITADA": "No acreditada", "RECHAZADA_EMPRESA": "La empresa no aceptó"}
CERRADAS = ("ACREDITADA", "NO_ACREDITADA", "RECHAZADA_EMPRESA")

DEPTO = {"Ing. en Sistemas Computacionales": "Sistemas y Computación", "Ing. Industrial": "Ingeniería Industrial",
         "Ing. Civil": "Ciencias de la Tierra", "Ing. en Gestión Empresarial": "Ciencias Económico-Administrativas",
         "Contador Público": "Ciencias Económico-Administrativas"}

CRIT_SEG = [("Asiste puntualmente y cumple su horario", 10), ("Trabaja en equipo y se comunica", 10),
            ("Muestra iniciativa", 10), ("Cumple los objetivos del cronograma", 30),
            ("Aplica los conocimientos de su carrera", 25), ("Documenta su trabajo", 15)]
CRIT_REP = [("Portada, índice y estructura", 10), ("Problema, objetivos y justificación", 15),
            ("Fundamento teórico", 15), ("Desarrollo y resultados", 35), ("Conclusiones", 15),
            ("Referencias y redacción", 10)]
SECC_PRELIM = [("nombre del proyecto", "Nombre del proyecto"), ("objetivo", "Objetivos"),
               ("justificacion", "Justificación"), ("cronograma", "Cronograma"),
               ("descripcion de actividades", "Descripción de actividades")]
SECC_FINAL = [("introduccion", "Introducción"), ("resultados", "Resultados"), ("conclusiones", "Conclusiones")]

# ------------------------------------------------------------------ base de datos
SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios(usuario TEXT PRIMARY KEY, clave_hash TEXT, rol TEXT, nombre TEXT, ref TEXT);
CREATE TABLE IF NOT EXISTS sii(control TEXT PRIMARY KEY, nombre TEXT, carrera TEXT, semestre INTEGER, creditos REAL,
  servicio_social INTEGER, act_comp REAL, correo TEXT);
CREATE TABLE IF NOT EXISTS asesores(id INTEGER PRIMARY KEY, usuario TEXT, nombre TEXT, depto TEXT, correo TEXT, tope INTEGER DEFAULT 6);
CREATE TABLE IF NOT EXISTS empresas(id INTEGER PRIMARY KEY, nombre TEXT, rfc TEXT, correo TEXT);
CREATE TABLE IF NOT EXISTS proyectos(id INTEGER PRIMARY KEY, titulo TEXT, empresa_id INTEGER, carrera TEXT, cupo INTEGER, avalado INTEGER DEFAULT 1, descripcion TEXT);
CREATE TABLE IF NOT EXISTS solicitudes(id INTEGER PRIMARY KEY, folio TEXT UNIQUE, control TEXT, proyecto_id INTEGER, etapa TEXT,
  asesor_id INTEGER, ext_nombre TEXT, ext_cargo TEXT, ext_correo TEXT, token TEXT UNIQUE, inicio TEXT, fin TEXT,
  carta_folio TEXT, calificacion INTEGER, motivo_rechazo TEXT, creado TEXT, en_espera INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS eventos(id INTEGER PRIMARY KEY, solicitud_id INTEGER, etapa TEXT, fecha TEXT, detalle TEXT);
CREATE TABLE IF NOT EXISTS documentos(id INTEGER PRIMARY KEY, solicitud_id INTEGER, control TEXT, tipo TEXT, nombre TEXT, ruta TEXT, fecha TEXT);
CREATE TABLE IF NOT EXISTS rechazos(id INTEGER PRIMARY KEY, control TEXT, tipo TEXT, motivo TEXT, fecha TEXT);
CREATE TABLE IF NOT EXISTS evaluaciones(id INTEGER PRIMARY KEY, solicitud_id INTEGER, tipo TEXT, evaluador TEXT, puntos TEXT, total INTEGER, fecha TEXT,
  UNIQUE(solicitud_id, tipo, evaluador));
CREATE TABLE IF NOT EXISTS correos(id INTEGER PRIMARY KEY, para TEXT, asunto TEXT, cuerpo TEXT, enlace TEXT, fecha TEXT);
CREATE TABLE IF NOT EXISTS recordatorios(solicitud_id INTEGER, tipo TEXT, PRIMARY KEY(solicitud_id, tipo));
CREATE TABLE IF NOT EXISTS sii_actas(id INTEGER PRIMARY KEY, solicitud_id INTEGER, control TEXT, calificacion INTEGER, fecha TEXT, folio TEXT);
CREATE TABLE IF NOT EXISTS auditoria(id INTEGER PRIMARY KEY, usuario TEXT, accion TEXT, fecha TEXT);
CREATE TABLE IF NOT EXISTS ajustes(clave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS intentos(clave TEXT PRIMARY KEY, n INTEGER DEFAULT 0, hasta TEXT);
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=30)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def _close(_):
    d = g.pop("db", None)
    if d:
        d.close()


def ajuste(k, d=""):
    r = db().execute("SELECT valor FROM ajustes WHERE clave=?", (k,)).fetchone()
    return r["valor"] if r else d


def set_ajuste(k, v):
    db().execute("INSERT INTO ajustes VALUES(?,?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (k, str(v)))


# Reloj del sistema. En modo demostración se puede adelantar para ver recordatorios y plazos.
def now():
    off = 0
    try:
        off = int(ajuste("reloj_dias", "0"))
    except Exception:
        pass
    return dt.datetime.now().replace(microsecond=0) + dt.timedelta(days=off)


def iso(d):
    return d.isoformat(sep=" ") if isinstance(d, dt.datetime) else d.isoformat()


def pdate(s):
    return dt.datetime.fromisoformat(s) if s and len(s) > 10 else dt.datetime.fromisoformat(s + " 00:00:00") if s else None


def fmt(s):
    if not s:
        return ""
    meses = "ene feb mar abr may jun jul ago sep oct nov dic".split()
    d = pdate(s)
    return f"{d.day} {meses[d.month - 1]} {d.year}"


def audit(accion, usuario=None):
    db().execute("INSERT INTO auditoria(usuario,accion,fecha) VALUES(?,?,?)",
                 (usuario or session.get("u") or "sistema", accion, iso(now())))


def correo(para, asunto, cuerpo, enlace=""):
    db().execute("INSERT INTO correos(para,asunto,cuerpo,enlace,fecha) VALUES(?,?,?,?,?)", (para, asunto, cuerpo, enlace, iso(now())))


def evento(sid, etapa, detalle="", fecha=None):
    db().execute("INSERT INTO eventos(solicitud_id,etapa,fecha,detalle) VALUES(?,?,?,?)", (sid, etapa, iso(fecha or now()), detalle))
    db().execute("UPDATE solicitudes SET etapa=? WHERE id=?", (etapa, sid))


def init_db(reset=False):
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        for root, _, files in os.walk(UPLOADS):
            for f in files:
                os.remove(os.path.join(root, f))
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    vacia = c.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0
    c.close()
    if vacia:
        with app.app_context():
            seed()
            db().commit()


# ------------------------------------------------------------------ lógica de negocio (servicios)
def norm(s):
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s)


def requisitos(control):
    """ValidadorRequisitos: lee el kárdex del SII (simulado) y aplica RN-01."""
    a = db().execute("SELECT * FROM sii WHERE control=?", (control,)).fetchone()
    if not a:
        return None
    reqs = [
        {"id": "creditos", "nombre": "Créditos aprobados ≥ 80 %", "ok": a["creditos"] >= 80, "valor": f"{a['creditos']:.0f} %",
         "ayuda": "Te faltan créditos. Revisa tu carga académica con tu coordinador de carrera."},
        {"id": "ss", "nombre": "Servicio social acreditado", "ok": bool(a["servicio_social"]),
         "valor": "Liberado" if a["servicio_social"] else "Pendiente", "ayuda": "Termina y libera tu servicio social."},
        {"id": "ac", "nombre": "Actividades complementarias (5 créditos)", "ok": a["act_comp"] >= 5,
         "valor": f"{a['act_comp']:g} de 5", "ayuda": f"Te falta{'n' if 5 - a['act_comp'] > 1 else ''} {5 - a['act_comp']:g} crédito(s). Consulta la oferta de actividades complementarias."},
    ]
    return {"alumno": dict(a), "requisitos": reqs, "cumple": all(r["ok"] for r in reqs)}


def ocupados(pid):
    return db().execute("SELECT COUNT(*) FROM solicitudes WHERE proyecto_id=? AND etapa NOT IN ('RECHAZADA_EMPRESA')", (pid,)).fetchone()[0]


def carga(aid):
    return db().execute(f"SELECT COUNT(*) FROM solicitudes WHERE asesor_id=? AND etapa NOT IN {CERRADAS}", (aid,)).fetchone()[0]


def asignar_asesor(sid):
    """AsignadorAsesor (RN-07): mismo departamento, menor carga y sin pasar el tope."""
    d = db()
    s = d.execute("SELECT s.*, x.carrera FROM solicitudes s JOIN sii x ON x.control=s.control WHERE s.id=?", (sid,)).fetchone()
    depto = DEPTO.get(s["carrera"])
    cands = [(carga(a["id"]), a["id"], a) for a in d.execute("SELECT * FROM asesores WHERE depto=?", (depto,)).fetchall()]
    cands = [c for c in cands if c[0] < c[2]["tope"]]
    if not cands:
        d.execute("UPDATE solicitudes SET en_espera=1 WHERE id=?", (sid,))
        audit(f"Asignación en espera para {s['folio']}: ningún asesor de {depto} tiene cupo", "sistema")
        return None
    cands.sort(key=lambda c: (c[0], c[1]))
    ca, aid, a = cands[0]
    d.execute("UPDATE solicitudes SET asesor_id=?, en_espera=0 WHERE id=?", (aid, sid))
    evento(sid, "ASESOR_ASIGNADO", f"{a['nombre']} ({depto}); tenía {ca} de {a['tope']} residentes")
    correo(a["correo"], f"Nuevo residente asignado · {s['folio']}",
           f"Se le asignó automáticamente como asesor interno del folio {s['folio']}. Ingrese a ResiTrack para ver el reporte preliminar.", "#/asesor")
    audit(f"Asesor {a['usuario']} asignado a {s['folio']}", "sistema")
    return a


def emitir_carta(sid):
    """GeneradorDocumentos: emite la carta con folio verificable y la envía a la empresa."""
    d = db()
    s = d.execute("SELECT * FROM solicitudes WHERE id=?", (sid,)).fetchone()
    folio = "RT-%s-%04d" % (now().year, sid)
    d.execute("UPDATE solicitudes SET carta_folio=? WHERE id=?", (folio, sid))
    p, e = proyecto(s["proyecto_id"])
    a = d.execute("SELECT * FROM sii WHERE control=?", (s["control"],)).fetchone()
    evento(sid, "CARTA_EMITIDA", f"Folio {folio} con firma electrónica; enviada a {e['correo']}")
    correo(e["correo"], f"Carta de presentación · {a['nombre']}",
           f"El Instituto Tecnológico de Matehuala presenta a {a['nombre']} para el proyecto «{p['titulo']}». "
           f"Use el enlace seguro para aceptar al residente y registrar a su asesor externo (no necesita crear cuenta).",
           f"#/empresa/{s['token']}")
    correo(a["correo"], "Tu carta de presentación está lista",
           f"Tu carta (folio {folio}) ya se envió a {e['nombre']}. Puedes descargarla en ResiTrack.", "#/alumno")
    audit(f"Carta {folio} emitida", "sistema")


def proyecto(pid):
    p = db().execute("SELECT * FROM proyectos WHERE id=?", (pid,)).fetchone()
    e = db().execute("SELECT * FROM empresas WHERE id=?", (p["empresa_id"],)).fetchone()
    return p, e


def fechas(s):
    if not s["inicio"]:
        return {}
    i = pdate(s["inicio"])
    fin = pdate(s["fin"]) if s["fin"] else i + dt.timedelta(days=120)
    return {"s1": i + dt.timedelta(days=42), "s2": i + dt.timedelta(days=84), "fin": fin, "limite": fin + dt.timedelta(days=15)}


def eval_total(sid, tipo):
    rows = db().execute("SELECT evaluador,total FROM evaluaciones WHERE solicitud_id=? AND tipo=?", (sid, tipo)).fetchall()
    return {r["evaluador"]: r["total"] for r in rows}


def avanzar_seguimiento(sid, tipo):
    t = eval_total(sid, tipo)
    if "interno" in t and "externo" in t:
        cal = round((t["interno"] + t["externo"]) / 2)
        etapa = "SEGUIMIENTO_1" if tipo == "s1" else "SEGUIMIENTO_2"
        evento(sid, etapa, f"Calificación del seguimiento: {cal} (promedio interno {t['interno']} y externo {t['externo']})")
        s = db().execute("SELECT control FROM solicitudes WHERE id=?", (sid,)).fetchone()
        correo(alumno_correo(s["control"]), f"Tus asesores registraron el {ETAPA_TXT[etapa].lower()}",
               f"Calificación del seguimiento: {cal}. Revisa en ResiTrack qué sigue.", "#/alumno")


def calificacion_final(sid):
    s1, s2 = eval_total(sid, "s1"), eval_total(sid, "s2")
    rep = eval_total(sid, "rep").get("interno")
    if not (len(s1) == 2 and len(s2) == 2 and rep is not None):
        return None
    c1, c2 = (s1["interno"] + s1["externo"]) / 2, (s2["interno"] + s2["externo"]) / 2
    return round(0.1 * c1 + 0.1 * c2 + 0.8 * rep)


def cerrar_residencia(sid):
    """Calcula la calificación (RN-05), genera el acta y la envía al SII sin captura manual."""
    d = db()
    cal = calificacion_final(sid)
    s = d.execute("SELECT * FROM solicitudes WHERE id=?", (sid,)).fetchone()
    etapa = "ACREDITADA" if cal >= 70 else "NO_ACREDITADA"
    d.execute("UPDATE solicitudes SET calificacion=? WHERE id=?", (cal, sid))
    folio = "ACTA-%s-%04d" % (now().year, sid)
    d.execute("INSERT INTO sii_actas(solicitud_id,control,calificacion,fecha,folio) VALUES(?,?,?,?,?)", (sid, s["control"], cal, iso(now()), folio))
    evento(sid, etapa, f"Calificación final {cal}; acta {folio} enviada a Servicios Escolares (SII)")
    correo(alumno_correo(s["control"]), "Resultado de tu Residencia Profesional",
           f"Tu calificación final es {cal}. " + ("¡Felicidades, tu residencia está acreditada! El acta ya está en Servicios Escolares." if cal >= 70 else "No alcanzaste el mínimo de 70; acércate a tu asesor interno."), "#/alumno")
    audit(f"Acta {folio} enviada al SII ({cal})", "sistema")


def alumno_correo(control):
    r = db().execute("SELECT correo FROM sii WHERE control=?", (control,)).fetchone()
    return r["correo"] if r else ""


def procesar_reloj():
    """Calendario del periodo: envía recordatorios 3 días antes de cada fecha límite (RF-13)."""
    d = db()
    hoy = now()
    for s in d.execute(f"SELECT * FROM solicitudes WHERE inicio IS NOT NULL AND etapa NOT IN {CERRADAS}").fetchall():
        f = fechas(s)
        a = d.execute("SELECT * FROM asesores WHERE id=?", (s["asesor_id"],)).fetchone()
        nombre = d.execute("SELECT nombre FROM sii WHERE control=?", (s["control"],)).fetchone()["nombre"]
        pend = []
        if s["etapa"] == "EN_RESIDENCIA":
            pend.append(("s1", f["s1"], "seguimiento 1"))
        if s["etapa"] == "SEGUIMIENTO_1":
            pend.append(("s2", f["s2"], "seguimiento 2"))
        if s["etapa"] == "SEGUIMIENTO_2":
            pend.append(("rf", f["limite"], "entrega del reporte final"))
        for tipo, fecha, txt in pend:
            if hoy >= fecha - dt.timedelta(days=3):
                if d.execute("SELECT 1 FROM recordatorios WHERE solicitud_id=? AND tipo=?", (s["id"], tipo)).fetchone():
                    continue
                d.execute("INSERT INTO recordatorios VALUES(?,?)", (s["id"], tipo))
                if tipo == "rf":
                    correo(alumno_correo(s["control"]), f"Recordatorio: tu reporte final vence el {fmt(iso(fecha))}",
                           "Sube tu reporte final en PDF desde ResiTrack antes de la fecha límite.", "#/alumno")
                else:
                    if a:
                        correo(a["correo"], f"Recordatorio: {txt} de {nombre} el {fmt(iso(fecha))}",
                               "Registre la evaluación en ResiTrack. Le tomará menos de 5 minutos.", "#/asesor")
                    if s["ext_correo"]:
                        correo(s["ext_correo"], f"Recordatorio: {txt} de {nombre} el {fmt(iso(fecha))}",
                               "Registre la evaluación con su enlace seguro.", f"#/empresa/{s['token']}")
                audit(f"Recordatorio {tipo} de {s['folio']}", "sistema")
    d.commit()


# ------------------------------------------------------------------ validación de PDF
def leer_pdf(file, maximo):
    data = file.read()
    if len(data) > maximo:
        return None, f"El archivo pesa {len(data) / MB:.1f} MB; el máximo es {maximo // MB} MB."
    if not data.startswith(b"%PDF"):
        return None, "El archivo debe ser PDF. Si lo hiciste en Word, usa «Guardar como PDF»."
    try:
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(data))
        texto = norm(" ".join((p.extract_text() or "") for p in r.pages))
        paginas = r.pages
    except Exception:
        return None, "No se pudo leer el PDF. Vuelve a exportarlo desde tu procesador de textos."
    return (data, texto, paginas), None


def faltantes(texto, secciones):
    return [nom for clave, nom in secciones if clave not in texto]


def membretada_ok(paginas):
    """Regla de formato frecuente en las devoluciones: la hoja membretada va solo en la portada."""
    if len(paginas) < 2:
        return True
    marcas = sum(1 for p in paginas[1:] if "hoja membretada" in norm(p.extract_text() or ""))
    return marcas == 0


# ------------------------------------------------------------------ seguridad
@app.before_request
def _csrf():
    if request.method in ("POST", "PUT", "DELETE") and request.path.startswith("/api/"):
        if request.headers.get("X-CSRF-Token") != session.get("csrf"):
            return err("La sesión expiró. Recarga la página.", 403)


@app.after_request
def _headers(r):
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"] = "SAMEORIGIN"
    r.headers["Referrer-Policy"] = "same-origin"
    return r


def err(msg, code=400, **kw):
    return jsonify(error=msg, **kw), code


def need(*roles):
    if session.get("rol") not in roles:
        abort(401)


@app.errorhandler(401)
def _401(_):
    return err("Necesitas iniciar sesión.", 401)


@app.errorhandler(403)
def _403(_):
    return err("No tienes permiso para esta acción.", 403)


@app.errorhandler(413)
def _413(_):
    return err("El archivo es demasiado grande.", 413)


def bloqueado(k):
    r = db().execute("SELECT hasta FROM intentos WHERE clave=?", (k,)).fetchone()
    return bool(r and r["hasta"] and dt.datetime.fromisoformat(r["hasta"]) > dt.datetime.now())


def fallo(k):
    r = db().execute("SELECT n FROM intentos WHERE clave=?", (k,)).fetchone()
    n = (r["n"] if r else 0) + 1
    hasta = (dt.datetime.now() + dt.timedelta(minutes=BLOQUEO_MIN)).isoformat(sep=" ") if n >= MAX_INTENTOS else None
    db().execute("INSERT INTO intentos VALUES(?,?,?) ON CONFLICT(clave) DO UPDATE SET n=?,hasta=?", (k, n, hasta, n, hasta))
    db().commit()
    return n


# ------------------------------------------------------------------ rutas generales
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/muestras/<path:f>")
def muestras(f):
    return send_from_directory(os.path.join(BASE, "muestras"), f, as_attachment=True)


@app.route("/api/sesion")
def api_sesion():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    procesar_reloj()
    return jsonify(token=session["csrf"], rol=session.get("rol"), nombre=session.get("nombre"), usuario=session.get("u"),
                   reloj=fmt(iso(now())), reloj_dias=int(ajuste("reloj_dias", "0")))


@app.route("/api/publico")
def api_publico():
    d = db()
    tot = d.execute("SELECT COUNT(*) FROM solicitudes").fetchone()[0]
    acred = d.execute("SELECT COUNT(*) FROM solicitudes WHERE etapa='ACREDITADA'").fetchone()[0]
    proys = d.execute("SELECT COUNT(*) FROM proyectos WHERE avalado=1").fetchone()[0]
    return jsonify(periodo=ajuste("periodo"), solicitudes=tot, acreditadas=acred, proyectos=proys)


@app.route("/api/login", methods=["POST"])
def api_login():
    j = request.get_json(silent=True) or {}
    u, p, rol = (j.get("usuario") or "").strip().lower(), j.get("clave") or "", j.get("rol")
    k = "login:" + u
    if bloqueado(k):
        return err(f"Demasiados intentos. Espera {BLOQUEO_MIN} minutos.", 429)
    r = db().execute("SELECT * FROM usuarios WHERE usuario=?", (u,)).fetchone()
    ok_rol = r and (r["rol"] == rol or (rol == "consulta" and r["rol"] == "consulta"))
    if not r or not ok_rol or not check_password_hash(r["clave_hash"], p):
        n = fallo(k)
        return err("Usuario o contraseña incorrectos." + (f" Te quedan {MAX_INTENTOS - n} intentos." if n < MAX_INTENTOS else ""), 401, intentos=n)
    db().execute("DELETE FROM intentos WHERE clave=?", (k,))
    session.update(u=r["usuario"], rol=r["rol"], nombre=r["nombre"], ref=r["ref"])
    audit("Inicio de sesión")
    db().commit()
    return jsonify(ok=True, rol=r["rol"], nombre=r["nombre"])


@app.route("/api/logout", methods=["POST"])
def api_logout():
    csrf = session.get("csrf")
    session.clear()
    session["csrf"] = csrf
    return jsonify(ok=True)


def mis_correos(direccion, n=6):
    return [dict(r) for r in db().execute("SELECT * FROM correos WHERE para=? ORDER BY id DESC LIMIT ?", (direccion, n)).fetchall()]


def timeline(s):
    ev = [dict(e) for e in db().execute("SELECT etapa,fecha,detalle FROM eventos WHERE solicitud_id=? ORDER BY id", (s["id"],)).fetchall()]
    hechos = {e["etapa"]: e for e in ev}
    pasos = []
    for k, nombre in ETAPAS:
        e = hechos.get(k)
        pasos.append({"etapa": k, "nombre": nombre, "hecho": bool(e), "fecha": fmt(e["fecha"]) if e else "", "hora": e["fecha"][11:16] if e else "",
                      "detalle": e["detalle"] if e else ""})
    if s["etapa"] in ("NO_ACREDITADA", "RECHAZADA_EMPRESA"):
        e = hechos.get(s["etapa"])
        pasos.append({"etapa": s["etapa"], "nombre": ETAPA_TXT[s["etapa"]], "hecho": True, "fecha": fmt(e["fecha"]) if e else "", "detalle": e["detalle"] if e else "", "error": True})
    return pasos


def siguiente_paso(s, f):
    e = s["etapa"]
    if s["en_espera"]:
        return "Tu solicitud está registrada. Por ahora ningún asesor de tu departamento tiene cupo; en cuanto se libere uno, el sistema te lo asignará y te avisará por correo."
    if e == "CARTA_EMITIDA":
        return "Tu carta ya se envió a la empresa por correo. Cuando la empresa te acepte con su enlace, empezará tu residencia. Mientras, puedes descargar tu carta."
    if e == "EN_RESIDENCIA":
        return f"Asiste a tus asesorías. Tu seguimiento 1 es el {fmt(iso(f['s1']))}; tus asesores lo registran en línea y te avisaremos."
    if e == "SEGUIMIENTO_1":
        return f"Vas muy bien. Tu seguimiento 2 es el {fmt(iso(f['s2']))}."
    if e == "SEGUIMIENTO_2":
        return f"Al terminar tus 500 horas, sube tu reporte final en PDF. Fecha límite: {fmt(iso(f['limite']))}."
    return {
        "SOLICITADA": "Tu solicitud está registrada.",
        "REPORTE_ENTREGADO": "Tu asesor interno está evaluando tu reporte final. En cuanto lo haga, el sistema calcula tu calificación y envía el acta.",
        "ACREDITADA": "¡Felicidades! Tu residencia está acreditada y el acta ya está en Servicios Escolares. No tienes que hacer nada más.",
        "NO_ACREDITADA": "No alcanzaste la calificación mínima de 70. Habla con tu asesor interno sobre los siguientes pasos.",
    }.get(e, "")


# ------------------------------------------------------------------ ALUMNO
def solicitud_activa(control):
    return db().execute("SELECT * FROM solicitudes WHERE control=? AND etapa!='RECHAZADA_EMPRESA' ORDER BY id DESC LIMIT 1", (control,)).fetchone()


@app.route("/api/alumno")
def api_alumno():
    need("alumno")
    procesar_reloj()
    ctl = session["ref"]
    rq = requisitos(ctl)
    s = solicitud_activa(ctl)
    out = {"req": rq, "correos": mis_correos(rq["alumno"]["correo"]), "solicitud": None, "proyectos": []}
    rech = db().execute("SELECT * FROM solicitudes WHERE control=? AND etapa='RECHAZADA_EMPRESA' ORDER BY id DESC LIMIT 1", (ctl,)).fetchone()
    if s:
        p, e = proyecto(s["proyecto_id"])
        a = db().execute("SELECT nombre,correo,depto FROM asesores WHERE id=?", (s["asesor_id"],)).fetchone()
        f = fechas(s)
        out["solicitud"] = {"folio": s["folio"], "etapa": s["etapa"], "etapa_txt": ETAPA_TXT[s["etapa"]], "proyecto": p["titulo"], "empresa": e["nombre"],
                            "asesor": dict(a) if a else None, "carta": s["carta_folio"], "ext": s["ext_nombre"],
                            "timeline": timeline(s), "siguiente": siguiente_paso(s, f), "calificacion": s["calificacion"],
                            "fechas": {k: fmt(iso(v)) for k, v in f.items()},
                            "puede_reporte": s["etapa"] == "SEGUIMIENTO_2", "vencido": bool(f and now() > f["limite"]),
                            "dias_restantes": (f["limite"] - now()).days if f else None,
                            "eval": {t: eval_total(s["id"], t) for t in ("s1", "s2", "rep")}}
    elif rq["cumple"]:
        carrera = rq["alumno"]["carrera"]
        for p in db().execute("SELECT * FROM proyectos WHERE carrera=? AND avalado=1 ORDER BY id", (carrera,)).fetchall():
            e = db().execute("SELECT nombre FROM empresas WHERE id=?", (p["empresa_id"],)).fetchone()
            out["proyectos"].append({"id": p["id"], "titulo": p["titulo"], "empresa": e["nombre"], "descripcion": p["descripcion"],
                                     "libres": p["cupo"] - ocupados(p["id"]), "cupo": p["cupo"]})
        if rech:
            out["aviso"] = "La empresa de tu proyecto anterior no pudo aceptarte" + (f": «{rech['motivo_rechazo']}»" if rech["motivo_rechazo"] else "") + ". Elige otro proyecto."
    return jsonify(out)


@app.route("/api/alumno/solicitar", methods=["POST"])
def api_solicitar():
    """CU-03 + CU-04: elige proyecto y sube el reporte preliminar; el sistema hace el resto."""
    need("alumno")
    ctl = session["ref"]
    rq = requisitos(ctl)
    if not rq["cumple"]:
        return err("Aún no cumples los requisitos para solicitar tu residencia.", 409)
    if solicitud_activa(ctl):
        return err("Ya tienes una solicitud en curso.", 409)
    try:
        pid = int(request.form.get("proyecto_id", "0"))
    except ValueError:
        return err("Elige un proyecto.")
    p = db().execute("SELECT * FROM proyectos WHERE id=? AND avalado=1", (pid,)).fetchone()
    if not p or p["carrera"] != rq["alumno"]["carrera"]:
        return err("Ese proyecto no está disponible para tu carrera.")
    if ocupados(pid) >= p["cupo"]:
        return err("Ese proyecto ya no tiene lugares. Elige otro.", 409)
    f = request.files.get("archivo")
    if not f or not f.filename:
        return err("Adjunta tu reporte preliminar en PDF.")
    leido, e = leer_pdf(f, 5 * MB)
    motivo = e
    if not e:
        data, texto, paginas = leido
        falt = faltantes(texto, SECC_PRELIM)
        if falt:
            motivo = "A tu reporte preliminar le falta: " + ", ".join(falt) + ". Agrégalo y vuelve a subirlo."
        elif not membretada_ok(paginas):
            motivo = "La hoja membretada debe ir solo en la portada; tu archivo la tiene en otras páginas. Corrígelo y vuelve a subirlo."
    if motivo:
        db().execute("INSERT INTO rechazos(control,tipo,motivo,fecha) VALUES(?,?,?,?)", (ctl, "preliminar", motivo, iso(now())))
        db().commit()
        return err(motivo, 422, validacion=True)
    d = db()
    sid = d.execute("INSERT INTO solicitudes(folio,control,proyecto_id,etapa,token,creado) VALUES(?,?,?,?,?,?)",
                    ("TMP", ctl, pid, "SOLICITADA", secrets.token_urlsafe(18), iso(now()))).lastrowid
    folio = "RES-%s-%04d" % (now().year, sid)
    d.execute("UPDATE solicitudes SET folio=? WHERE id=?", (folio, sid))
    ruta = os.path.join(UPLOADS, f"{folio}_preliminar.pdf")
    with open(ruta, "wb") as fh:
        fh.write(data)
    d.execute("INSERT INTO documentos(solicitud_id,control,tipo,nombre,ruta,fecha) VALUES(?,?,?,?,?,?)", (sid, ctl, "preliminar", f.filename, ruta, iso(now())))
    evento(sid, "SOLICITADA", f"Reporte preliminar validado ({len(paginas)} páginas)")
    audit(f"Solicitud {folio} registrada")
    if asignar_asesor(sid):
        emitir_carta(sid)
    d.commit()
    return jsonify(ok=True, folio=folio)


@app.route("/api/alumno/reporte", methods=["POST"])
def api_reporte():
    need("alumno")
    s = solicitud_activa(session["ref"])
    if not s or s["etapa"] != "SEGUIMIENTO_2":
        return err("Podrás subir tu reporte final después del seguimiento 2.", 409)
    f = fechas(s)
    if now() > f["limite"]:
        return err(f"El plazo de 15 días naturales venció el {fmt(iso(f['limite']))} (RN-06). Habla con tu asesor interno.", 409)
    fl = request.files.get("archivo")
    if not fl or not fl.filename:
        return err("Adjunta tu reporte final en PDF.")
    leido, e = leer_pdf(fl, 20 * MB)
    if not e:
        data, texto, paginas = leido
        falt = faltantes(texto, SECC_FINAL)
        if falt:
            e = "A tu reporte final le falta: " + ", ".join(falt) + ". Agrégalo y vuelve a subirlo."
    if e:
        db().execute("INSERT INTO rechazos(control,tipo,motivo,fecha) VALUES(?,?,?,?)", (s["control"], "final", e, iso(now())))
        db().commit()
        return err(e, 422, validacion=True)
    ruta = os.path.join(UPLOADS, f"{s['folio']}_final.pdf")
    with open(ruta, "wb") as fh:
        fh.write(data)
    db().execute("INSERT INTO documentos(solicitud_id,control,tipo,nombre,ruta,fecha) VALUES(?,?,?,?,?,?)", (s["id"], s["control"], "final", fl.filename, ruta, iso(now())))
    evento(s["id"], "REPORTE_ENTREGADO", f"{len(paginas)} páginas; quedaban {(f['limite'] - now()).days} días del plazo")
    a = db().execute("SELECT correo FROM asesores WHERE id=?", (s["asesor_id"],)).fetchone()
    correo(a["correo"], f"Reporte final listo para evaluar · {s['folio']}", "El residente entregó su reporte final. Evalúelo en ResiTrack (Anexo XXX).", "#/asesor")
    audit(f"Reporte final de {s['folio']} recibido")
    db().commit()
    return jsonify(ok=True)


@app.route("/api/alumno/carta.pdf")
def api_carta():
    need("alumno")
    s = solicitud_activa(session["ref"])
    if not s or not s["carta_folio"]:
        abort(404)
    return send_file(io.BytesIO(pdf_carta(s)), mimetype="application/pdf", download_name=f"{s['carta_folio']}.pdf")


@app.route("/api/alumno/acta.pdf")
def api_acta():
    need("alumno")
    s = db().execute("SELECT * FROM solicitudes WHERE control=? AND etapa IN ('ACREDITADA','NO_ACREDITADA')", (session["ref"],)).fetchone()
    if not s:
        abort(404)
    return send_file(io.BytesIO(pdf_acta(s)), mimetype="application/pdf", download_name=f"acta_{s['folio']}.pdf")


# ------------------------------------------------------------------ EMPRESA (enlace seguro, sin cuenta)
def por_token(tok):
    s = db().execute("SELECT * FROM solicitudes WHERE token=?", (tok,)).fetchone()
    if not s:
        abort(404)
    f = fechas(s)
    if f and now() > f["limite"] + dt.timedelta(days=30):
        abort(410)
    return s


@app.errorhandler(404)
def _404(e):
    if request.path.startswith("/api/"):
        return err("No encontramos lo que buscas. Revisa el enlace.", 404)
    return render_template("index.html"), 200


@app.errorhandler(410)
def _410(_):
    return err("Este enlace ya caducó.", 410)


@app.route("/api/empresa/<tok>")
def api_empresa(tok):
    procesar_reloj()
    s = por_token(tok)
    p, e = proyecto(s["proyecto_id"])
    a = db().execute("SELECT nombre,carrera FROM sii WHERE control=?", (s["control"],)).fetchone()
    pend = None
    if s["etapa"] == "EN_RESIDENCIA" and "externo" not in eval_total(s["id"], "s1"):
        pend = "s1"
    elif s["etapa"] == "SEGUIMIENTO_1" and "externo" not in eval_total(s["id"], "s2"):
        pend = "s2"
    f = fechas(s)
    return jsonify(folio=s["folio"], etapa=s["etapa"], etapa_txt=ETAPA_TXT[s["etapa"]], alumno=a["nombre"], carrera=a["carrera"],
                   proyecto=p["titulo"], empresa=e["nombre"], carta=s["carta_folio"], ext=s["ext_nombre"],
                   pendiente=pend, criterios=CRIT_SEG, fechas={k: fmt(iso(v)) for k, v in f.items()},
                   hechas={t: ("externo" in eval_total(s["id"], t)) for t in ("s1", "s2")})


@app.route("/api/empresa/<tok>/aceptar", methods=["POST"])
def api_empresa_aceptar(tok):
    s = por_token(tok)
    if s["etapa"] != "CARTA_EMITIDA":
        return err("Esta solicitud ya fue respondida.", 409)
    j = request.get_json(silent=True) or {}
    if j.get("acepta") is False:
        motivo = (j.get("motivo") or "").strip()[:300]
        db().execute("UPDATE solicitudes SET motivo_rechazo=? WHERE id=?", (motivo, s["id"]))
        evento(s["id"], "RECHAZADA_EMPRESA", motivo or "Sin motivo")
        correo(alumno_correo(s["control"]), "La empresa no pudo aceptarte", "Tu lugar se liberó. Entra a ResiTrack y elige otro proyecto del banco.", "#/alumno")
        audit(f"Empresa rechazó {s['folio']}", "empresa")
        db().commit()
        return jsonify(ok=True)
    nombre, cargo, mail = (j.get("nombre") or "").strip(), (j.get("cargo") or "").strip(), (j.get("correo") or "").strip()
    try:
        inicio = dt.date.fromisoformat(j.get("inicio") or "")
    except ValueError:
        return err("Escribe la fecha de inicio.")
    if len(nombre) < 3 or len(cargo) < 2:
        return err("Escribe el nombre y el cargo del asesor externo.")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", mail):
        return err("Escribe un correo válido para el asesor externo.")
    fin = inicio + dt.timedelta(days=120)
    db().execute("UPDATE solicitudes SET ext_nombre=?,ext_cargo=?,ext_correo=?,inicio=?,fin=? WHERE id=?",
                 (nombre, cargo, mail, inicio.isoformat(), fin.isoformat(), s["id"]))
    evento(s["id"], "EN_RESIDENCIA", f"Asesor externo: {nombre}, {cargo}. Inicio {fmt(inicio.isoformat())}; recordatorios programados")
    correo(alumno_correo(s["control"]), "¡La empresa te aceptó!", f"Tu residencia inicia el {fmt(inicio.isoformat())}. Tu asesor externo es {nombre}.", "#/alumno")
    correo(mail, "Bienvenido como asesor externo", "Use su enlace seguro para registrar los seguimientos. Le enviaremos recordatorios.", f"#/empresa/{tok}")
    audit(f"Empresa aceptó {s['folio']}", "empresa")
    db().commit()
    return jsonify(ok=True)


def validar_puntos(puntos, crit):
    if not isinstance(puntos, list) or len(puntos) != len(crit):
        return None, "Califica todos los criterios."
    out = []
    for (nombre, maximo), v in zip(crit, puntos):
        try:
            n = int(v)
        except (TypeError, ValueError):
            return None, f"«{nombre}»: escribe un número entero."
        if not 0 <= n <= maximo or str(v).strip() != str(n):
            return None, f"«{nombre}»: el valor debe estar entre 0 y {maximo}."
        out.append(n)
    return out, None


def registrar_eval(s, tipo, evaluador, puntos):
    crit = CRIT_REP if tipo == "rep" else CRIT_SEG
    pts, e = validar_puntos(puntos, crit)
    if e:
        return err(e)
    try:
        db().execute("INSERT INTO evaluaciones(solicitud_id,tipo,evaluador,puntos,total,fecha) VALUES(?,?,?,?,?,?)",
                     (s["id"], tipo, evaluador, json.dumps(pts), sum(pts), iso(now())))
    except sqlite3.IntegrityError:
        return err("Esta evaluación ya fue registrada.", 409)
    audit(f"Evaluación {tipo} ({evaluador}) de {s['folio']}: {sum(pts)}", evaluador if evaluador == "externo" else None)
    if tipo in ("s1", "s2"):
        avanzar_seguimiento(s["id"], tipo)
    else:
        cerrar_residencia(s["id"])
    db().commit()
    return jsonify(ok=True, total=sum(pts))


@app.route("/api/empresa/<tok>/evaluar", methods=["POST"])
def api_empresa_eval(tok):
    s = por_token(tok)
    j = request.get_json(silent=True) or {}
    tipo = j.get("tipo")
    esperada = "EN_RESIDENCIA" if tipo == "s1" else "SEGUIMIENTO_1" if tipo == "s2" else None
    if s["etapa"] != esperada:
        return err("Esta evaluación no está disponible ahora.", 409)
    return registrar_eval(s, tipo, "externo", j.get("puntos"))


# ------------------------------------------------------------------ ASESOR INTERNO
@app.route("/api/asesor")
def api_asesor():
    need("asesor")
    procesar_reloj()
    a = db().execute("SELECT * FROM asesores WHERE usuario=?", (session["u"],)).fetchone()
    res = []
    for s in db().execute("SELECT * FROM solicitudes WHERE asesor_id=? ORDER BY id", (a["id"],)).fetchall():
        x = db().execute("SELECT nombre,carrera FROM sii WHERE control=?", (s["control"],)).fetchone()
        p, e = proyecto(s["proyecto_id"])
        f = fechas(s)
        ev = {t: eval_total(s["id"], t) for t in ("s1", "s2", "rep")}
        pend = None
        if s["etapa"] == "EN_RESIDENCIA" and "interno" not in ev["s1"]:
            pend = "s1"
        elif s["etapa"] == "SEGUIMIENTO_1" and "interno" not in ev["s2"]:
            pend = "s2"
        elif s["etapa"] == "REPORTE_ENTREGADO":
            pend = "rep"
        venc = None
        if pend in ("s1", "s2") and f:
            venc = (f[pend] - now()).days
        res.append({"id": s["id"], "folio": s["folio"], "alumno": x["nombre"], "carrera": x["carrera"], "proyecto": p["titulo"], "empresa": e["nombre"],
                    "etapa": s["etapa"], "etapa_txt": ETAPA_TXT[s["etapa"]], "pendiente": pend, "vence_en": venc, "eval": ev,
                    "calificacion": s["calificacion"], "fechas": {k: fmt(iso(v)) for k, v in f.items()}})
    return jsonify(asesor=dict(a), carga=carga(a["id"]), residentes=res, criterios={"seg": CRIT_SEG, "rep": CRIT_REP},
                   correos=mis_correos(a["correo"]))


@app.route("/api/asesor/evaluar", methods=["POST"])
def api_asesor_eval():
    need("asesor")
    j = request.get_json(silent=True) or {}
    a = db().execute("SELECT * FROM asesores WHERE usuario=?", (session["u"],)).fetchone()
    s = db().execute("SELECT * FROM solicitudes WHERE id=? AND asesor_id=?", (j.get("id"), a["id"])).fetchone()
    if not s:
        abort(403)
    tipo = j.get("tipo")
    esperada = {"s1": "EN_RESIDENCIA", "s2": "SEGUIMIENTO_1", "rep": "REPORTE_ENTREGADO"}.get(tipo)
    if s["etapa"] != esperada:
        return err("Esta evaluación no está disponible ahora.", 409)
    return registrar_eval(s, tipo, "interno", j.get("puntos"))


@app.route("/api/asesor/preliminar/<int:sid>.pdf")
def api_asesor_doc(sid):
    need("asesor")
    a = db().execute("SELECT id FROM asesores WHERE usuario=?", (session["u"],)).fetchone()
    tipo = request.args.get("tipo", "preliminar")
    d = db().execute("SELECT d.* FROM documentos d JOIN solicitudes s ON s.id=d.solicitud_id WHERE s.id=? AND s.asesor_id=? AND d.tipo=? ORDER BY d.id DESC",
                     (sid, a["id"], tipo)).fetchone()
    if not d or not os.path.exists(d["ruta"]):
        abort(404)
    return send_file(d["ruta"], mimetype="application/pdf", download_name=d["nombre"])


# ------------------------------------------------------------------ CONSULTA (DEP · Jefatura · Escolares) — solo lectura
def indicadores():
    d = db()
    sols = d.execute("SELECT * FROM solicitudes").fetchall()
    tiempos = []
    for s in sols:
        a = d.execute("SELECT fecha FROM eventos WHERE solicitud_id=? AND etapa='SOLICITADA'", (s["id"],)).fetchone()
        b = d.execute("SELECT fecha FROM eventos WHERE solicitud_id=? AND etapa='CARTA_EMITIDA'", (s["id"],)).fetchone()
        if a and b:
            tiempos.append((pdate(b["fecha"]) - pdate(a["fecha"])).total_seconds())
    rech = d.execute("SELECT COUNT(*) FROM rechazos").fetchone()[0]
    docs = d.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
    hoy = now()
    vencidos = 0
    for s in d.execute("SELECT * FROM solicitudes WHERE etapa IN ('EN_RESIDENCIA','SEGUIMIENTO_1')").fetchall():
        f = fechas(s)
        lim = f["s1"] if s["etapa"] == "EN_RESIDENCIA" else f["s2"]
        if hoy > lim:
            vencidos += 1
    por_etapa = {k: 0 for k in list(ETAPA_TXT)}
    for s in sols:
        por_etapa[s["etapa"]] += 1
    prom = sum(tiempos) / len(tiempos) if tiempos else 0
    return {"activos": sum(1 for s in sols if s["etapa"] not in CERRADAS), "total": len(sols),
            "acreditadas": por_etapa["ACREDITADA"], "tiempo_carta_seg": round(prom, 1),
            "tiempo_carta_txt": "al instante (< 1 min)" if prom < 60 else f"{prom / 3600:.1f} h",
            "corregidos_antes": rech, "devueltos_personal": 0, "documentos": docs, "hojas": 0,
            "tareas_personal": 0, "vencidos": vencidos, "en_espera": d.execute("SELECT COUNT(*) FROM solicitudes WHERE en_espera=1").fetchone()[0],
            "por_etapa": [{"etapa": k, "nombre": v, "n": por_etapa[k]} for k, v in ETAPA_TXT.items()],
            "correos": d.execute("SELECT COUNT(*) FROM correos").fetchone()[0]}


@app.route("/api/consulta")
def api_consulta():
    need("consulta")
    procesar_reloj()
    d = db()
    filas = []
    for s in d.execute("SELECT * FROM solicitudes ORDER BY id DESC").fetchall():
        x = d.execute("SELECT nombre,carrera FROM sii WHERE control=?", (s["control"],)).fetchone()
        p, e = proyecto(s["proyecto_id"])
        a = d.execute("SELECT nombre FROM asesores WHERE id=?", (s["asesor_id"],)).fetchone()
        filas.append({"folio": s["folio"], "control": s["control"], "alumno": x["nombre"], "carrera": x["carrera"], "proyecto": p["titulo"],
                      "empresa": e["nombre"], "asesor": a["nombre"] if a else "En espera", "etapa": s["etapa"], "etapa_txt": ETAPA_TXT[s["etapa"]],
                      "creado": fmt(s["creado"]), "calificacion": s["calificacion"]})
    ases = [{"nombre": a["nombre"], "depto": a["depto"], "carga": carga(a["id"]), "tope": a["tope"]} for a in d.execute("SELECT * FROM asesores ORDER BY depto,nombre")]
    actas = [dict(r) for r in d.execute("SELECT a.folio,a.control,a.calificacion,a.fecha,s.nombre FROM sii_actas a JOIN sii s ON s.control=a.control ORDER BY a.id DESC")]
    bit = [dict(r) for r in d.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT 40")]
    return jsonify(kpi=indicadores(), solicitudes=filas, asesores=ases, actas=actas, bitacora=bit, rol_txt=session.get("nombre"))


@app.route("/api/consulta/excel")
def api_excel():
    need("consulta")
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Solicitudes"
    hdr = ["Folio", "No. control", "Alumno", "Carrera", "Proyecto", "Empresa", "Asesor interno", "Etapa", "Fecha", "Calificación"]
    ws.append(hdr)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="12355B")
    for f in api_consulta().get_json()["solicitudes"]:
        ws.append([f["folio"], f["control"], f["alumno"], f["carrera"], f["proyecto"], f["empresa"], f["asesor"], f["etapa_txt"], f["creado"], f["calificacion"]])
    for col, w in zip("ABCDEFGHIJ", [16, 12, 24, 30, 40, 30, 28, 28, 14, 12]):
        ws.column_dimensions[col].width = w
    k = indicadores()
    ws2 = wb.create_sheet("Indicadores")
    for r in [("Residentes activos", k["activos"]), ("Tiempo solicitud → carta", k["tiempo_carta_txt"]),
              ("Documentos corregidos por el alumno antes de enviar", k["corregidos_antes"]), ("Documentos devueltos por el personal", 0),
              ("Hojas impresas", 0), ("Tareas manuales del personal", 0), ("Seguimientos vencidos", k["vencidos"])]:
        ws2.append(r)
    ws2.column_dimensions["A"].width = 52
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    audit("Descarga de reporte Excel")
    db().commit()
    return send_file(bio, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", download_name="reporte_residencias.xlsx")


# ------------------------------------------------------------------ verificación pública de documentos (QR)
@app.route("/api/verificar/<folio>")
def api_verificar(folio):
    s = db().execute("SELECT * FROM solicitudes WHERE carta_folio=?", (folio.upper(),)).fetchone()
    if not s:
        return jsonify(valido=False)
    p, e = proyecto(s["proyecto_id"])
    a = db().execute("SELECT nombre,carrera FROM sii WHERE control=?", (s["control"],)).fetchone()
    partes = a["nombre"].split()
    corto = partes[0] + " " + " ".join(x[0] + "." for x in partes[1:])
    ev = db().execute("SELECT fecha FROM eventos WHERE solicitud_id=? AND etapa='CARTA_EMITIDA'", (s["id"],)).fetchone()
    return jsonify(valido=True, folio=folio.upper(), alumno=corto, carrera=a["carrera"], proyecto=p["titulo"], empresa=e["nombre"], fecha=fmt(ev["fecha"]) if ev else "")


# ------------------------------------------------------------------ demostración (no forma parte del sistema real)
@app.route("/api/demo")
def api_demo():
    return jsonify(correos=[dict(r) for r in db().execute("SELECT * FROM correos ORDER BY id DESC LIMIT 60")],
                   reloj=fmt(iso(now())), reloj_dias=int(ajuste("reloj_dias", "0")),
                   enlaces=[{"folio": r["folio"], "token": r["token"], "etapa": ETAPA_TXT[r["etapa"]], "empresa": proyecto(r["proyecto_id"])[1]["nombre"]}
                            for r in db().execute("SELECT * FROM solicitudes WHERE ext_correo IS NOT NULL OR etapa='CARTA_EMITIDA' ORDER BY id")])


@app.route("/api/demo/reloj", methods=["POST"])
def api_demo_reloj():
    j = request.get_json(silent=True) or {}
    dias = 0 if j.get("reiniciar") else int(ajuste("reloj_dias", "0")) + max(0, min(int(j.get("dias", 0)), 120))
    set_ajuste("reloj_dias", dias)
    db().commit()
    procesar_reloj()
    return jsonify(ok=True, reloj=fmt(iso(now())), reloj_dias=dias)


@app.route("/api/demo/reiniciar", methods=["POST"])
def api_demo_reiniciar():
    db().close()
    g.pop("db", None)
    init_db(reset=True)
    csrf = session.get("csrf")
    session.clear()
    session["csrf"] = csrf
    return jsonify(ok=True)


# ------------------------------------------------------------------ PDFs
def _pdf_base(titulo):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    bio = io.BytesIO()
    c = canvas.Canvas(bio, pagesize=letter)
    c.setTitle(titulo)
    W, H = letter
    c.setFillColorRGB(0.07, 0.21, 0.36)
    c.rect(0, H - 70, W, 70, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(50, H - 42, "Instituto Tecnológico de Matehuala (documento simulado)")
    c.setFont("Helvetica", 9)
    c.drawString(50, H - 58, "División de Estudios Profesionales · Generado automáticamente por ResiTrack")
    c.setFillColorRGB(0.85, 0.39, 0.12)
    c.rect(0, H - 74, W, 4, fill=1, stroke=0)
    c.setFillColorRGB(0.12, 0.16, 0.2)
    return c, bio, W, H


def _qr(c, url, x, y, size=95):
    import qrcode
    from reportlab.lib.utils import ImageReader
    img = qrcode.make(url)
    b = io.BytesIO()
    img.save(b, format="PNG")
    b.seek(0)
    c.drawImage(ImageReader(b), x, y, size, size)


def _parrafo(c, texto, x, y, ancho=95, lead=16, font=("Helvetica", 11)):
    import textwrap
    c.setFont(*font)
    for linea in textwrap.wrap(texto, ancho):
        c.drawString(x, y, linea)
        y -= lead
    return y


def pdf_carta(s):
    p, e = proyecto(s["proyecto_id"])
    a = db().execute("SELECT * FROM sii WHERE control=?", (s["control"],)).fetchone()
    ase = db().execute("SELECT nombre FROM asesores WHERE id=?", (s["asesor_id"],)).fetchone()
    ev = db().execute("SELECT fecha FROM eventos WHERE solicitud_id=? AND etapa='CARTA_EMITIDA'", (s["id"],)).fetchone()
    c, bio, W, H = _pdf_base("Carta de presentación " + s["carta_folio"])
    y = H - 120
    c.setFont("Helvetica", 11)
    c.drawRightString(W - 50, y, f"Matehuala, S.L.P., {fmt(ev['fecha'])}")
    c.drawRightString(W - 50, y - 16, f"Folio: {s['carta_folio']}")
    y -= 60
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, e["nombre"].upper())
    c.setFont("Helvetica", 11)
    c.drawString(50, y - 16, "PRESENTE")
    y -= 50
    y = _parrafo(c, f"Por medio de la presente, el Instituto Tecnológico de Matehuala presenta a {a['nombre']}, con número de control "
                    f"{a['control']}, estudiante de {a['carrera']}, quien desarrollará el proyecto «{p['titulo']}» como Residencia "
                    f"Profesional, con una duración de 4 a 6 meses y un total de 500 horas.", 50, y)
    y -= 10
    y = _parrafo(c, f"Su asesor interno será {ase['nombre']}. Le solicitamos registrar la aceptación del residente y los datos de su "
                    f"asesor externo con el enlace seguro que recibió por correo electrónico.", 50, y)
    y -= 10
    _parrafo(c, "Agradecemos su apoyo a la formación profesional de nuestros estudiantes.", 50, y)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 230, "ATENTAMENTE")
    c.setFont("Helvetica", 10)
    c.drawString(50, 212, "División de Estudios Profesionales")
    c.setFont("Courier", 8)
    c.drawString(50, 190, "Firma electrónica (simulada): " + secrets.token_hex(12).upper())
    url = (request.host_url.rstrip("/") if request else "") + f"/#/verificar/{s['carta_folio']}"
    _qr(c, url, W - 150, 150)
    c.setFont("Helvetica", 8)
    c.drawRightString(W - 50, 140, "Escanee para verificar la autenticidad")
    c.setFillColorRGB(0.85, 0.39, 0.12)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W / 2, 40, "PROTOTIPO ACADÉMICO · DATOS SIMULADOS · SIN VALIDEZ OFICIAL")
    c.showPage()
    c.save()
    return bio.getvalue()


def pdf_acta(s):
    a = db().execute("SELECT * FROM sii WHERE control=?", (s["control"],)).fetchone()
    acta = db().execute("SELECT * FROM sii_actas WHERE solicitud_id=?", (s["id"],)).fetchone()
    s1, s2, rep = eval_total(s["id"], "s1"), eval_total(s["id"], "s2"), eval_total(s["id"], "rep")
    c, bio, W, H = _pdf_base("Acta " + acta["folio"])
    y = H - 120
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Acta de calificación de Residencia Profesional")
    c.setFont("Helvetica", 11)
    c.drawString(50, y - 22, f"Folio {acta['folio']} · enviada a Servicios Escolares (SII) el {fmt(acta['fecha'])}")
    y -= 70
    filas = [("Alumno", a["nombre"]), ("Número de control", a["control"]), ("Carrera", a["carrera"]),
             ("Seguimiento 1 (10 %)", f"{(s1['interno'] + s1['externo']) / 2:g}"), ("Seguimiento 2 (10 %)", f"{(s2['interno'] + s2['externo']) / 2:g}"),
             ("Reporte final (80 %)", str(rep["interno"])), ("Calificación final", str(s["calificacion"])),
             ("Resultado", "ACREDITADA" if s["calificacion"] >= 70 else "NO ACREDITADA")]
    for k, v in filas:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(60, y, k)
        c.setFont("Helvetica", 11)
        c.drawString(260, y, v)
        c.setStrokeColorRGB(0.85, 0.82, 0.78)
        c.line(55, y - 6, W - 55, y - 6)
        y -= 26
    c.setFillColorRGB(0.85, 0.39, 0.12)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W / 2, 40, "PROTOTIPO ACADÉMICO · DATOS SIMULADOS · SIN VALIDEZ OFICIAL")
    c.showPage()
    c.save()
    return bio.getvalue()


# ------------------------------------------------------------------ datos simulados
def seed():
    d = db()
    set_ajuste("periodo", "Enero–Junio 2027")
    set_ajuste("reloj_dias", "0")
    for u, p, r, n, ref in [("dep", "Dep-2026", "consulta", "División de Estudios Profesionales", "DEP"),
                            ("jefatura", "Jefatura-2026", "consulta", "Jefatura de Sistemas y Computación", "JEF"),
                            ("escolares", "Escolares-2026", "consulta", "Servicios Escolares", "ESC")]:
        d.execute("INSERT INTO usuarios VALUES(?,?,?,?,?)", (u, generate_password_hash(p, HASH), r, n, ref))
    alumnos = [  # control, nombre, carrera, semestre, créditos, servicio social, act. comp.
        ("22000101", "Ana Sofía Ledezma", "Ing. en Sistemas Computacionales", 9, 86, 1, 5),
        ("22000102", "Bruno Esquivel", "Ing. en Sistemas Computacionales", 9, 88, 1, 4),
        ("22000103", "Carla Medrano", "Ing. Industrial", 9, 91, 1, 5),
        ("22000104", "Daniel Robledo", "Ing. Industrial", 10, 95, 1, 5),
        ("22000105", "Elena Quintero", "Ing. en Sistemas Computacionales", 9, 84, 1, 5),
        ("22000106", "Fernando Ibarra", "Ing. en Gestión Empresarial", 9, 82, 1, 5),
        ("22000107", "Gabriela Treviño", "Ing. Civil", 9, 79, 1, 5),
        ("22000108", "Héctor Saucedo", "Ing. Civil", 9, 90, 1, 5),
        ("22000109", "Isabel Zamarripa", "Contador Público", 9, 87, 0, 5),
        ("22000110", "Jorge Castañón", "Ing. Industrial", 9, 89, 1, 5),
    ]
    for ctl, n, car, sem, cr, ss, ac in alumnos:
        mail = f"l{ctl}@alumnos.ejemplo.mx"
        d.execute("INSERT INTO sii VALUES(?,?,?,?,?,?,?,?)", (ctl, n, car, sem, cr, ss, ac, mail))
        d.execute("INSERT INTO usuarios VALUES(?,?,?,?,?)", (ctl, generate_password_hash("Resi-2026", HASH), "alumno", n, ctl))
    asesores = [("asesor.sistemas", "M.C. Ricardo Ibarra", "Sistemas y Computación", 6), ("asesor.sistemas2", "Ing. Paola Garza", "Sistemas y Computación", 6),
                ("asesor.industrial", "Ing. Laura Montemayor", "Ingeniería Industrial", 6), ("asesor.industrial2", "M.I. Óscar Leyva", "Ingeniería Industrial", 6),
                ("asesor.civil", "Ing. Hugo Salazar", "Ciencias de la Tierra", 1), ("asesor.admin", "M.A. Claudia Ríos", "Ciencias Económico-Administrativas", 6)]
    for i, (u, n, dep, tope) in enumerate(asesores, 1):
        d.execute("INSERT INTO asesores(id,usuario,nombre,depto,correo,tope) VALUES(?,?,?,?,?,?)", (i, u, n, dep, u + "@docentes.ejemplo.mx", tope))
        d.execute("INSERT INTO usuarios VALUES(?,?,?,?,?)", (u, generate_password_hash("Asesor-2026", HASH), "asesor", n, str(i)))
    empresas = [("Minera del Altiplano (ficticia)", "MAL010101AAA"), ("Ensambles Matehuala (ficticia)", "EMA020202BBB"),
                ("Obras Públicas Municipales (ficticia)", "OPM030303CCC"), ("Dulces La Biznaga (ficticia)", "DLB040404DDD"),
                ("Clínica Del Valle (ficticia)", "CDV050505EEE"), ("Transportes Norteños (ficticia)", "TNO060606FFF")]
    for i, (n, rfc) in enumerate(empresas, 1):
        d.execute("INSERT INTO empresas VALUES(?,?,?,?)", (i, n, rfc, f"residencias@empresa{i}.ejemplo.mx"))
    proyectos = [
        ("Sistema de inventario para almacén de refacciones", 1, "Ing. en Sistemas Computacionales", 2, "Aplicación web para controlar entradas y salidas del almacén."),
        ("Portal de citas para pacientes", 5, "Ing. en Sistemas Computacionales", 1, "Agenda en línea con recordatorios por correo."),
        ("Tablero de indicadores de producción", 2, "Ing. en Sistemas Computacionales", 2, "Dashboard con datos de la línea de ensamble."),
        ("Balanceo de línea en área de ensamble", 2, "Ing. Industrial", 2, "Reducir tiempos muertos en la línea principal."),
        ("Programa de mantenimiento preventivo", 1, "Ing. Industrial", 2, "Plan anual de mantenimiento para equipo pesado."),
        ("Supervisión de pavimentación urbana", 3, "Ing. Civil", 2, "Control de calidad y avance de obra."),
        ("Plan de mercadotecnia digital para PyME", 4, "Ing. en Gestión Empresarial", 2, "Estrategia en redes sociales y ventas en línea."),
        ("Control interno de cuentas por pagar", 6, "Contador Público", 1, "Procedimiento y conciliaciones mensuales."),
    ]
    for i, (t, emp, car, cupo, desc) in enumerate(proyectos, 1):
        d.execute("INSERT INTO proyectos(id,titulo,empresa_id,carrera,cupo,avalado,descripcion) VALUES(?,?,?,?,?,?,?)", (i, t, emp, car, cupo, 1, desc))

    # Historias simuladas en distintas etapas, para que los reportes tengan datos.
    base = now() - dt.timedelta(days=130)

    def historia(ctl, pid, hasta, inicio_dias=8, puntos=None):
        t0 = base + dt.timedelta(days=len(ctl) % 3)
        sid = d.execute("INSERT INTO solicitudes(folio,control,proyecto_id,etapa,token,creado) VALUES(?,?,?,?,?,?)",
                        ("TMP", ctl, pid, "SOLICITADA", secrets.token_urlsafe(18), iso(t0))).lastrowid
        folio = "RES-%s-%04d" % (t0.year, sid)
        d.execute("UPDATE solicitudes SET folio=? WHERE id=?", (folio, sid))
        d.execute("INSERT INTO documentos(solicitud_id,control,tipo,nombre,ruta,fecha) VALUES(?,?,?,?,?,?)",
                  (sid, ctl, "preliminar", "reporte_preliminar.pdf", os.path.join(BASE, "muestras", "reporte_preliminar_correcto.pdf"), iso(t0)))
        evento(sid, "SOLICITADA", "Reporte preliminar validado", t0)
        s = d.execute("SELECT s.*, x.carrera FROM solicitudes s JOIN sii x ON x.control=s.control WHERE s.id=?", (sid,)).fetchone()
        dep = DEPTO[s["carrera"]]
        a = sorted([(carga(r["id"]), r["id"], r) for r in d.execute("SELECT * FROM asesores WHERE depto=?", (dep,))])[0][2]
        d.execute("UPDATE solicitudes SET asesor_id=? WHERE id=?", (a["id"], sid))
        evento(sid, "ASESOR_ASIGNADO", f"{a['nombre']} ({dep})", t0)
        d.execute("UPDATE solicitudes SET carta_folio=? WHERE id=?", ("RT-%s-%04d" % (t0.year, sid), sid))
        evento(sid, "CARTA_EMITIDA", "Folio con firma electrónica; enviada a la empresa", t0)
        if hasta == "CARTA_EMITIDA":
            return sid
        ini = (t0 + dt.timedelta(days=inicio_dias)).date()
        d.execute("UPDATE solicitudes SET ext_nombre=?,ext_cargo=?,ext_correo=?,inicio=?,fin=? WHERE id=?",
                  ("Ing. Carlos Méndez (ficticio)", "Jefe de área", f"asesor.externo{sid}@empresa.ejemplo.mx", ini.isoformat(), (ini + dt.timedelta(days=120)).isoformat(), sid))
        evento(sid, "EN_RESIDENCIA", "Aceptado por la empresa", dt.datetime.combine(ini, dt.time(10)))
        pts = puntos or {"s1": (92, 90), "s2": (88, 90), "rep": 85}
        for tipo, etapa, dias in (("s1", "SEGUIMIENTO_1", 42), ("s2", "SEGUIMIENTO_2", 84)):
            if ETAPA_IDX[hasta] < ETAPA_IDX[etapa]:
                return sid
            fecha = dt.datetime.combine(ini, dt.time(11)) + dt.timedelta(days=dias)
            for ev_, tot in zip(("interno", "externo"), pts[tipo]):
                d.execute("INSERT INTO evaluaciones(solicitud_id,tipo,evaluador,puntos,total,fecha) VALUES(?,?,?,?,?,?)", (sid, tipo, ev_, "[]", tot, iso(fecha)))
            evento(sid, etapa, f"Calificación del seguimiento: {round(sum(pts[tipo]) / 2)}", fecha)
        if ETAPA_IDX[hasta] >= ETAPA_IDX["REPORTE_ENTREGADO"]:
            f = dt.datetime.combine(ini, dt.time(12)) + dt.timedelta(days=118)
            evento(sid, "REPORTE_ENTREGADO", "Reporte final recibido", f)
        if hasta == "ACREDITADA":
            d.execute("INSERT INTO evaluaciones(solicitud_id,tipo,evaluador,puntos,total,fecha) VALUES(?,?,?,?,?,?)", (sid, "rep", "interno", "[]", pts["rep"], iso(now() - dt.timedelta(days=2))))
            cal = calificacion_final(sid)
            d.execute("UPDATE solicitudes SET calificacion=? WHERE id=?", (cal, sid))
            d.execute("INSERT INTO sii_actas(solicitud_id,control,calificacion,fecha,folio) VALUES(?,?,?,?,?)", (sid, ctl, cal, iso(now() - dt.timedelta(days=2)), "ACTA-%s-%04d" % (now().year, sid)))
            evento(sid, "ACREDITADA", f"Calificación final {cal}; acta enviada a Servicios Escolares (SII)", now() - dt.timedelta(days=2))
        return sid

    historia("22000104", 5, "ACREDITADA")
    historia("22000103", 4, "SEGUIMIENTO_2", inicio_dias=4)
    historia("22000105", 3, "SEGUIMIENTO_1", inicio_dias=40)
    historia("22000110", 4, "EN_RESIDENCIA", inicio_dias=95)
    historia("22000106", 7, "CARTA_EMITIDA")
    historia("22000108", 6, "EN_RESIDENCIA", inicio_dias=100)
    d.execute("INSERT INTO rechazos(control,tipo,motivo,fecha) VALUES(?,?,?,?)", ("22000105", "preliminar", "Hoja membretada en todas las páginas", iso(base)))
    d.execute("INSERT INTO rechazos(control,tipo,motivo,fecha) VALUES(?,?,?,?)", ("22000106", "preliminar", "Faltaba el cronograma", iso(base)))
    d.execute("INSERT INTO auditoria(usuario,accion,fecha) VALUES(?,?,?)", ("sistema", "Datos simulados cargados", iso(now())))


init_db()

if __name__ == "__main__":
    print("\n  ResiTrack listo en  http://localhost:%s\n" % os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
