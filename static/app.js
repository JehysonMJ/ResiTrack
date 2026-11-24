"use strict";
/* ResiTrack · interfaz de una sola página (rutas con #). Prototipo de Altiplano Labs con datos simulados. */
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const app = $("#app");
let CSRF = "", SES = { rol: null };

/* ---------- utilidades ---------- */
function toast(t) { const e = $("#toast"); e.textContent = t; e.classList.add("on"); clearTimeout(toast.t); toast.t = setTimeout(() => e.classList.remove("on"), 3200); }
async function api(url, opt = {}) {
  opt.headers = Object.assign({ "X-CSRF-Token": CSRF }, opt.headers || {});
  if (opt.json !== undefined) { opt.method = opt.method || "POST"; opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(opt.json); }
  let r; try { r = await fetch(url, opt); } catch (e) { return { ok: false, status: 0, data: { error: "No hay conexión con el servidor. ¿Está corriendo app.py?" } }; }
  let data = {}; try { data = await r.json(); } catch (e) { }
  return { ok: r.ok, status: r.status, data };
}
async function sesion() { const r = await api("/api/sesion"); CSRF = r.data.token; SES = r.data; return r.data; }
function modal(html) { $("#modal-card").innerHTML = html; $("#modal").hidden = false; const f = $("#modal-card input,#modal-card button"); f && f.focus(); }
function cerrar() { $("#modal").hidden = true; }
$("#modal").addEventListener("click", e => { if (e.target.id === "modal") cerrar(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") cerrar(); });
function confetti() {
  const cols = ["#D9641E", "#2E8B6E", "#12355B", "#F2A15F", "#F4EDE3"];
  for (let i = 0; i < 70; i++) { const c = document.createElement("i"); c.className = "confetti"; c.style.left = Math.random() * 100 + "vw"; c.style.background = cols[i % 5]; c.style.animationDelay = Math.random() * .8 + "s"; c.style.borderRadius = i % 2 ? "50%" : "2px"; document.body.appendChild(c); setTimeout(() => c.remove(), 3600); }
}
const iniciales = n => (n || "").replace(/^(M\.C\.|Ing\.|M\.A\.|M\.I\.)\s*/, "").split(" ").filter(w => w.length > 2 && w[0] === w[0].toUpperCase()).slice(0, 2).map(x => x[0]).join("");

/* ---------- tema ---------- */
const SUN = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/></svg>';
const MOON = '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>';
function paintTheme() { const d = document.documentElement.dataset.theme === "dark", b = $("#theme"); b.innerHTML = d ? SUN : MOON; b.setAttribute("aria-label", d ? "Cambiar a tema claro" : "Cambiar a tema oscuro"); }
$("#theme").onclick = () => { const n = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = n; try { localStorage.setItem("rt_theme", n); } catch (e) { } paintTheme(); };
paintTheme();

/* ---------- palabras flotantes ---------- */
(function () {
  const w = ["Solicitud", "Carta al instante", "Asesor asignado", "500 horas", "10 créditos", "Seguimiento 1", "Seguimiento 2", "Reporte final", "Acreditada ✓", "Sin filas", "0 hojas", "QR verificado", "Empresa", "Recordatorio"], box = $("#chips");
  w.forEach((t, i) => { const s = document.createElement("span"); s.textContent = t; s.style.left = (3 + (i * 7.3) % 92) + "%"; s.style.animationDuration = (24 + (i * 3) % 14) + "s"; s.style.animationDelay = (-i * 2.6) + "s"; box.appendChild(s); });
})();

/* ---------- escena del altiplano ---------- */
function escena() {
  return `<div class="scene" aria-hidden="true">
  <svg viewBox="0 0 520 340" preserveAspectRatio="xMidYMid slice">
   <g class="stars" fill="#fff">${Array.from({ length: 30 }, (_, i) => `<circle cx="${(i * 97) % 520}" cy="${(i * 53) % 170}" r="${i % 3 ? 1.2 : 1.9}" opacity="${.4 + (i % 5) / 8}"/>`).join("")}</g>
   <g class="sun"><circle cx="370" cy="120" r="46" fill="#D9641E"/><circle cx="370" cy="120" r="70" fill="#D9641E" opacity=".12"/></g>
   <path d="M0 250 L70 190 L130 230 L210 150 L290 215 L360 165 L440 220 L520 180 L520 340 L0 340Z" fill="var(--mt3)" opacity=".55"/>
   <path d="M0 275 L90 215 L160 255 L250 185 L330 245 L410 200 L520 260 L520 340 L0 340Z" fill="var(--mt2)"/>
   <path d="M0 300 L120 250 L200 285 L300 240 L390 280 L520 250 L520 340 L0 340Z" fill="var(--mt1)"/>
   <path class="path-anim" d="M40 300 C110 270 150 300 210 262 S320 250 360 232 S450 215 490 196" fill="none" stroke="#F2A15F" stroke-width="3.5"/>
   <circle class="node" cx="40" cy="300" r="7" fill="#F4EDE3"/><circle class="node" cx="130" cy="282" r="7" fill="#F4EDE3"/><circle class="node" cx="210" cy="262" r="7" fill="#F4EDE3"/>
   <circle class="node" cx="300" cy="246" r="7" fill="#F4EDE3"/><circle class="node" cx="400" cy="226" r="7" fill="#F4EDE3"/><circle class="node" cx="490" cy="196" r="7" fill="#F4EDE3"/>
   <rect x="0" y="330" width="520" height="10" fill="#2E8B6E"/>
  </svg>
  <div class="float f1"><i>📄</i> Carta emitida · al instante</div>
  <div class="float f2"><i>✅</i> Asesor asignado solo</div>
  <div class="float f3"><i>🎓</i> Acta enviada · 86</div></div>`;
}

/* ---------- navegación ---------- */
const RUTAS = { "": vInicio, alumno: vAlumno, asesor: vAsesor, reportes: vReportes, empresa: vEmpresa, verificar: vVerificar, demo: vDemo };
async function router() {
  const h = location.hash.replace(/^#\/?/, ""), [ruta, arg] = h.split("/");
  $$("nav .tab").forEach(t => t.classList.toggle("on", t.dataset.t === (ruta || "inicio") || (ruta === "reportes" && t.dataset.t === "reportes")));
  cerrar();
  const f = RUTAS[ruta] || vInicio;
  app.innerHTML = '<div class="card"><p class="muted">Cargando…</p></div>';
  await f(arg);
  app.focus({ preventScroll: true }); window.scrollTo({ top: 0 });
}
window.addEventListener("hashchange", router);

/* ================================================================ INICIO */
async function vInicio() {
  const p = (await api("/api/publico")).data;
  app.innerHTML = `<div class="stack">
  <section class="card hero">
   <div><span class="pill live">Periodo ${esc(p.periodo)}</span>
    <h1 style="margin-top:14px">Tu residencia,<br>sin filas ni papeles</h1><div class="uline"></div>
    <p class="lead">Elige tu proyecto, sube tu reporte preliminar y listo: ResiTrack revisa tus requisitos, te asigna asesor y emite tu carta <b>al instante</b>.</p>
    <div class="row" style="margin-top:18px"><a class="btn pri" href="#/alumno">Soy alumno →</a><a class="btn sec" href="#/asesor">Soy asesor</a></div>
    <p class="small muted" style="margin-top:12px">¿Eres de la DEP, Jefatura o Escolares? <a href="#/reportes">Consulta los reportes</a></p></div>
   ${escena()}
  </section>
  <section class="grid g4">
   <div class="card stat"><b>${p.proyectos}</b><span>proyectos avalados en el banco</span></div>
   <div class="card stat"><b>${p.solicitudes}</b><span>solicitudes del periodo</span></div>
   <div class="card stat"><b>${p.acreditadas}</b><span>residencias acreditadas</span></div>
   <div class="card stat"><b>0</b><span>hojas impresas</span></div>
  </section>
  <section><h2 style="margin:10px 0 22px">¿Cómo funciona?</h2>
   <div class="grid g4">
    ${[["1", "🔎", "Revisa tus requisitos", "El sistema consulta tu kárdex y te dice si te falta algo y cómo resolverlo."],
       ["2", "📤", "Elige y sube", "Escoge un proyecto avalado y sube tu reporte preliminar. Se valida antes de enviar."],
       ["3", "⚡", "Todo al instante", "Se asigna tu asesor y la carta sale con firma electrónica directo a la empresa."],
       ["4", "🎓", "Seguimiento en línea", "Tus asesores evalúan en línea y el acta llega sola a Servicios Escolares."]]
      .map(s => `<div class="card step"><span class="n">${s[0]}</span><div class="ic">${s[1]}</div><h3>${s[2]}</h3><p class="muted small">${s[3]}</p></div>`).join("")}
   </div></section>
  <section class="band"><div class="big">0</div><div><h2>tareas manuales del personal</h2><p>Ya automatizado, ¿quién interviene? <b>Nadie.</b> El alumno, la empresa y los asesores hacen su parte; la DEP, la Jefatura y Escolares solo reciben reportes.</p></div></section>
 </div>`;
}

/* ================================================================ LOGIN genérico */
function vLogin(rol, titulo, sub, demos) {
  app.innerHTML = `<section class="card login"><h1 style="font-size:34px">${titulo}</h1><div class="uline"></div><p class="muted">${sub}</p>
   <form id="lf"><label for="u">${rol === "alumno" ? "Número de control" : "Usuario"}</label><input id="u" autocomplete="username" required>
   <label for="p">Contraseña</label><input id="p" type="password" autocomplete="current-password" required>
   <div id="le" role="alert"></div>
   <div class="row" style="margin-top:16px"><button class="btn pri">Entrar</button><a class="btn ghost" href="#/">← Inicio</a></div></form>
   <div class="note" style="margin-top:18px"><b>Cuentas de demostración</b> (toca una para llenarla):<div class="demo-acc">${demos.map(d => `<button type="button" data-u="${d[0]}" data-p="${d[1]}">${esc(d[2])}</button>`).join("")}</div></div></section>`;
  $$(".demo-acc button").forEach(b => b.onclick = () => { $("#u").value = b.dataset.u; $("#p").value = b.dataset.p; $("#p").focus(); });
  $("#lf").onsubmit = async e => {
    e.preventDefault();
    const r = await api("/api/login", { json: { usuario: $("#u").value, clave: $("#p").value, rol } });
    if (!r.ok) { $("#le").innerHTML = `<div class="err-box">${esc(r.data.error)}</div>`; return; }
    await sesion(); toast("¡Bienvenido(a), " + r.data.nombre.split(" ")[0] + "!"); router();
  };
}
async function salir() { await api("/api/logout", { json: {} }); await sesion(); toast("Sesión cerrada"); location.hash = "#/"; router(); }
const barraSesion = (txt) => `<div class="row between"><div class="row"><span class="avatar">${esc(iniciales(SES.nombre))}</span><div><h2 style="margin:0">${txt}</h2><span class="muted small">${esc(SES.nombre)} · reloj del sistema: ${esc(SES.reloj)}</span></div></div><button class="btn ghost sm" id="salir">Cerrar sesión</button></div>`;
const correosHTML = cs => cs.length ? cs.map(c => `<div class="mail"><b>✉️ ${esc(c.asunto)}</b><span class="small">${esc(c.cuerpo)}</span><br><time>${esc(c.fecha.slice(0, 16))}</time>${c.enlace ? ` · <a href="${esc(c.enlace)}">Abrir</a>` : ""}</div>`).join("") : '<p class="muted small">Aún no tienes avisos.</p>';

/* ================================================================ ALUMNO */
async function vAlumno() {
  await sesion();
  if (SES.rol !== "alumno") return vLogin("alumno", "Hola, residente", "Entra con tu número de control para ver tus requisitos y tu trámite.",
    [["22000101", "Resi-2026", "22000101 · cumple requisitos"], ["22000102", "Resi-2026", "22000102 · le falta 1 crédito"], ["22000103", "Resi-2026", "22000103 · subir reporte final"], ["22000104", "Resi-2026", "22000104 · acreditada"]]);
  const r = await api("/api/alumno"); if (!r.ok) return vLogin("alumno", "Hola, residente", r.data.error, []);
  const d = r.data, rq = d.req, s = d.solicitud;
  const reqHTML = rq.requisitos.map(x => `<div class="req"><span class="ico ${x.ok ? "" : "no"}">${x.ok ? "✓" : "✕"}</span><div style="flex:1"><b>${esc(x.nombre)}</b><div class="small muted">${esc(x.valor)}${x.ok ? "" : " · " + esc(x.ayuda)}</div></div></div>`).join("");
  let cuerpo = "";
  if (s) {
    const tl = s.timeline.map((p, i) => { const cur = !p.hecho && (i === 0 || s.timeline[i - 1].hecho); return `<li class="${p.error ? "bad" : p.hecho ? "done" : cur ? "cur" : ""}"><span class="dot">${p.error ? "!" : p.hecho ? "✓" : i + 1}</span><b>${esc(p.nombre)}</b><small>${p.hecho ? esc(p.fecha + (p.hora ? " · " + p.hora : "")) + (p.detalle ? " — " + esc(p.detalle) : "") : "Pendiente"}</small></li>`; }).join("");
    const docs = [s.carta ? `<a class="btn azul sm" href="/api/alumno/carta.pdf">📄 Descargar carta (${esc(s.carta)})</a>` : "",
      ["ACREDITADA", "NO_ACREDITADA"].includes(s.etapa) ? `<a class="btn azul sm" href="/api/alumno/acta.pdf">🎓 Descargar acta</a>` : ""].join(" ");
    const subir = s.puede_reporte ? `<div class="card"><div class="row between"><h2 style="margin:0">Reporte final</h2><span class="pill ${s.dias_restantes <= 3 ? "err" : "warn"}">Te quedan ${Math.max(0, s.dias_restantes)} de 15 días</span></div>
      <p class="muted small">Debe incluir Introducción, Resultados y Conclusiones (Anexo XXVIII). Máximo 20 MB.</p>${dropzone("rf", "Sube tu reporte final en PDF")}<div id="rfm"></div></div>` : "";
    cuerpo = `<div class="grid g2">
     <div class="card span2 next"><h3>👉 ¿Qué sigue?</h3><p style="margin:0">${esc(s.siguiente)}</p></div>
     <div class="card"><div class="row between"><h2 style="margin:0">Mi trámite</h2><span class="pill info">${esc(s.folio)}</span></div><p class="muted small">${esc(s.proyecto)} · ${esc(s.empresa)}</p><ol class="tl">${tl}</ol></div>
     <div class="stack">
      ${s.asesor ? `<div class="card"><h3>Tu asesor interno</h3><div class="row"><span class="avatar">${esc(iniciales(s.asesor.nombre))}</span><div><b>${esc(s.asesor.nombre)}</b><div class="small muted">${esc(s.asesor.depto)} · ${esc(s.asesor.correo)}</div></div></div>
        <p class="small muted" style="margin-bottom:0">Asignado automáticamente: mismo departamento y menor carga.</p>${s.ext ? `<p class="small" style="margin:6px 0 0"><b>Asesor externo:</b> ${esc(s.ext)}</p>` : ""}</div>` : ""}
      ${s.calificacion != null ? `<div class="card" style="text-align:center"><span class="muted">Calificación final</span><div style="font-size:60px;font-weight:900;color:var(--terra);line-height:1">${s.calificacion}</div><span class="pill ${s.calificacion >= 70 ? "" : "err"}">${s.calificacion >= 70 ? "Acreditada" : "No acreditada"}</span></div>` : ""}
      ${docs.trim() ? `<div class="card"><h3>Mis documentos</h3><div class="row">${docs}</div></div>` : ""}
      ${subir}
      <div class="card"><h3>Mis avisos</h3>${correosHTML(d.correos)}</div>
     </div></div>`;
  } else if (rq.cumple) {
    cuerpo = `${d.aviso ? `<div class="err-box">${esc(d.aviso)}</div>` : ""}<div class="card"><div class="row between"><h2 style="margin:0">Banco de proyectos</h2><span class="pill">Avalados por la Academia</span></div>
      <p class="muted small">Solo ves proyectos de tu carrera con lugares disponibles.</p>
      <div class="grid g2">${d.proyectos.map(p => `<div class="proj"><b style="color:var(--head)">${esc(p.titulo)}</b><span class="small muted">${esc(p.empresa)}</span><span class="small">${esc(p.descripcion)}</span>
       <div class="row between"><span class="pill ${p.libres > 0 ? "" : "err"}">${p.libres > 0 ? p.libres + " de " + p.cupo + " lugares" : "Sin cupo"}</span><button class="btn pri sm" data-pid="${p.id}" ${p.libres > 0 ? "" : "disabled"}>Elegir</button></div></div>`).join("") || '<p class="muted">No hay proyectos para tu carrera en este periodo.</p>'}</div></div>
      <div class="card"><h3>Mis avisos</h3>${correosHTML(d.correos)}</div>`;
  } else {
    cuerpo = `<div class="card next"><h3>👉 ¿Qué sigue?</h3><p style="margin:0">Aún no puedes solicitar tu residencia. Resuelve el requisito en rojo; el sistema lo detectará solo cuando se actualice tu kárdex.</p></div>`;
  }
  app.innerHTML = `<div class="stack"><div class="card">${barraSesion("Hola, " + esc(rq.alumno.nombre.split(" ")[0]))}</div>
    <div class="grid g3"><div class="card"><h3>Mis requisitos</h3><p class="small muted" style="margin:0">Leídos del SII · ${esc(rq.alumno.carrera)}</p>${reqHTML}</div><div class="span2 stack">${cuerpo}</div></div></div>`;
  $("#salir").onclick = salir;
  $$("[data-pid]").forEach(b => b.onclick = () => solicitarModal(d.proyectos.find(p => p.id == b.dataset.pid)));
  if (s && s.puede_reporte) wireDrop("rf", async f => {
    const fd = new FormData(); fd.append("archivo", f);
    const x = await api("/api/alumno/reporte", { method: "POST", body: fd });
    if (!x.ok) { $("#rfm").innerHTML = `<div class="err-box">${esc(x.data.error)}</div>`; return; }
    toast("Reporte final entregado. Tu asesor ya fue notificado."); vAlumno();
  });
}
function dropzone(id, txt) { return `<label class="drop" id="dz-${id}" for="f-${id}"><div style="font-size:34px">📄</div><b>${txt}</b><div class="small muted">Arrástralo aquí o toca para elegirlo</div><input id="f-${id}" type="file" accept="application/pdf,.pdf"></label>`; }
function wireDrop(id, cb) {
  const z = $("#dz-" + id), inp = $("#f-" + id);
  inp.onchange = () => inp.files[0] && cb(inp.files[0]);
  ["dragover", "dragenter"].forEach(ev => z.addEventListener(ev, e => { e.preventDefault(); z.classList.add("over"); }));
  ["dragleave", "drop"].forEach(ev => z.addEventListener(ev, e => { e.preventDefault(); z.classList.remove("over"); }));
  z.addEventListener("drop", e => e.dataTransfer.files[0] && cb(e.dataTransfer.files[0]));
}
function solicitarModal(p) {
  modal(`<h2>${esc(p.titulo)}</h2><p class="muted small">${esc(p.empresa)}</p>
   <p class="small">Sube tu <b>reporte preliminar</b> en PDF (máx. 5 MB). Debe tener: nombre del proyecto, objetivos, justificación, cronograma y descripción de actividades. La hoja membretada va <b>solo en la portada</b>.</p>
   ${dropzone("rp", "Sube tu reporte preliminar")}<div id="rpm" role="alert"></div>
   <p class="small muted">¿No tienes uno? Descarga un <a href="/muestras/reporte_preliminar_correcto.pdf">ejemplo correcto</a> o uno <a href="/muestras/reporte_preliminar_sin_cronograma.pdf">con errores</a> para probar.</p>
   <div class="row" style="justify-content:flex-end"><button class="btn ghost" id="cx">Cancelar</button></div>`);
  $("#cx").onclick = cerrar;
  wireDrop("rp", async f => {
    $("#rpm").innerHTML = '<div class="note">Revisando tu archivo…</div>';
    const fd = new FormData(); fd.append("archivo", f); fd.append("proyecto_id", p.id);
    const r = await api("/api/alumno/solicitar", { method: "POST", body: fd });
    if (!r.ok) { $("#rpm").innerHTML = `<div class="err-box">${esc(r.data.error)}</div>`; return; }
    cerrar(); confetti(); toast("¡Listo! Folio " + r.data.folio + ": asesor asignado y carta enviada."); vAlumno();
  });
}

/* ================================================================ ASESOR */
async function vAsesor() {
  await sesion();
  if (SES.rol !== "asesor") return vLogin("asesor", "Asesores internos", "Registra los seguimientos y evalúa los reportes finales de tus residentes.",
    [["asesor.sistemas", "Asesor-2026", "M.C. Ricardo Ibarra · Sistemas"], ["asesor.sistemas2", "Asesor-2026", "Ing. Paola Garza · Sistemas"], ["asesor.industrial", "Asesor-2026", "Ing. Laura Montemayor · Industrial"]]);
  const r = await api("/api/asesor"); if (!r.ok) return;
  const d = r.data, A = d.asesor, pct = Math.round(d.carga / A.tope * 100);
  const accion = x => {
    if (!x.pendiente) return `<span class="pill ${x.etapa === "ACREDITADA" ? "" : "info"}">${esc(x.etapa_txt)}${x.calificacion != null ? " · " + x.calificacion : ""}</span>`;
    const t = { s1: "Evaluar seguimiento 1", s2: "Evaluar seguimiento 2", rep: "Evaluar reporte final" }[x.pendiente];
    const v = x.vence_en == null ? "" : x.vence_en < 0 ? `<span class="pill err">Vencido hace ${-x.vence_en} días</span>` : `<span class="pill warn">Vence en ${x.vence_en} días</span>`;
    return `${v} <button class="btn pri sm" data-ev="${x.id}" data-t="${x.pendiente}">${t}</button>`;
  };
  app.innerHTML = `<div class="stack"><div class="card">${barraSesion("Mis residentes")}</div>
   <div class="grid g3"><div class="card kpi"><span class="em">👥</span><b>${d.carga} / ${A.tope}</b><span>residentes activos (tope RN-07)</span><div class="bar" style="margin-top:10px"><i style="width:${pct}%" class="${pct >= 100 ? "full" : ""}"></i></div></div>
    <div class="card kpi"><span class="em">⏰</span><b>${d.residentes.filter(x => x.pendiente).length}</b><span>evaluaciones pendientes</span></div>
    <div class="card kpi good"><span class="em">🖨️</span><b>0</b><span>formatos impresos o sellos</span></div></div>
   <div class="grid g3"><div class="span2 stack">${d.residentes.map(x => `<div class="card"><div class="row between"><div><h3 style="margin:0">${esc(x.alumno)}</h3><span class="small muted">${esc(x.carrera)} · ${esc(x.folio)}</span></div><div class="row">${accion(x)}</div></div>
     <p class="small" style="margin:10px 0 6px"><b>${esc(x.proyecto)}</b> · ${esc(x.empresa)}</p>
     <div class="row small muted">${x.fechas.s1 ? `Seg. 1: ${esc(x.fechas.s1)} · Seg. 2: ${esc(x.fechas.s2)} · Límite reporte: ${esc(x.fechas.limite)}` : "Esperando aceptación de la empresa"}</div>
     <div class="row" style="margin-top:10px"><a class="btn ghost sm" href="/api/asesor/preliminar/${x.id}.pdf">📄 Reporte preliminar</a>${["REPORTE_ENTREGADO", "ACREDITADA", "NO_ACREDITADA"].includes(x.etapa) ? `<a class="btn ghost sm" href="/api/asesor/preliminar/${x.id}.pdf?tipo=final">📘 Reporte final</a>` : ""}</div></div>`).join("") || '<div class="card"><p class="muted">Aún no tienes residentes asignados.</p></div>'}</div>
    <div class="card"><h3>Mis avisos</h3>${correosHTML(d.correos)}</div></div></div>`;
  $("#salir").onclick = salir;
  $$("[data-ev]").forEach(b => b.onclick = () => evalModal(d.residentes.find(x => x.id == b.dataset.ev), b.dataset.t, d.criterios, async (tipo, puntos) => api("/api/asesor/evaluar", { json: { id: +b.dataset.ev, tipo, puntos } }), vAsesor));
}
function evalModal(x, tipo, criterios, enviar, despues) {
  const crit = tipo === "rep" ? criterios.rep : criterios.seg, tit = { s1: "Seguimiento 1 · Anexo XXIX", s2: "Seguimiento 2 · Anexo XXIX", rep: "Evaluación del reporte · Anexo XXX" }[tipo];
  modal(`<h2>${tit}</h2><p class="muted small">${esc(x.alumno)} · ${esc(x.proyecto)}</p>
   <div class="crit small muted"><b>Criterio</b><b>Máx.</b><b>Puntos</b></div>
   ${crit.map((c, i) => `<div class="crit"><span>${esc(c[0])}</span><span class="muted">${c[1]}</span><input type="number" min="0" max="${c[1]}" step="1" inputmode="numeric" data-i="${i}" aria-label="${esc(c[0])}"></div>`).join("")}
   <div class="row between" style="margin-top:14px"><span>Total (se calcula solo)</span><span class="total" id="tot">0</span></div>
   ${tipo === "rep" ? '<p class="small note">Al firmar, el sistema calcula la calificación final (10 % + 10 % + 80 %) y envía el acta a Servicios Escolares.</p>' : ""}
   <div id="em" role="alert"></div><div class="row" style="justify-content:flex-end;margin-top:14px"><button class="btn ghost" id="cx">Cancelar</button><button class="btn pri" id="ok">Firmar y enviar</button></div>`);
  const ins = $$("#modal-card input");
  ins.forEach(i => i.oninput = () => $("#tot").textContent = ins.reduce((s, j) => s + (parseInt(j.value) || 0), 0));
  $("#cx").onclick = cerrar;
  $("#ok").onclick = async () => {
    const r = await enviar(tipo, ins.map(i => i.value.trim()));
    if (!r.ok) { $("#em").innerHTML = `<div class="err-box">${esc(r.data.error)}</div>`; return; }
    cerrar(); toast("Evaluación firmada: " + r.data.total + " puntos"); if (tipo === "rep") confetti(); despues();
  };
}

/* ================================================================ EMPRESA (enlace) */
async function vEmpresa(tok) {
  const r = await api("/api/empresa/" + encodeURIComponent(tok || ""));
  if (!r.ok) { app.innerHTML = `<section class="card verif"><div class="seal bad">✕</div><h2>Enlace no válido</h2><p class="muted">${esc(r.data.error)}</p></section>`; return; }
  const d = r.data;
  let cuerpo;
  if (d.etapa === "CARTA_EMITIDA") {
    cuerpo = `<h2>¿Acepta a ${esc(d.alumno)} como residente?</h2><p class="muted">${esc(d.carrera)} · Proyecto: <b>${esc(d.proyecto)}</b> · 500 horas, de 4 a 6 meses · Carta ${esc(d.carta)}</p>
     <form id="af" class="grid g2"><div><label for="n">Nombre del asesor externo</label><input id="n" required></div><div><label for="c">Cargo</label><input id="c" required></div>
     <div><label for="m">Correo del asesor externo</label><input id="m" type="email" required></div><div><label for="i">Fecha de inicio</label><input id="i" type="date" required></div>
     <div class="span2" id="ae" role="alert"></div>
     <div class="span2 row"><button class="btn pri">Aceptar residente</button><button type="button" class="btn sec" id="no">No puedo aceptarlo</button></div></form>`;
  } else if (d.pendiente) {
    cuerpo = `<h2>Evaluación de ${d.pendiente === "s1" ? "seguimiento 1" : "seguimiento 2"}</h2><p class="muted">${esc(d.alumno)} · ${esc(d.proyecto)} · fecha programada: ${esc(d.fechas[d.pendiente])}</p>
     <button class="btn pri" id="evb">Evaluar ahora</button>`;
  } else {
    cuerpo = `<div class="seal">✓</div><h2 style="text-align:center">Todo al día</h2><p class="muted" style="text-align:center">Estado: <b>${esc(d.etapa_txt)}</b>. Le avisaremos por correo cuando haya algo pendiente.</p>`;
  }
  app.innerHTML = `<section class="card" style="max-width:760px;margin:0 auto"><div class="row between"><span class="pill info">🔒 Enlace seguro · sin cuenta</span><span class="small muted">${esc(d.empresa)}</span></div><div style="margin-top:14px">${cuerpo}</div></section>`;
  if ($("#af")) {
    $("#af").onsubmit = async e => {
      e.preventDefault();
      const x = await api(`/api/empresa/${tok}/aceptar`, { json: { acepta: true, nombre: $("#n").value, cargo: $("#c").value, correo: $("#m").value, inicio: $("#i").value } });
      if (!x.ok) { $("#ae").innerHTML = `<div class="err-box">${esc(x.data.error)}</div>`; return; }
      confetti(); toast("¡Gracias! La residencia quedó registrada."); vEmpresa(tok);
    };
    $("#no").onclick = () => {
      modal(`<h2>No puedo aceptarlo</h2><label for="mo">Motivo (opcional)</label><textarea id="mo" rows="3"></textarea><div class="row" style="justify-content:flex-end;margin-top:12px"><button class="btn ghost" id="cx">Cancelar</button><button class="btn pri" id="ok">Enviar</button></div>`);
      $("#cx").onclick = cerrar;
      $("#ok").onclick = async () => { await api(`/api/empresa/${tok}/aceptar`, { json: { acepta: false, motivo: $("#mo").value } }); cerrar(); toast("Respuesta enviada. Avisamos al alumno."); vEmpresa(tok); };
    };
  }
  if ($("#evb")) $("#evb").onclick = () => evalModal({ alumno: d.alumno, proyecto: d.proyecto }, d.pendiente, { seg: d.criterios }, (tipo, puntos) => api(`/api/empresa/${tok}/evaluar`, { json: { tipo, puntos } }), () => vEmpresa(tok));
}

/* ================================================================ REPORTES (DEP · Jefatura · Escolares) */
async function vReportes() {
  await sesion();
  if (SES.rol !== "consulta") return vLogin("consulta", "Reportes", "DEP, Jefatura y Servicios Escolares consultan aquí. Es de solo lectura: el sistema hace todo lo administrativo.",
    [["dep", "Dep-2026", "División de Estudios"], ["jefatura", "Jefatura-2026", "Jefatura"], ["escolares", "Escolares-2026", "Servicios Escolares"]]);
  const r = await api("/api/consulta"); if (!r.ok) return;
  const d = r.data, k = d.kpi, maxE = Math.max(1, ...k.por_etapa.map(x => x.n));
  app.innerHTML = `<div class="stack"><div class="card">${barraSesion("Reportes del periodo")}</div>
   <div class="ro">🔒 Modo solo lectura: aquí no se captura, revisa ni autoriza nada. El sistema hace todo lo administrativo.</div>
   <div class="grid g4">
    <div class="card kpi"><span class="em">🧑‍🎓</span><b>${k.activos}</b><span>residentes activos</span></div>
    <div class="card kpi good"><span class="em">⚡</span><b style="font-size:22px">${esc(k.tiempo_carta_txt)}</b><span>de la solicitud a la carta</span></div>
    <div class="card kpi good"><span class="em">🛡️</span><b>${k.devueltos_personal}</b><span>documentos devueltos por el personal (${k.corregidos_antes} se corrigieron antes de enviar)</span></div>
    <div class="card kpi good"><span class="em">🌱</span><b>${k.hojas}</b><span>hojas impresas</span></div>
    <div class="card kpi good"><span class="em">🙌</span><b>${k.tareas_personal}</b><span>tareas manuales del personal</span></div>
    <div class="card kpi"><span class="em">🎓</span><b>${k.acreditadas}</b><span>acreditadas · actas en el SII</span></div>
    <div class="card kpi ${k.vencidos ? "" : "good"}"><span class="em">⏰</span><b>${k.vencidos}</b><span>seguimientos vencidos</span></div>
    <div class="card kpi"><span class="em">✉️</span><b>${k.correos}</b><span>avisos y recordatorios enviados</span></div></div>
   ${k.en_espera ? `<div class="err-box">${k.en_espera} solicitud(es) esperan asesor: ningún asesor del departamento tiene cupo. Revise la regla de asignación (tope RN-07).</div>` : ""}
   <div class="grid g2"><div class="card"><h3>Solicitudes por etapa</h3>${k.por_etapa.filter(x => x.n || ["SOLICITADA", "ACREDITADA"].includes(x.etapa)).map(x => `<div style="margin:8px 0"><div class="row between small"><span>${esc(x.nombre)}</span><b>${x.n}</b></div><div class="bar"><i style="width:${x.n / maxE * 100}%"></i></div></div>`).join("")}</div>
    <div class="card"><h3>Carga de asesores internos</h3>${d.asesores.map(a => `<div style="margin:8px 0"><div class="row between small"><span>${esc(a.nombre)} <span class="muted">· ${esc(a.depto)}</span></span><b>${a.carga}/${a.tope}</b></div><div class="bar"><i class="${a.carga >= a.tope ? "full" : ""}" style="width:${a.carga / a.tope * 100}%"></i></div></div>`).join("")}</div></div>
   <div class="card"><div class="row between"><h3 style="margin:0">Solicitudes</h3><div class="row"><input id="q" placeholder="Buscar por alumno, folio o empresa…" style="width:280px"><a class="btn azul sm" href="/api/consulta/excel">⬇ Excel</a></div></div>
    <div class="tw" style="margin-top:12px"><table><thead><tr><th>Folio</th><th>Alumno</th><th>Proyecto</th><th>Asesor</th><th>Etapa</th><th>Cal.</th></tr></thead><tbody id="tb">
    ${d.solicitudes.map(s => `<tr data-q="${esc((s.folio + s.alumno + s.empresa + s.proyecto).toLowerCase())}"><td><b>${esc(s.folio)}</b><div class="small muted">${esc(s.creado)}</div></td><td>${esc(s.alumno)}<div class="small muted">${esc(s.carrera)}</div></td><td>${esc(s.proyecto)}<div class="small muted">${esc(s.empresa)}</div></td><td>${esc(s.asesor)}</td><td><span class="pill ${s.etapa === "ACREDITADA" ? "" : s.etapa.includes("RECH") || s.etapa.includes("NO_") ? "err" : "info"}">${esc(s.etapa_txt)}</span></td><td>${s.calificacion ?? "—"}</td></tr>`).join("")}</tbody></table></div></div>
   <div class="grid g2"><div class="card"><h3>Actas recibidas en el SII (Servicios Escolares)</h3>${d.actas.map(a => `<div class="mail"><b>${esc(a.folio)} · ${esc(a.nombre)}</b><span class="small">Calificación ${a.calificacion} · recibida ${esc(a.fecha.slice(0, 16))}, sin captura manual</span></div>`).join("") || '<p class="muted">Sin actas todavía.</p>'}</div>
    <div class="card"><h3>Bitácora de auditoría</h3><div style="max-height:320px;overflow:auto">${d.bitacora.map(b => `<div class="mail"><b class="small">${esc(b.accion)}</b><time>${esc(b.fecha.slice(0, 16))} · ${esc(b.usuario)}</time></div>`).join("")}</div></div></div></div>`;
  $("#salir").onclick = salir;
  $("#q").oninput = e => { const q = e.target.value.toLowerCase(); $$("#tb tr").forEach(t => t.hidden = !t.dataset.q.includes(q)); };
}

/* ================================================================ VERIFICAR (QR) */
async function vVerificar(folio) {
  const d = (await api("/api/verificar/" + encodeURIComponent(folio || ""))).data;
  app.innerHTML = d.valido ? `<section class="card verif"><div class="seal">✓</div><h1 style="font-size:32px">Carta auténtica</h1><p class="muted">Emitida por ResiTrack con firma electrónica.</p>
    <div class="tw" style="text-align:left"><table><tbody><tr><td><b>Folio</b></td><td>${esc(d.folio)}</td></tr><tr><td><b>Alumno</b></td><td>${esc(d.alumno)}</td></tr><tr><td><b>Carrera</b></td><td>${esc(d.carrera)}</td></tr><tr><td><b>Proyecto</b></td><td>${esc(d.proyecto)}</td></tr><tr><td><b>Empresa</b></td><td>${esc(d.empresa)}</td></tr><tr><td><b>Emitida</b></td><td>${esc(d.fecha)}</td></tr></tbody></table></div></section>`
    : `<section class="card verif"><div class="seal bad">✕</div><h1 style="font-size:32px">No encontramos esa carta</h1><p class="muted">Revisa el folio o escanea de nuevo el código QR.</p></section>`;
}

/* ================================================================ DEMO */
async function vDemo() {
  const d = (await api("/api/demo")).data;
  app.innerHTML = `<div class="stack"><div class="card"><h1 style="font-size:32px">Panel de demostración</h1><div class="uline"></div>
   <p class="note">Esta pantalla <b>no forma parte del sistema real</b>: sirve para mostrar el prototipo. Simula el reloj (para ver recordatorios y plazos) y la bandeja de correo.</p></div>
   <div class="grid g3"><div class="card"><h3>⏱️ Reloj del sistema</h3><p style="font-size:24px;font-weight:900;margin:6px 0">${esc(d.reloj)}</p><p class="small muted">Adelantado ${d.reloj_dias} días</p>
     <div class="row"><button class="btn azul sm" data-d="7">+7 días</button><button class="btn azul sm" data-d="30">+30 días</button><button class="btn ghost sm" id="r0">Reiniciar</button></div></div>
    <div class="card"><h3>📄 PDF de prueba</h3><p class="small muted">Para probar la validación automática del reporte preliminar y del reporte final.</p>
     <div class="stack small"><a href="/muestras/reporte_preliminar_correcto.pdf">✅ Reporte preliminar correcto</a><a href="/muestras/reporte_preliminar_sin_cronograma.pdf">❌ Sin cronograma</a><a href="/muestras/reporte_preliminar_membretada_en_todas.pdf">❌ Hoja membretada en todas</a><a href="/muestras/reporte_final.pdf">✅ Reporte final</a></div></div>
    <div class="card"><h3>♻️ Datos simulados</h3><p class="small muted">Vuelve a cargar los datos iniciales. Se cierra la sesión.</p><button class="btn pri sm" id="rs">Reiniciar datos</button></div></div>
   <div class="card"><h3>🔗 Enlaces de empresa (lo que la empresa recibe por correo)</h3>${d.enlaces.map(e => `<div class="mail"><b>${esc(e.folio)} · ${esc(e.empresa)}</b><span class="small">${esc(e.etapa)} · <a href="#/empresa/${esc(e.token)}">Abrir como empresa</a></span></div>`).join("")}</div>
   <div class="card"><h3>✉️ Bandeja de correo simulada (${d.correos.length})</h3>${d.correos.map(c => `<div class="mail"><b>${esc(c.asunto)}</b><span class="small">Para: ${esc(c.para)} — ${esc(c.cuerpo)}</span><br><time>${esc(c.fecha.slice(0, 16))}</time>${c.enlace ? ` · <a href="${esc(c.enlace)}">Abrir enlace</a>` : ""}</div>`).join("") || '<p class="muted">Aún no se han enviado correos. Haz una solicitud como alumno.</p>'}</div></div>`;
  $$("[data-d]").forEach(b => b.onclick = async () => { const r = await api("/api/demo/reloj", { json: { dias: +b.dataset.d } }); toast("Reloj: " + r.data.reloj); vDemo(); });
  $("#r0").onclick = async () => { await api("/api/demo/reloj", { json: { reiniciar: true } }); toast("Reloj reiniciado"); vDemo(); };
  $("#rs").onclick = async () => { await api("/api/demo/reiniciar", { json: {} }); await sesion(); toast("Datos simulados reiniciados"); vDemo(); };
}

/* ---------- arranque ---------- */
sesion().then(router);
