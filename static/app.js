"use strict";

/* ===================== Utilidades ===================== */
const $ = (id) => document.getElementById(id);

// Crea elementos con textContent (nunca innerHTML con datos del usuario => sin XSS)
function el(tag, props = {}, ...hijos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  e.append(...hijos);
  return e;
}

async function api(url, opts = {}) {
  const res = await fetch(url, {
    method: opts.method || "GET",
    headers: opts.form ? {} : { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: opts.form || (opts.body ? JSON.stringify(opts.body) : undefined),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Error de servidor");
  return data;
}

function mostrarError(id, e) { $(id).textContent = e ? e.message : ""; }

// Las fechas del servidor vienen en UTC sin "Z": se agrega para mostrarlas en hora local
const fecha = (s) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : s + "Z").toLocaleString();

// Avatar con iniciales y color estable segun el nombre
function avatar(nombre, peq = false, foto = null, grande = false) {
  const tam = (peq ? " peq" : "") + (grande ? " grande" : "");
  if (foto) return el("img", { class: "avatar" + tam, src: `/api/imagenes/${foto}`, alt: nombre });
  const ini = (nombre || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
  let h = 0;
  for (const c of nombre || "") h = (h * 31 + c.charCodeAt(0)) % 360;
  return el("span", { class: "avatar" + tam, style: `background:hsl(${h} 45% 38%)` }, ini);
}

// Ventana flotante generica (nueva historia, visor de historias). Devuelve la funcion para cerrarla.
function abrirModal(contenido, alCerrar) {
  const fondo = el("div", { class: "modal" });
  const tecla = (ev) => { if (ev.key === "Escape") cerrar(); };
  const cerrar = () => {
    document.removeEventListener("keydown", tecla);
    fondo.remove();
    if (alCerrar) alCerrar();
  };
  fondo.addEventListener("click", (ev) => { if (ev.target === fondo) cerrar(); });
  document.addEventListener("keydown", tecla);
  fondo.append(contenido);
  document.body.append(fondo);
  return cerrar;
}

/* ===================== Tamaño de letra (Configuracion) ===================== */
const FUENTE_MIN = 12, FUENTE_MAX = 24, FUENTE_DEF = 16;
let fuentePx = FUENTE_DEF;
try {
  const guardado = Number(localStorage.getItem("fuentePx"));
  if (guardado >= FUENTE_MIN && guardado <= FUENTE_MAX) fuentePx = guardado;
} catch { /* localStorage no disponible: se usa el tamaño por defecto */ }

function aplicarFuente(px) {
  fuentePx = px;
  document.documentElement.style.fontSize = px + "px";
  try { localStorage.setItem("fuentePx", String(px)); } catch { /* ignorar */ }
}
document.documentElement.style.fontSize = fuentePx + "px";

/* ===================== Tema claro / oscuro (Configuracion) ===================== */
const TEMAS = ["claro", "oscuro", "auto"];
let temaPref = "auto";
try {
  const t = localStorage.getItem("tema");
  if (TEMAS.includes(t)) temaPref = t;
} catch { /* localStorage no disponible */ }
const mqOscuro = window.matchMedia("(prefers-color-scheme: dark)");

function aplicarTema(pref = temaPref) {
  temaPref = pref;
  const oscuro = pref === "oscuro" || (pref === "auto" && mqOscuro.matches);
  document.documentElement.dataset.tema = oscuro ? "oscuro" : "claro";
  try { localStorage.setItem("tema", pref); } catch { /* ignorar */ }
}
mqOscuro.addEventListener("change", () => { if (temaPref === "auto") aplicarTema(); });
aplicarTema();

// Alternar entre iniciar sesion y crear cuenta
function mostrarForm(registro) {
  $("form-login").hidden = registro;
  $("form-registro").hidden = !registro;
  $("seg-login").classList.toggle("activo", !registro);
  $("seg-registro").classList.toggle("activo", registro);
  mostrarError("msg-auth", null);
}
$("seg-login").addEventListener("click", () => mostrarForm(false));
$("seg-registro").addEventListener("click", () => mostrarForm(true));

/* ===================== Autenticacion ===================== */
function llenarEscuelas(raiz, sel = $("sel-escuela")) {
  for (const area of raiz.hijos) {
    for (const fac of area.hijos) {
      const grupo = el("optgroup", { label: `${area.nombre} · ${fac.nombre}` });
      for (const esc of fac.hijos) grupo.append(el("option", { value: esc.id }, esc.nombre));
      sel.append(grupo);
    }
  }
}

async function iniciar() {
  try {
    const u = await api("/api/me");
    entrarApp(u);
  } catch {
    $("vista-auth").hidden = false;
    $("vista-app").hidden = true;
    try { llenarEscuelas(await api("/api/unidades-publicas")); } catch (e) { mostrarError("msg-auth", e); }
  }
}

function entrarApp(u) {
  $("vista-auth").hidden = true;
  $("vista-app").hidden = false;
  pintarChip(u);
  cargarPosts();
  if (!badgeIniciado) { badgeIniciado = true; actualizarBadge(); setInterval(actualizarBadge, 20000); }
}

// Arriba a la derecha solo se muestra el primer nombre (sin facultad)
function pintarChip(u) {
  $("yo").replaceChildren(avatar(u.nombres, true, u.foto), el("span", {}, u.nombres.split(" ")[0]));
}
$("yo").addEventListener("click", () => irA("perfil").catch((e) => mostrarError("msg-app", e)));

$("form-login").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = Object.fromEntries(new FormData(ev.target));
  try { await api("/api/login", { method: "POST", body: f }); iniciar(); }
  catch (e) { mostrarError("msg-auth", e); }
});

$("form-registro").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = Object.fromEntries(new FormData(ev.target));
  try { await api("/api/registro", { method: "POST", body: f }); iniciar(); }
  catch (e) { mostrarError("msg-auth", e); }
});

$("btn-logout").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" });
  location.reload();
});

/* ===================== Navegacion (menu izquierdo) ===================== */
let tabActual = "muro";
const CARGADORES = { muro: cargarPosts, buscar: async () => {}, amigos: cargarAmigos, mensajes: cargarMensajes, grupos: listarGrupos, perfil: cargarPerfil, config: cargarConfig };

async function irA(tab, cargar = true) {
  detenerSondeo();
  tabActual = tab;
  document.querySelectorAll(".menu button").forEach((x) => x.classList.toggle("activo", x.dataset.tab === tab));
  document.querySelectorAll(".contenido > section").forEach((s) => (s.hidden = s.id !== `tab-${tab}`));
  mostrarError("msg-app", null);
  $("panel-resultado").hidden = true;
  if (cargar) await CARGADORES[tab]();
}

document.querySelectorAll(".menu button").forEach((b) =>
  b.addEventListener("click", () => irA(b.dataset.tab).catch((e) => mostrarError("msg-app", e))));

/* ===================== Emojis, fotos y "me gusta" ===================== */
const EMOJIS = ("😀 😂 🥹 😍 🥳 😎 🤔 😅 😢 😡 🙄 😴 👍 👏 🙏 💪 🔥 ✨ 🎉 ❤️ 💙 💛 📚 ✏️ 🎓 🧠 💡 📝 ⚽ 🎵 🎮 ☕ 🍕 🌎 🇵🇪 🏛️ ✅ ❓ 🚀 👀").split(" ");

function insertar(campo, texto) {
  const i = campo.selectionStart ?? campo.value.length, j = campo.selectionEnd ?? i;
  campo.value = campo.value.slice(0, i) + texto + campo.value.slice(j);
  campo.focus();
  campo.setSelectionRange(i + texto.length, i + texto.length);
}

function botonEmoji(campo) {
  const pop = el("div", { class: "emoji-pop", hidden: "" },
    ...EMOJIS.map((e) => el("button", { type: "button", class: "emo", onclick: () => insertar(campo, e) }, e)));
  const btn = el("button", { type: "button", class: "icono-btn", title: "Emojis", "aria-label": "Insertar emoji",
    onclick: () => (pop.hidden = !pop.hidden) }, "😊");
  return el("span", { class: "emoji-wrap" }, btn, pop);
}
document.addEventListener("click", (ev) => {
  if (!ev.target.closest(".emoji-wrap")) document.querySelectorAll(".emoji-pop").forEach((p) => (p.hidden = true));
  if (!ev.target.closest(".msg-wrap")) document.querySelectorAll(".msg-menu").forEach((p) => (p.hidden = true));
  if (!ev.target.closest(".buscador")) $("sugerencias").hidden = true;
});

function botonLike(tipo, id, total, activo) {
  const b = el("button", { type: "button", class: "like", title: "Me gusta" });
  const pintar = (n, a) => { b.classList.toggle("activo", a); b.textContent = `${a ? "❤️" : "🤍"} ${n}`; };
  pintar(total, activo);
  b.addEventListener("click", async () => {
    try { const r = await api(`/api/likes/${tipo}/${id}`, { method: "POST" }); pintar(r.total, r.liked); }
    catch (e) { mostrarError("msg-app", e); }
  });
  return b;
}

// Caja para publicar (muro o grupo): texto + emojis + foto opcional
function composer(grupoId, alPublicar) {
  const area = el("textarea", { maxlength: "1000",
    placeholder: grupoId ? "Comparte algo con el grupo…" : "¿Qué quieres compartir con San Marcos?" });
  const archivo = el("input", { type: "file", accept: "image/png,image/jpeg,image/gif,image/webp", hidden: "" });
  const vista = el("div", { class: "preview", hidden: "" });
  let img = null;
  const quitar = () => { img = null; archivo.value = ""; vista.hidden = true; vista.replaceChildren(); };
  archivo.addEventListener("change", () => {
    const f = archivo.files[0];
    if (!f) return;
    if (f.size > 2 * 1024 * 1024) { quitar(); return mostrarError("msg-app", new Error("La imagen no puede pasar de 2 MB")); }
    img = f;
    mostrarError("msg-app", null);
    vista.replaceChildren(el("img", { src: URL.createObjectURL(f), alt: "Vista previa" }),
      el("button", { type: "button", class: "sec mini", onclick: quitar }, "Quitar"));
    vista.hidden = false;
  });
  const pub = el("button", {}, "Publicar");
  pub.addEventListener("click", async () => {
    pub.disabled = true;
    try {
      let imagen_id = null;
      if (img) {
        const fd = new FormData();
        fd.append("imagen", img);
        imagen_id = (await api("/api/imagenes", { method: "POST", form: fd })).id;
      }
      await api("/api/posts", { method: "POST", body: { texto: area.value, imagen_id, grupo_id: grupoId } });
      area.value = "";
      quitar();
      mostrarError("msg-app", null);
      await alPublicar();
    } catch (e) { mostrarError("msg-app", e); }
    pub.disabled = false;
  });
  return el("div", { class: "card publicar" }, area, vista,
    el("div", { class: "barra" }, botonEmoji(area),
      el("button", { type: "button", class: "icono-btn", title: "Agregar foto", onclick: () => archivo.click() }, "📷 Foto"),
      archivo, el("span", { class: "espacio" }), pub));
}

/* ===================== Historias (duran 24 h) ===================== */
function nuevaHistoria(f) {
  if (f.size > 2 * 1024 * 1024) return mostrarError("msg-app", new Error("La imagen no puede pasar de 2 MB"));
  mostrarError("msg-app", null);
  const texto = el("input", { placeholder: "Añade un texto (opcional)", maxlength: "150" });
  const msg = el("p", { class: "error", role: "alert" });
  const ok = el("button", { type: "button" }, "Compartir historia");
  const cancelar = el("button", { type: "button", class: "sec" }, "Cancelar");
  let cerrar;
  cancelar.addEventListener("click", () => cerrar());
  ok.addEventListener("click", async () => {
    ok.disabled = true;
    try {
      const fd = new FormData();
      fd.append("imagen", f);
      const { id } = await api("/api/imagenes", { method: "POST", form: fd });
      await api("/api/historias", { method: "POST", body: { imagen_id: id, texto: texto.value } });
      cerrar();
      await pintarHistorias();
    } catch (e) { msg.textContent = e.message; ok.disabled = false; }
  });
  cerrar = abrirModal(el("div", { class: "modal-caja" }, el("h2", {}, "Nueva historia"),
    el("img", { class: "historia-prev", src: URL.createObjectURL(f), alt: "Vista previa de la historia" }),
    texto, msg, el("div", { class: "barra" }, ok, cancelar)));
}

// Visor a pantalla completa: avanza solo cada 5 s; toca la derecha/izquierda para cambiar.
// Abajo: reacciones con emojis y comentarios (al escribir, la historia se detiene).
const REACCIONES = ["\u2764\ufe0f", "\u{1F602}", "\u{1F62E}", "\u{1F622}", "\u{1F44F}", "\u{1F525}"];

function verHistorias(grupos, gi) {
  let si = 0, timer = null, cerrar;
  const caja = el("div", { class: "visor" });

  const siguiente = () => {
    if (si < grupos[gi].historias.length - 1) si++;
    else if (gi < grupos.length - 1) { gi++; si = 0; }
    else return cerrar();
    mostrar();
  };
  const anterior = () => {
    if (si > 0) si--;
    else if (gi > 0) { gi--; si = 0; }
    mostrar();
  };
  const borrar = async () => {
    if (!confirm("¿Eliminar esta historia?")) return;
    try {
      await api(`/api/historias/${grupos[gi].historias[si].id}`, { method: "DELETE" });
      cerrar();
      await pintarHistorias();
    } catch (e) { mostrarError("msg-app", e); }
  };
  const pausar = () => { clearTimeout(timer); caja.classList.add("pausa"); };

  function pintarInteracciones(pie, h, d) {
    const accion = (promesa) => promesa.then((nuevo) => pintarInteracciones(pie, h, nuevo))
      .catch((e) => mostrarError("msg-app", e));

    const reacciones = el("div", { class: "visor-reacc" }, ...REACCIONES.map((emo) => {
      const n = d.reacciones[emo] || 0, mia = d.mia === emo;
      return el("button", { type: "button", class: "reacc" + (mia ? " activa" : ""), "aria-pressed": String(mia),
        "aria-label": `Reaccionar con ${emo}`,
        onclick: () => accion(api(`/api/historias/${h.id}/reaccion`, { method: "POST", body: { emoji: emo } })) },
        emo, ...(n ? [el("small", {}, String(n))] : []));
    }));

    const lista = el("ul", { class: "visor-coment" }, ...d.comentarios.map((c) => el("li", {},
      el("strong", {}, c.autor), " ", el("span", {}, c.texto),
      ...(c.puedo_borrar ? [el("button", { type: "button", class: "x", "aria-label": "Eliminar comentario",
        onclick: () => accion(api(`/api/historias/${h.id}/comentarios/${c.id}`, { method: "DELETE" })) }, "✕")] : []))));

    const inp = el("input", { placeholder: "Escribe un comentario…", maxlength: "200", "aria-label": "Comentar historia" });
    inp.addEventListener("focus", pausar);
    const form = el("form", { class: "visor-form" }, inp, botonEmoji(inp), el("button", { type: "submit", class: "mini" }, "Enviar"));
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const texto = inp.value.trim();
      if (texto) accion(api(`/api/historias/${h.id}/comentarios`, { method: "POST", body: { texto } }));
    });
    pie.replaceChildren(reacciones, ...(d.comentarios.length ? [lista] : []), form);
    lista.scrollTop = lista.scrollHeight;
  }

  function mostrar() {
    clearTimeout(timer);
    caja.classList.remove("pausa");
    const g = grupos[gi], h = g.historias[si];
    const barras = el("div", { class: "visor-barras" },
      ...g.historias.map((_, i) => el("span", { class: i < si ? "hecha" : i === si ? "actual" : "" })));
    const cab = el("div", { class: "visor-cab" }, avatar(g.autor, true, g.autor_foto),
      el("strong", {}, g.mio ? "Tu historia" : g.autor), el("small", {}, fecha(h.fecha)),
      el("span", { class: "espacio" }),
      ...(g.mio ? [el("button", { type: "button", class: "mini peligro", onclick: borrar }, "Eliminar")] : []),
      el("button", { type: "button", class: "mini sec", "aria-label": "Cerrar", onclick: () => cerrar() }, "✕"));
    const pie = el("div", { class: "visor-pie" });
    caja.replaceChildren(barras, cab,
      el("img", { class: "visor-img", src: `/api/imagenes/${h.imagen}`, alt: "Historia de " + g.autor }),
      ...(h.texto ? [el("p", { class: "visor-texto" }, h.texto)] : []),
      el("button", { type: "button", class: "visor-zona izq", "aria-label": "Anterior", onclick: anterior }),
      el("button", { type: "button", class: "visor-zona der", "aria-label": "Siguiente", onclick: siguiente }),
      pie);
    api(`/api/historias/${h.id}/interacciones`).then((d) => pintarInteracciones(pie, h, d)).catch(() => {});
    timer = setTimeout(siguiente, 5000);
  }

  cerrar = abrirModal(caja, () => clearTimeout(timer));
  mostrar();
}

async function pintarHistorias() {
  const grupos = await api("/api/historias");
  const archivo = el("input", { type: "file", accept: "image/png,image/jpeg,image/gif,image/webp", hidden: "" });
  archivo.addEventListener("change", () => {
    const f = archivo.files[0];
    archivo.value = "";
    if (f) nuevaHistoria(f);
  });
  const crear = el("button", { type: "button", class: "historia nueva", title: "Subir una historia",
    onclick: () => archivo.click() }, el("span", { class: "historia-aro" }, "+"), el("small", {}, "Agregar"), archivo);
  const items = grupos.map((g, i) => el("button", { type: "button", class: "historia", title: g.autor,
    onclick: () => verHistorias(grupos, i) },
    el("span", { class: "historia-aro" }, avatar(g.autor, false, g.autor_foto)),
    el("small", {}, g.mio ? "Tu historia" : g.autor.split(" ")[0])));
  $("historias").replaceChildren(crear, ...items);
}

/* ===================== Muro + comentarios (ARBOL) ===================== */
// Muro general (solo yo y mis amigos) o publicaciones de un grupo concreto
async function pintarPosts(cont, grupoId) {
  const posts = await api("/api/posts" + (grupoId ? `?grupo=${grupoId}` : ""));
  const vacio = grupoId ? "Aún no hay publicaciones en este grupo. ¡Escribe la primera!"
    : "Tu muro está vacío. Publica algo o agrega amigos para ver lo que comparten.";
  const recargar = () => pintarPosts(cont, grupoId);
  cont.replaceChildren(...(posts.length ? posts.map((p) => tarjetaPost(p, recargar)) : [el("p", { class: "muted vacio" }, vacio)]));
}

async function cargarPosts() {
  $("composer-muro").replaceChildren(composer(null, cargarPosts));
  await Promise.all([
    pintarHistorias().catch((e) => mostrarError("msg-app", e)),
    pintarPosts($("posts")),
  ]);
}

function tarjetaPost(p, alBorrar) {
  const zona = el("div", { hidden: "" });
  const btn = el("button", { class: "sec mini" }, `💬 Comentarios (${p.n_comentarios})`);
  btn.addEventListener("click", async () => {
    zona.hidden = !zona.hidden;
    if (!zona.hidden) await pintarComentarios(p.id, zona);
  });

  // Solo el autor ve el boton de eliminar
  const extra = [];
  if (p.mio) {
    const borrar = el("button", { type: "button", class: "mini peligro", title: "Eliminar publicación" }, "🗑 Eliminar");
    borrar.addEventListener("click", async () => {
      if (!confirm("¿Eliminar esta publicación? También se borrarán sus comentarios.")) return;
      borrar.disabled = true;
      try {
        await api(`/api/posts/${p.id}`, { method: "DELETE" });
        mostrarError("msg-app", null);
        await alBorrar();
      } catch (e) { borrar.disabled = false; mostrarError("msg-app", e); }
    });
    extra.push(el("span", { class: "espacio" }), borrar);
  }

  return el("div", { class: "card" },
    el("div", { class: "autor" }, avatar(p.autor, false, p.autor_foto),
      el("div", {}, el("strong", {}, p.autor), el("span", { class: "muted" }, fecha(p.fecha)))),
    ...(p.texto ? [el("p", { class: "texto" }, p.texto)] : []),
    ...(p.imagen ? [el("img", { class: "foto", src: `/api/imagenes/${p.imagen}`, alt: "Imagen publicada", loading: "lazy" })] : []),
    el("div", { class: "acciones" }, botonLike("post", p.id, p.likes, p.yo_like), btn, ...extra), zona);
}

// Descarga el arbol y lo recorre en DFS (preorden) con renderNodo
async function pintarComentarios(postId, zona) {
  const arbol = await api(`/api/posts/${postId}/comentarios`);
  const ul = el("ul", { class: "comentarios" });
  ul.append(...arbol.map((n) => renderNodo(n, 0, postId, zona)));
  zona.replaceChildren(ul, formRespuesta(postId, null, zona));
}

function renderNodo(nodo, profundidad, postId, zona) {
  const li = el("li", { class: "comentario" });
  const cuerpo = el("div", {},
    el("div", { class: "autor" }, avatar(nodo.autor, true, nodo.autor_foto), el("strong", {}, nodo.autor),
      el("span", { class: "meta" }, fecha(nodo.fecha))),
    el("p", { class: "texto" }, nodo.texto));
  const resp = el("button", { class: "sec mini" }, "Responder");
  const hueco = el("div");
  resp.addEventListener("click", () => {
    if (hueco.firstChild) hueco.replaceChildren();
    else hueco.append(formRespuesta(postId, nodo.id, zona));
  });
  li.append(cuerpo, el("div", { class: "acciones peq" }, botonLike("comment", nodo.id, nodo.likes, nodo.yo_like), resp), hueco);
  if (nodo.hijos.length) {                       // caso recursivo: visita cada subarbol
    const sub = el("ul");
    sub.append(...nodo.hijos.map((h) => renderNodo(h, profundidad + 1, postId, zona)));
    li.append(sub);
  }                                              // caso base: hoja
  return li;
}

function formRespuesta(postId, parentId, zona) {
  const inp = el("input", { placeholder: parentId ? "Tu respuesta…" : "Escribe un comentario…", maxlength: "500" });
  const ok = el("button", { class: "mini" }, "Enviar");
  ok.addEventListener("click", async () => {
    try {
      await api(`/api/posts/${postId}/comentarios`, { method: "POST", body: { texto: inp.value, parent_id: parentId } });
      await pintarComentarios(postId, zona);
    } catch (e) { mostrarError("msg-app", e); }
  });
  return el("div", { class: "form-resp" }, inp, botonEmoji(inp), ok);
}

/* ===================== Buscador (barra superior + filtros avanzados) ===================== */
let ultimaConsulta = "";
let ultimoFiltro = null;
let temporizador;

async function buscarTexto(q, sinNavegar = false) {
  q = q.trim();
  if (q.length < 2) return mostrarError("msg-app", new Error("Escribe al menos 2 letras para buscar"));
  ultimaConsulta = q;
  $("sugerencias").hidden = true;
  if (!sinNavegar) await irA("buscar", false);
  const r = await api(`/api/buscar-rapido?q=${encodeURIComponent(q)}`);
  $("res-rapidos").replaceChildren(
    el("div", { class: "card" }, el("h2", {}, `Personas (${r.personas.length})`),
      ...(r.personas.length ? r.personas.map(itemUsuario) : [el("p", { class: "muted" }, "Nadie coincide con tu búsqueda.")])),
    el("div", { class: "card" }, el("h2", {}, `Grupos (${r.grupos.length})`),
      ...(r.grupos.length ? r.grupos.map((g) => filaGrupo(g, () => buscarTexto(q, true))) : [el("p", { class: "muted" }, "Ningún grupo coincide.")])));
}

$("form-busqueda").addEventListener("submit", (ev) => {
  ev.preventDefault();
  buscarTexto($("q").value).catch((e) => mostrarError("msg-app", e));
});

$("q").addEventListener("input", () => {
  clearTimeout(temporizador);
  const q = $("q").value.trim();
  if (q.length < 2) { $("sugerencias").hidden = true; return; }
  temporizador = setTimeout(async () => {
    try {
      const r = await api(`/api/buscar-rapido?q=${encodeURIComponent(q)}`);
      const personas = r.personas.slice(0, 5).map((u) => el("button", { type: "button", class: "sug",
        onclick: () => { $("q").value = u.nombres; buscarTexto(u.nombres).catch((e) => mostrarError("msg-app", e)); } },
        avatar(u.nombres, true, u.foto), el("span", {}, el("strong", {}, u.nombres), el("small", {}, `${u.escuela} · ciclo ${u.ciclo}`))));
      const grupos = r.grupos.slice(0, 3).map((g) => el("button", { type: "button", class: "sug",
        onclick: () => { $("sugerencias").hidden = true; abrirGrupo(g.id); } },
        avatarGrupo(g, true), el("span", {}, el("strong", {}, g.nombre), el("small", {}, `${g.miembros} miembros`))));
      $("sugerencias").replaceChildren(...personas, ...grupos,
        el("button", { type: "submit", class: "sug todos" }, `Ver todos los resultados para “${q}”`));
      $("sugerencias").hidden = false;
    } catch { $("sugerencias").hidden = true; }
  }, 250);
});

function construirFiltro() {
  const fac = $("b-facultad").value.trim(), ciclo = $("b-ciclo").value, inte = $("b-interes").value.trim();
  const a = [];
  if (fac) a.push({ campo: "facultad", cmp: "==", valor: fac });
  if (ciclo) a.push({ campo: "ciclo", cmp: ">=", valor: Number(ciclo) });
  const A = a.length ? { op: "AND", args: a } : null;
  const B = inte ? { campo: "intereses", cmp: "CONTAINS", valor: inte } : null;
  if (A && B) {
    const c = $("b-comb").value;
    if (c === "ANDNOT") return { op: "AND", args: [A, { op: "NOT", arg: B }] };
    return { op: c, args: [A, B] };
  }
  return A || B;
}

async function ejecutarBusqueda() {
  const filtro = ultimoFiltro;
  const r = await api("/api/buscar", { method: "POST", body: { filtro } });
  $("resultados").replaceChildren(
    el("div", { class: "card" }, el("h2", {}, `Resultados del filtro (${r.resultados.length})`), ...r.resultados.map(itemUsuario)));
}

$("btn-buscar").addEventListener("click", async () => {
  const f = construirFiltro();
  if (!f) return mostrarError("msg-app", new Error("Ingresa al menos un criterio"));
  ultimoFiltro = f;
  mostrarError("msg-app", null);
  try { await ejecutarBusqueda(); } catch (e) { mostrarError("msg-app", e); }
});

/* ===================== Usuarios y amistad (AUTOMATA) ===================== */
function itemUsuario(u) {
  const rel = u.relacion || { estado: "INEXISTENTE" };
  const btn = (txt, fn, clase = "") => el("button", { class: `mini ${clase}`, onclick: fn }, txt);
  const acc = (evento) => () => accionAmistad(u.id, evento);
  const botones = [];

  switch (rel.estado) {
    case "INEXISTENTE": case "RECHAZADA":
      botones.push(btn("Enviar solicitud", acc("enviar"))); break;
    case "PENDIENTE":
      if (rel.emisor_soy_yo) botones.push(btn("Cancelar solicitud", acc("cancelar"), "sec"));
      else botones.push(btn("Aceptar", acc("aceptar")), btn("Rechazar", acc("rechazar"), "sec"));
      break;
    case "ACEPTADA":
      botones.push(btn("Mensaje", () => abrirMensajes(u.id)), btn("Eliminar amigo", acc("eliminar_amigo"), "sec")); break;
    case "BLOQUEADA":
      if (rel.bloqueado_por_mi) botones.push(btn("Desbloquear", acc("desbloquear")));
  }
  if (rel.estado !== "BLOQUEADA") botones.push(btn("Bloquear", acc("bloquear"), "peligro"));

  return el("div", { class: "usuario" }, avatar(u.nombres, false, u.foto),
    el("div", {}, el("strong", {}, u.nombres),
      el("span", { class: "tipo" }, `${u.facultad} · ${u.escuela} · ciclo ${u.ciclo}`),
      ...(u.bio ? [el("div", { class: "muted" }, u.bio)] : [])),
    el("div", {}, ...u.intereses.map((i) => el("span", { class: "etiqueta" }, i)),
      " ", el("span", { class: `estado ${rel.estado}` }, rel.estado)),
    el("div", {}, ...botones));
}

async function accionAmistad(id, evento) {
  try {
    await api(`/api/amistad/${id}/${evento}`, { method: "POST" });
    mostrarError("msg-app", null);
    if (tabActual === "buscar") {
      if (ultimaConsulta) await buscarTexto(ultimaConsulta, true);
      if (ultimoFiltro) await ejecutarBusqueda();
    } else if (tabActual === "amigos") await cargarAmigos();
  } catch (e) { mostrarError("msg-app", e); }
}

function panel(texto) {
  const p = $("panel-resultado");
  p.hidden = false;
  p.textContent = texto;
  p.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function cargarAmigos() {
  const d = await api("/api/amigos");
  const bloque = (titulo, lista) => el("div", { class: "card" }, el("h2", {}, `${titulo} (${lista.length})`),
    ...(lista.length ? lista.map(itemUsuario) : [el("p", { class: "muted" }, "—")]));
  $("listas-amigos").replaceChildren(
    bloque("Amigos", d.amigos), bloque("Solicitudes recibidas", d.recibidas),
    bloque("Solicitudes enviadas", d.enviadas), bloque("Bloqueados", d.bloqueados));
}

/* ===================== Grupos (conjunto de miembros) ===================== */
function avatarGrupo(g, peq = false, grande = false) {
  const tam = (peq ? " peq" : "") + (grande ? " grande" : "");
  if (g.foto) return el("img", { class: "avatar" + tam, src: `/api/imagenes/${g.foto}`, alt: g.nombre });
  return el("span", { class: "avatar grupo" + tam }, "👥");
}

// En la lista no hay "Abrir" ni "Salir": al presionar el grupo se entra, y para salir hay que estar dentro.
// Solo se ofrece "Unirme" a quien todavia no es miembro.
function filaGrupo(g, refrescar) {
  const botones = [];
  if (!g.soy_miembro) {
    botones.push(el("button", { class: "mini", onclick: async (ev) => {
      ev.stopPropagation();
      try { await api(`/api/grupos/${g.id}/unirse`, { method: "POST" }); mostrarError("msg-app", null); await refrescar(); }
      catch (e) { mostrarError("msg-app", e); }
    } }, "Unirme"));
  }
  return el("div", { class: "usuario foro fila-grupo clicable", role: "button", tabindex: "0",
    "aria-label": `Abrir grupo ${g.nombre}`,
    onclick: () => abrirGrupo(g.id),
    onkeydown: (ev) => { if (ev.key === "Enter" && ev.target === ev.currentTarget) abrirGrupo(g.id); } },
    avatarGrupo(g),
    el("div", { class: "grupo-info" }, el("strong", {}, g.nombre),
      el("span", { class: "tipo" }, `${g.miembros} miembro${g.miembros === 1 ? "" : "s"}`),
      g.descripcion ? el("p", { class: "muted" }, g.descripcion) : "",
      ...(botones.length ? [el("div", {}, ...botones)] : [])));
}

async function listarGrupos() {
  const lista = await api("/api/grupos");
  const nombre = el("input", { placeholder: "Nombre del grupo (ej. Matemática Discreta 2026)", maxlength: "60" });
  const desc = el("input", { placeholder: "Descripción (opcional)", maxlength: "200" });
  const crear = el("button", {}, "Crear grupo");
  crear.addEventListener("click", async () => {
    try {
      const r = await api("/api/grupos", { method: "POST", body: { nombre: nombre.value, descripcion: desc.value } });
      mostrarError("msg-app", null);
      await abrirGrupo(r.id);
    } catch (e) { mostrarError("msg-app", e); }
  });
  $("vista-grupos").replaceChildren(
    el("div", { class: "card" }, el("h2", {}, "Crea un grupo de estudio"),
      el("div", { class: "fila-2" }, nombre, crear), el("div", { class: "separa" }, desc)),
    el("div", { class: "card" }, el("h2", {}, `Grupos (${lista.length})`),
      ...(lista.length ? lista.map((g) => filaGrupo(g, listarGrupos)) : [el("p", { class: "muted vacio" }, "Todavía no hay grupos. ¡Crea el primero!")])));
}

async function mostrarGrupo(id) {
  const g = await api(`/api/grupos/${id}`);
  // Foto del grupo: solo la cambia el creador o un administrador
  const archivo = el("input", { type: "file", accept: "image/png,image/jpeg,image/gif,image/webp", hidden: "" });
  archivo.addEventListener("change", async () => {
    const f = archivo.files[0];
    if (!f) return;
    if (f.size > 2 * 1024 * 1024) return mostrarError("msg-app", new Error("La foto no puede pasar de 2 MB"));
    try {
      const fd = new FormData();
      fd.append("imagen", f);
      const { id: fotoId } = await api("/api/imagenes", { method: "POST", form: fd });
      await api(`/api/grupos/${id}/foto`, { method: "PUT", body: { foto_id: fotoId } });
      mostrarError("msg-app", null);
      await mostrarGrupo(id);
    } catch (e) { mostrarError("msg-app", e); }
  });
  const quitarFoto = async () => {
    try { await api(`/api/grupos/${id}/foto`, { method: "PUT", body: { foto_id: null } }); await mostrarGrupo(id); }
    catch (e) { mostrarError("msg-app", e); }
  };
  const botonesFoto = g.puedo_editar ? [
    el("button", { type: "button", class: "mini", onclick: () => archivo.click() }, g.foto ? "Cambiar foto" : "Subir foto"),
    ...(g.foto ? [el("button", { type: "button", class: "mini sec", onclick: quitarFoto }, "Quitar foto")] : []), archivo] : [];

  const cab = el("div", { class: "card" },
    el("button", { class: "sec mini", onclick: () => listarGrupos().catch((e) => mostrarError("msg-app", e)) }, "← Todos los grupos"),
    el("div", { class: "perfil-cab separa" }, avatarGrupo(g, false, true),
      el("div", {}, el("h2", {}, g.nombre),
        g.descripcion ? el("p", {}, g.descripcion) : "",
        el("p", { class: "muted" }, `${g.miembros} miembro${g.miembros === 1 ? "" : "s"}: ${g.nombres_miembros.join(", ")}${g.miembros > g.nombres_miembros.length ? "…" : ""}`),
        el("div", { class: "acciones" }, ...botonesFoto,
          ...(g.soy_creador ? [] : [el("button", { class: "mini " + (g.soy_miembro ? "sec" : ""), onclick: async () => {
            try { await api(`/api/grupos/${id}/unirse`, { method: "POST" }); await mostrarGrupo(id); }
            catch (e) { mostrarError("msg-app", e); }
          } }, g.soy_miembro ? "Salir del grupo" : "Unirme al grupo")]))))
  );
  const cont = el("div");
  const partes = [cab];
  if (g.soy_miembro) partes.push(composer(id, () => pintarPosts(cont, id)), cont);
  else partes.push(el("div", { class: "card" }, el("p", { class: "muted" }, "Únete al grupo para ver y compartir publicaciones.")));
  $("vista-grupos").replaceChildren(...partes);
  if (g.soy_miembro) await pintarPosts(cont, id);
}

function abrirGrupo(id) {
  return irA("grupos", false).then(() => mostrarGrupo(id)).catch((e) => mostrarError("msg-app", e));
}

/* ===================== Mensajes directos (solo entre amigos) ===================== */
let sondeo = null;            // temporizador que actualiza el chat abierto
let badgeIniciado = false;
function detenerSondeo() { clearInterval(sondeo); sondeo = null; }

async function actualizarBadge() {
  try {
    const { total } = await api("/api/mensajes-no-leidos");
    $("badge-msg").textContent = total > 99 ? "99+" : String(total);
    $("badge-msg").hidden = total === 0;
  } catch { /* sin sesion o sin red: se reintenta en el siguiente ciclo */ }
}

function abrirMensajes(id) {
  return irA("mensajes", false).then(() => cargarMensajes(id)).catch((e) => mostrarError("msg-app", e));
}

async function cargarMensajes(abrirId = null) {
  let convs = [], activo = null, traerActivo = null;
  const lista = el("div", { class: "chat-lista" });
  const panelChat = el("div", { class: "chat-panel" },
    el("p", { class: "muted vacio" }, "Elige un amigo para empezar a chatear."));
  $("vista-mensajes").replaceChildren(el("div", { class: "chat-layout" }, lista, panelChat));

  const pintarLista = () => lista.replaceChildren(...(convs.length ? convs.map((c) => {
    const item = el("button", { type: "button", class: "chat-item" + (c.id === activo ? " activo" : "") },
      avatar(c.nombres, true, c.foto),
      el("span", { class: "chat-meta" }, el("strong", {}, c.nombres), el("small", {}, c.ultimo || "Sin mensajes")),
      ...(c.no_leidos ? [el("span", { class: "badge" }, String(c.no_leidos))] : []));
    item.addEventListener("click", () => abrir(c).catch((e) => mostrarError("msg-app", e)));
    return item;
  }) : [el("p", { class: "muted vacio" }, "Agrega amigos para poder escribirles.")]));

  const abrir = async (c) => {
    activo = c.id;
    traerActivo = null;
    let ultimoId = null;
    const caja = el("div", { class: "chat-msgs", role: "log" });
    const inp = el("input", { placeholder: "Escribe un mensaje…", maxlength: "1000" });
    const enviar = el("button", { type: "submit" }, "Enviar");
    const form = el("form", { class: "chat-form" }, inp, botonEmoji(inp), enviar);

    const nodos = new Map();      // id de mensaje -> funcion que lo vuelve a pintar (para cambios en vivo)
    let sync = null;              // hora del servidor hasta la que ya vimos editados/eliminados

    const burbuja = (m0) => {
      let d = m0;
      const nodo = el("div", { class: "burbuja msg-wrap " + (d.mio ? "mia" : "suya") });
      const quitar = () => { nodo.remove(); nodos.delete(d.id); };

      const editar = () => {
        const inp = el("input", { value: d.texto, maxlength: "1000", "aria-label": "Editar mensaje" });
        const guardar = el("button", { type: "button", class: "mini" }, "Guardar");
        const cancelar = el("button", { type: "button", class: "mini sec" }, "Cancelar");
        const confirmar = async () => {
          const t = inp.value.trim();
          if (!t || t === d.texto) return pintar();
          guardar.disabled = true;
          try {
            d = await api(`/api/mensajes/${c.id}/${d.id}`, { method: "PUT", body: { texto: t } });
            mostrarError("msg-app", null);
            pintar();
          } catch (e) { guardar.disabled = false; mostrarError("msg-app", e); }
        };
        guardar.addEventListener("click", confirmar);
        cancelar.addEventListener("click", () => pintar());
        inp.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter") { ev.preventDefault(); confirmar(); }
          if (ev.key === "Escape") pintar();
        });
        nodo.replaceChildren(inp, el("div", { class: "msg-edit" }, guardar, cancelar));
        inp.focus();
      };

      const borrar = async (para) => {
        const aviso = para === "todos" ? "¿Eliminar este mensaje para todos?" : "¿Eliminar este mensaje solo para ti?";
        if (!confirm(aviso)) return;
        try {
          await api(`/api/mensajes/${c.id}/${d.id}?para=${para}`, { method: "DELETE" });
          mostrarError("msg-app", null);
          if (para === "mi") quitar();
          else { d = { ...d, eliminado: true, texto: "" }; pintar(); }
        } catch (e) { mostrarError("msg-app", e); }
      };

      function pintar() {
        nodo.classList.toggle("eliminada", d.eliminado);
        const menu = el("div", { class: "msg-menu", hidden: "" });
        const opcion = (txt, fn) => el("button", { type: "button", onclick: () => { menu.hidden = true; fn(); } }, txt);
        if (d.mio && !d.eliminado) menu.append(opcion("Editar", editar));
        menu.append(opcion("Eliminar para mí", () => borrar("mi")));
        if (d.mio && !d.eliminado) menu.append(opcion("Eliminar para todos", () => borrar("todos")));
        const abrirMenu = el("button", { type: "button", class: "msg-opc", "aria-label": "Opciones del mensaje",
          onclick: () => { menu.hidden = !menu.hidden; } }, "⋯");
        nodo.replaceChildren(
          el("p", { class: "texto" + (d.eliminado ? " msg-borrado" : "") }, d.eliminado ? "Se eliminó este mensaje" : d.texto),
          el("div", { class: "msg-pie" }, el("small", {}, fecha(d.fecha) + (d.editado ? " · editado" : "")), abrirMenu),
          menu);
      }

      pintar();
      nodos.set(d.id, (nuevo) => { d = nuevo; pintar(); });
      return nodo;
    };

    // Trae lo editado/eliminado por la otra persona desde la ultima vez
    const sincronizar = async () => {
      const r = await api(`/api/mensajes/${c.id}/cambios` + (sync ? `?desde=${encodeURIComponent(sync)}` : ""));
      sync = r.ahora;
      for (const m of r.cambios) { const act = nodos.get(m.id); if (act) act(m); }
    };
    const traer = async (forzar = false) => {
      const msgs = await api(`/api/mensajes/${c.id}` + (ultimoId ? `?despues=${ultimoId}` : ""));
      if (!msgs.length) return;
      const abajo = caja.scrollHeight - caja.scrollTop - caja.clientHeight < 60;
      caja.querySelector(".vacio")?.remove();
      caja.append(...msgs.map(burbuja));
      ultimoId = msgs[msgs.length - 1].id;
      if (forzar || abajo) caja.scrollTop = caja.scrollHeight;
    };

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const texto = inp.value.trim();
      if (!texto) return;
      enviar.disabled = true;
      try {
        await api(`/api/mensajes/${c.id}`, { method: "POST", body: { texto } });
        inp.value = "";
        mostrarError("msg-app", null);
        await traer(true);
      } catch (e) { mostrarError("msg-app", e); }
      enviar.disabled = false;
      inp.focus();
    });

    panelChat.replaceChildren(
      el("div", { class: "chat-cab" }, avatar(c.nombres, true, c.foto), el("strong", {}, c.nombres)), caja, form);
    pintarLista();
    await sincronizar();          // punto de partida de los cambios en vivo
    await traer(true);
    if (!ultimoId) caja.append(el("p", { class: "muted vacio" }, "Aún no hay mensajes. ¡Saluda!"));
    traerActivo = async () => { await traer(); await sincronizar(); };
    inp.focus();
    actualizarBadge();
  };

  // Cada 4 s: trae mensajes nuevos del chat abierto y refresca la lista (no leidos, ultimo mensaje)
  const tick = async () => {
    if (document.hidden) return;
    try { if (traerActivo) await traerActivo(); }
    catch (e) { traerActivo = null; mostrarError("msg-app", e); }
    try { convs = await api("/api/mensajes"); pintarLista(); } catch { /* se reintenta */ }
  };

  convs = await api("/api/mensajes");
  if (tabActual !== "mensajes") return;           // el usuario ya cambio de pestana
  pintarLista();
  detenerSondeo();
  sondeo = setInterval(tick, 4000);
  if (abrirId) {
    const c = convs.find((x) => x.id === abrirId);
    if (c) await abrir(c);
  }
}

/* ===================== Mi perfil ===================== */
async function cargarPerfil() {
  const [u, arbol] = await Promise.all([api("/api/me"), api("/api/unidades-publicas")]);
  const campo = (etiqueta, control) => el("label", {}, etiqueta, control);
  const nombres = el("input", { value: u.nombres, maxlength: "80", required: "" });
  const bio = el("textarea", { maxlength: "160", placeholder: "Cuéntale a San Marcos quién eres (máx. 160 caracteres)" });
  bio.value = u.bio || "";
  const escuela = el("select", {});
  llenarEscuelas(arbol, escuela);
  escuela.value = u.escuela_id;
  const ciclo = el("input", { type: "number", min: "1", max: "12", value: String(u.ciclo) });
  const intereses = el("input", { value: (u.intereses || []).join(", "), placeholder: "deportes, música, ajedrez" });
  const ok = el("p", { class: "ok", role: "status" });

  const archivo = el("input", { type: "file", accept: "image/png,image/jpeg,image/gif,image/webp", hidden: "" });
  archivo.addEventListener("change", async () => {
    const f = archivo.files[0];
    if (!f) return;
    if (f.size > 2 * 1024 * 1024) return mostrarError("msg-app", new Error("La foto no puede pasar de 2 MB"));
    try {
      const fd = new FormData();
      fd.append("imagen", f);
      const { id } = await api("/api/imagenes", { method: "POST", form: fd });
      pintarChip(await api("/api/perfil", { method: "PUT", body: { foto_id: id } }));
      mostrarError("msg-app", null);
      await cargarPerfil();
    } catch (e) { mostrarError("msg-app", e); }
  });
  const quitarFoto = async () => {
    try { pintarChip(await api("/api/perfil", { method: "PUT", body: { foto_id: null } })); await cargarPerfil(); }
    catch (e) { mostrarError("msg-app", e); }
  };

  const guardar = el("button", { type: "submit" }, "Guardar cambios");
  const form = el("form", {}, campo("Nombre completo", nombres), campo("Sobre mí", bio),
    campo("Escuela profesional", escuela), campo("Ciclo", ciclo), campo("Intereses", intereses),
    guardar, ok);
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const nuevo = await api("/api/perfil", { method: "PUT", body: {
        nombres: nombres.value, bio: bio.value, escuela_id: escuela.value, ciclo: ciclo.value,
        intereses: intereses.value } });
      pintarChip(nuevo);
      mostrarError("msg-app", null);
      $("vista-perfil").querySelector(".perfil-cab h2").textContent = nuevo.nombres;
      $("vista-perfil").querySelector(".perfil-cab p").textContent = `${nuevo.escuela} · ${nuevo.facultad} · ciclo ${nuevo.ciclo}`;
      ok.textContent = "✓ Perfil actualizado";
    } catch (e) { ok.textContent = ""; mostrarError("msg-app", e); }
  });

  $("vista-perfil").replaceChildren(
    el("div", { class: "card" },
      el("div", { class: "perfil-cab" }, avatar(u.nombres, false, u.foto, true),
        el("div", {}, el("h2", {}, u.nombres), el("p", { class: "muted" }, `${u.escuela} · ${u.facultad} · ciclo ${u.ciclo}`),
          el("div", { class: "acciones" },
            el("button", { type: "button", class: "mini", onclick: () => archivo.click() }, u.foto ? "Cambiar foto" : "Subir foto"),
            ...(u.foto ? [el("button", { type: "button", class: "mini sec", onclick: quitarFoto }, "Quitar foto")] : []), archivo)))),
    el("div", { class: "card" }, el("h2", {}, "Editar perfil"), form));
}

/* ===================== Configuracion ===================== */
function cargarConfig() {
  const valor = el("strong", {}, `${fuentePx} px`);
  const rango = el("input", { type: "range", min: String(FUENTE_MIN), max: String(FUENTE_MAX), step: "1",
    value: String(fuentePx), "aria-label": "Tamaño de letra" });
  const poner = (px) => {
    px = Math.min(FUENTE_MAX, Math.max(FUENTE_MIN, px));
    aplicarFuente(px);
    rango.value = String(px);
    valor.textContent = `${px} px`;
  };
  rango.addEventListener("input", () => poner(Number(rango.value)));

  const menos = el("button", { type: "button", class: "sec mini", "aria-label": "Reducir letra", onclick: () => poner(fuentePx - 1) }, "A−");
  const mas = el("button", { type: "button", class: "sec mini", "aria-label": "Aumentar letra", onclick: () => poner(fuentePx + 1) }, "A+");
  const reset = el("button", { type: "button", class: "mini", onclick: () => poner(FUENTE_DEF) }, "Restablecer");

  const botonesTema = TEMAS.map((t) => el("button", { type: "button", class: t === temaPref ? "activo" : "",
    onclick: () => {
      aplicarTema(t);
      botonesTema.forEach((b, i) => b.classList.toggle("activo", TEMAS[i] === t));
    } }, { claro: "Claro", oscuro: "Oscuro", auto: "Automático" }[t]));

  $("vista-config").replaceChildren(
    el("div", { class: "card" }, el("h2", {}, "Apariencia"),
      el("p", { class: "muted" }, "Elige el tema de la aplicación. «Automático» sigue el modo de tu dispositivo."),
      el("div", { class: "segmento tres" }, ...botonesTema)),
    el("div", { class: "card" }, el("h2", {}, "Tamaño de letra"),
      el("p", { class: "muted" }, "Ajusta el tamaño del texto de toda la aplicación. Se guarda en este navegador."),
      el("div", { class: "config-fila" }, menos, rango, mas, valor),
      el("div", { class: "config-fila" }, reset),
      el("div", { class: "config-muestra" },
        el("strong", {}, "Así se ve tu texto"),
        el("p", {}, "Bienvenido a LogKeate, la red social de los sanmarquinos."))));
}

iniciar();