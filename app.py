import os
import re
from datetime import datetime, timezone, timedelta
from functools import wraps

from bson import ObjectId
from bson.binary import Binary
from bson.errors import InvalidId
from flask import Flask, Response, jsonify, request, session, send_from_directory
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash, check_password_hash

from db import db, crear_indices
import servicios
from servicios import Conflicto
from dominio import validacion, busqueda, conjuntos, grafo, arboles
from dominio.solicitud_fsm import Ev, E, TransicionInvalida
from dominio import solicitud_fsm
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.getenv("SECRET_KEY", "dev-no-usar-en-produccion")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("APP_ENV") == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=3 * 1024 * 1024,   # tope global (las imagenes admiten 2 MB)
)
crear_indices()


# ---------- utilidades ----------
class ErrorApi(Exception):
    def __init__(self, msg, code=400):
        self.msg, self.code = msg, code


@app.errorhandler(ErrorApi)
def _err(e):
    return jsonify(error=e.msg), e.code


def oid(s):
    try:
        return ObjectId(s)
    except (InvalidId, TypeError):
        raise ErrorApi("Identificador invalido", 400)


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if "uid" not in session:
            raise ErrorApi("Debes iniciar sesion", 401)
        return f(*a, **k)
    return w


def yo():
    return ObjectId(session["uid"])


def datos():
    if request.content_length and request.content_length > 64 * 1024:
        raise ErrorApi("Solicitud demasiado grande", 413)
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise ErrorApi("Se esperaba JSON")
    return d


def lista_texto(v, normalizar):
    if isinstance(v, str):
        v = v.split(",")
    if not isinstance(v, list):
        return []
    return sorted({normalizar(str(x).strip()) for x in v if str(x).strip()})[:30]


def publico(u, rel=None):
    out = {"id": str(u["_id"]), "nombres": u["nombres"], "facultad": u.get("facultad"),
           "escuela": u.get("escuela"), "ciclo": u.get("ciclo"), "intereses": u.get("intereses", []),
           "bio": u.get("bio", ""), "foto": str(u["foto_id"]) if u.get("foto_id") else None}
    if rel is not None:
        out["relacion"] = rel
    return out


def resumen_relacion(me, doc):
    if not doc:
        return {"estado": "INEXISTENTE"}
    return {"estado": doc["estado"], "emisor_soy_yo": doc["emisor"] == me,
            "bloqueado_por_mi": doc.get("bloqueado_por") == me}


PROY = {"pass_hash": 0, "email": 0}


# ---------- paginas ----------
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------- autenticacion (logica proposicional) ----------
@app.post("/api/registro")
def registro():
    d = datos()
    email = validacion.normalizar_correo(d.get("email", ""))
    password = str(d.get("password", ""))
    existe = servicios.correo_ya_registrado(email)
    if not validacion.correo_institucional(email):
        raise ErrorApi("Solo se permiten correos @unmsm.edu.pe")
    if not validacion.password_valida(password):
        raise ErrorApi("La contrasena debe tener 8+ caracteres, letras y numeros")
    if not validacion.registro_valido(email, password, existe):
        raise ErrorApi("Ese correo ya esta registrado", 409)

    nombres = str(d.get("nombres", "")).strip()[:80]
    if len(nombres) < 2:
        raise ErrorApi("Nombre requerido")
    try:
        ciclo = int(d.get("ciclo"))
    except (TypeError, ValueError):
        raise ErrorApi("Ciclo invalido")
    if not 1 <= ciclo <= 12:
        raise ErrorApi("Ciclo debe estar entre 1 y 12")
    escuela = db.academic_units.find_one({"_id": str(d.get("escuela_id")), "tipo": "escuela"})
    if not escuela:
        raise ErrorApi("Escuela invalida")
    facultad = db.academic_units.find_one({"_id": escuela["parent_id"]})

    try:
        r = db.users.insert_one({
            "email": email, "pass_hash": generate_password_hash(password),
            "nombres": nombres, "escuela_id": escuela["_id"], "escuela": escuela["nombre"],
            "facultad_id": facultad["_id"], "facultad": facultad.get("sigla", facultad["nombre"]),
            "ciclo": ciclo,
            "intereses": lista_texto(d.get("intereses", []), str.lower),
            "cursos": lista_texto(d.get("cursos", []), str.upper),
            "creado": datetime.now(timezone.utc),
        })
    except DuplicateKeyError:
        raise ErrorApi("Ese correo ya esta registrado", 409)
    session.clear()
    session["uid"] = str(r.inserted_id)
    session.permanent = True
    return jsonify(ok=True), 201


@app.post("/api/login")
def login():
    d = datos()
    crudo = str(d.get("email", "")).strip().lower()
    u = db.users.find_one({"email": {"$in": [validacion.normalizar_correo(crudo), crudo]}})
    if not u or not check_password_hash(u["pass_hash"], str(d.get("password", ""))):
        raise ErrorApi("Credenciales incorrectas", 401)
    session.clear()
    session["uid"] = str(u["_id"])
    session.permanent = True
    return jsonify(ok=True)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
@login_required
def me():
    u = db.users.find_one({"_id": yo()}, PROY)
    return jsonify({**publico(u), "cursos": u.get("cursos", []), "escuela_id": u.get("escuela_id")})


@app.put("/api/perfil")
@login_required
def editar_perfil():
    """Edita solo los campos enviados. El correo y la contrasena no se cambian aqui."""
    d = datos()
    uid = yo()
    poner, quitar = {}, {}
    if "nombres" in d:
        n = " ".join(str(d["nombres"]).split())[:80]
        if len(n) < 2:
            raise ErrorApi("El nombre debe tener al menos 2 caracteres")
        poner["nombres"] = n
    if "bio" in d:
        poner["bio"] = str(d["bio"]).strip()[:160]
    if "ciclo" in d:
        try:
            ciclo = int(d["ciclo"])
        except (TypeError, ValueError):
            raise ErrorApi("Ciclo invalido")
        if not 1 <= ciclo <= 12:
            raise ErrorApi("Ciclo debe estar entre 1 y 12")
        poner["ciclo"] = ciclo
    if d.get("escuela_id"):
        esc = db.academic_units.find_one({"_id": str(d["escuela_id"]), "tipo": "escuela"})
        if not esc:
            raise ErrorApi("Escuela invalida")
        fac = db.academic_units.find_one({"_id": esc["parent_id"]})
        poner.update(escuela_id=esc["_id"], escuela=esc["nombre"],
                     facultad_id=fac["_id"], facultad=fac.get("sigla", fac["nombre"]))
    if "intereses" in d:
        poner["intereses"] = lista_texto(d["intereses"], str.lower)
    if "cursos" in d:
        poner["cursos"] = lista_texto(d["cursos"], str.upper)
    if "foto_id" in d:
        actual = (db.users.find_one({"_id": uid}, {"foto_id": 1}) or {}).get("foto_id")
        if d["foto_id"]:
            nueva = oid(d["foto_id"])
            if not db.images.find_one({"_id": nueva, "owner": uid}, {"_id": 1}):
                raise ErrorApi("Imagen invalida")
            poner["foto_id"] = nueva
        else:
            nueva = None
            quitar["foto_id"] = ""
        if actual and actual != nueva:
            db.images.delete_one({"_id": actual, "owner": uid})      # no dejar fotos viejas huerfanas
    if not poner and not quitar:
        raise ErrorApi("No hay cambios para guardar")
    db.users.update_one({"_id": uid}, {k: v for k, v in (("$set", poner), ("$unset", quitar)) if v})
    if "nombres" in poner:                      # las publicaciones y comentarios guardan una copia del nombre
        db.posts.update_many({"autor": uid}, {"$set": {"autor_nombre": poner["nombres"]}})
        db.comments.update_many({"autor": uid}, {"$set": {"autor_nombre": poner["nombres"]}})
    return me()


# ---------- buscador (algebra de Boole) ----------
@app.post("/api/buscar")
@login_required
def buscar():
    d = datos()
    try:
        consulta = busqueda.compilar(d.get("filtro"))
    except busqueda.FiltroInvalido as e:
        raise ErrorApi(str(e))
    yo_id = yo()
    rels = servicios.relaciones_con(yo_id)
    bloqueadores = [ObjectId(k) for k, v in rels.items()
                    if v["estado"] == "BLOQUEADA" and v.get("bloqueado_por") != yo_id]
    q = {"$and": [consulta, {"_id": {"$ne": yo_id}}, {"_id": {"$nin": bloqueadores}}]}
    res = [publico(u, resumen_relacion(yo_id, rels.get(str(u["_id"]))))
           for u in db.users.find(q, PROY).limit(50)]
    return jsonify(resultados=res, consulta_mongo=consulta)


# ---------- conjuntos ----------
@app.get("/api/cursos-comunes/<otro>")
@login_required
def cursos_comunes(otro):
    a = db.users.find_one({"_id": yo()})
    b = db.users.find_one({"_id": oid(otro)})
    if not b:
        raise ErrorApi("Usuario no encontrado", 404)
    ca, cb = a.get("cursos", []), b.get("cursos", [])
    return jsonify(
        otro=b["nombres"],
        interseccion=sorted(conjuntos.interseccion(ca, cb)),
        union=sorted(conjuntos.union(ca, cb)),
        solo_mios=sorted(conjuntos.diferencia(ca, cb)),
        jaccard=round(conjuntos.jaccard(ca, cb), 3),
    )


# ---------- amistades (automata + grafo) ----------
@app.post("/api/amistad/<otro>/<evento>")
@login_required
def amistad(otro, evento):
    otro_id = oid(otro)
    if otro_id == yo():
        raise ErrorApi("No puedes relacionarte contigo mismo")
    if not db.users.find_one({"_id": otro_id}, {"_id": 1}):
        raise ErrorApi("Usuario no encontrado", 404)
    try:
        ev = Ev(evento)
    except ValueError:
        raise ErrorApi("Evento desconocido")
    try:
        nuevo = servicios.aplicar_evento(yo(), otro_id, ev)
    except TransicionInvalida as e:
        raise ErrorApi(str(e), 409)
    except Conflicto as e:
        raise ErrorApi(str(e), 409)
    return jsonify(estado=nuevo.value)


@app.get("/api/amigos")
@login_required
def amigos():
    me_id = yo()
    rels = servicios.relaciones_con(me_id)
    ids = [ObjectId(k) for k in rels]
    users = {str(u["_id"]): u for u in db.users.find({"_id": {"$in": ids}}, PROY)}
    out = {"amigos": [], "recibidas": [], "enviadas": [], "bloqueados": []}
    for k, d in rels.items():
        u = users.get(k)
        if not u:
            continue
        p = publico(u, resumen_relacion(me_id, d))
        if d["estado"] == "ACEPTADA":
            out["amigos"].append(p)
        elif d["estado"] == "PENDIENTE":
            out["enviadas" if d["emisor"] == me_id else "recibidas"].append(p)
        elif d["estado"] == "BLOQUEADA" and d.get("bloqueado_por") == me_id:
            out["bloqueados"].append(p)
    return jsonify(out)


@app.get("/api/grados/<otro>")
@login_required
def grados(otro):
    destino = oid(otro)
    d = db.users.find_one({"_id": destino}, {"nombres": 1})
    if not d:
        raise ErrorApi("Usuario no encontrado", 404)
    dist, camino = grafo.grados_de_separacion(yo(), destino, servicios.vecinos, max_prof=6)
    if dist is None:
        return jsonify(distancia=None, camino=[], mensaje="Sin conexion (hasta 6 grados)")
    nombres = {u["_id"]: u["nombres"] for u in db.users.find({"_id": {"$in": camino}}, {"nombres": 1})}
    return jsonify(distancia=dist, camino=[nombres.get(i, "?") for i in camino])

@app.get("/api/automata")
@login_required
def automata():
    """Expone M = (Q, Sigma, delta, q0, F) tal cual esta en el dominio (fuente unica de verdad)."""
    return jsonify(
        Q=[e.value for e in E], Sigma=[e.value for e in Ev], q0=solicitud_fsm.Q0.value,
        F=[e.value for e in solicitud_fsm.F],
        delta=[{"de": q.value, "evento": a.value, "a": r.value} for (q, a), r in solicitud_fsm.DELTA.items()])


@app.get("/api/grafo/resumen")
@login_required
def grafo_resumen():
    """G = (V, E) de toda la red + comprobacion del lema del apreton de manos."""
    aristas = list(db.friendships.find({}, {"u": 1, "v": 1}))
    grados = {}
    for a in aristas:
        grados[a["u"]] = grados.get(a["u"], 0) + 1
        grados[a["v"]] = grados.get(a["v"], 0) + 1
    n_v = db.users.count_documents({})
    mis_amigos = len(servicios.vecinos(yo()))
    return jsonify(
        V=n_v, E=len(aristas), suma_grados=sum(grados.values()),
        apreton_de_manos=grafo.verificar_apreton_de_manos(list(grados.values()), len(aristas)),
        grado_maximo=max(grados.values(), default=0), mi_grado=mis_amigos,
        grado_impar=sum(1 for g in grados.values() if g % 2))
# ---------- arboles ----------
@app.get("/api/unidades-publicas")
def unidades_publicas():
    """El formulario de registro necesita las escuelas antes de iniciar sesion."""
    return jsonify(arboles.construir_arbol_unidades(list(db.academic_units.find())))


# ---------- imagenes (se guardan en MongoDB: no dependen del disco del hosting) ----------
MAX_IMG = 2 * 1024 * 1024
FIRMAS = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"),
          (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"))


def tipo_imagen(b: bytes):
    """Detecta el formato por sus primeros bytes (no confia en la extension del archivo)."""
    for firma, mime in FIRMAS:
        if b.startswith(firma):
            return mime
    return "image/webp" if b[:4] == b"RIFF" and b[8:12] == b"WEBP" else None


@app.post("/api/imagenes")
@login_required
def subir_imagen():
    f = request.files.get("imagen")
    data = f.read(MAX_IMG + 1) if f else b""
    if not data:
        raise ErrorApi("Elige una imagen")
    if len(data) > MAX_IMG:
        raise ErrorApi("La imagen no puede pasar de 2 MB", 413)
    mime = tipo_imagen(data)
    if not mime:
        raise ErrorApi("Formato no permitido (usa PNG, JPG, GIF o WEBP)")
    r = db.images.insert_one({"owner": yo(), "mime": mime, "data": Binary(data), "creado": datetime.now(timezone.utc)})
    return jsonify(id=str(r.inserted_id)), 201


@app.get("/api/imagenes/<img_id>")
@login_required
def ver_imagen(img_id):
    im = db.images.find_one({"_id": oid(img_id)})
    if not im:
        raise ErrorApi("Imagen no encontrada", 404)
    return Response(bytes(im["data"]), mimetype=im["mime"],
                    headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})


# ---------- publicaciones, comentarios (arbol) y me gusta ----------
def acceso_post(p):
    """Grupo: solo miembros. Muro general: solo el autor o sus amigos."""
    g = p.get("grupo_id")
    if g:
        if not db.group_members.find_one({"grupo_id": g, "user": yo()}, {"_id": 1}):
            raise ErrorApi("Solo los miembros del grupo pueden ver esto", 403)
        return
    autor = p.get("autor")
    if autor != yo() and autor not in servicios.vecinos(yo()):
        raise ErrorApi("Solo puedes ver publicaciones tuyas o de tus amigos", 403)


def fotos_de(ids):
    """{id de usuario: id de su foto de perfil} solo para quienes tienen foto."""
    return {u["_id"]: str(u["foto_id"]) for u in
            db.users.find({"_id": {"$in": list(set(ids))}, "foto_id": {"$exists": True}}, {"foto_id": 1})}


def likes_de(tipo, ids):
    """Cada 'me gusta' es un par (usuario, objeto): una relacion usuario -> objeto sin repeticiones."""
    cuenta = {d["_id"]: d["n"] for d in db.likes.aggregate([
        {"$match": {"tipo": tipo, "obj": {"$in": ids}}}, {"$group": {"_id": "$obj", "n": {"$sum": 1}}}])}
    mios = {d["obj"] for d in db.likes.find({"tipo": tipo, "obj": {"$in": ids}, "user": yo()}, {"obj": 1})}
    return cuenta, mios


def serializar_posts(docs):
    cuenta, mios = likes_de("post", [p["_id"] for p in docs])
    fotos = fotos_de([p["autor"] for p in docs])
    out = []
    for p in docs:
        item = {"id": str(p["_id"]), "autor": p["autor_nombre"], "autor_foto": fotos.get(p["autor"]),
                "texto": p.get("texto", ""),
                "imagen": str(p["imagen_id"]) if p.get("imagen_id") else None,
                "fecha": p["creado"].isoformat(), "likes": cuenta.get(p["_id"], 0),
                "yo_like": p["_id"] in mios,
                "n_comentarios": db.comments.count_documents({"post_id": p["_id"]})}
        out.append(item)
    return out


@app.get("/api/posts")
@login_required
def posts():
    g = request.args.get("grupo")
    if g:
        gid = oid(g)
        acceso_post({"grupo_id": gid})
        filtro = {"grupo_id": gid}
    else:
        # Muro general: solo mis publicaciones y las de mis amigos, sin las de grupos
        permitidos = servicios.vecinos(yo()) + [yo()]
        filtro = {"grupo_id": {"$exists": False}, "autor": {"$in": permitidos}}
    docs = list(db.posts.find(filtro).sort("creado", -1).limit(30))
    return jsonify(serializar_posts(docs))


@app.post("/api/posts")
@login_required
def crear_post():
    d = datos()
    texto = str(d.get("texto", "")).strip()
    img = None
    if d.get("imagen_id"):
        img = oid(d["imagen_id"])
        if not db.images.find_one({"_id": img, "owner": yo()}, {"_id": 1}):
            raise ErrorApi("Imagen invalida")
    if len(texto) > 1000 or (not texto and not img):
        raise ErrorApi("Escribe algo (maximo 1000 caracteres) o agrega una imagen")
    u = db.users.find_one({"_id": yo()}, {"nombres": 1})
    doc = {"autor": u["_id"], "autor_nombre": u["nombres"], "texto": texto, "creado": datetime.now(timezone.utc)}
    if img:
        doc["imagen_id"] = img
    if d.get("grupo_id"):
        doc["grupo_id"] = oid(d["grupo_id"])
        acceso_post(doc)
    db.posts.insert_one(doc)
    return jsonify(ok=True), 201


@app.get("/api/posts/<post_id>/comentarios")
@login_required
def comentarios(post_id):
    p = db.posts.find_one({"_id": oid(post_id)})
    if not p:
        raise ErrorApi("Publicacion no encontrada", 404)
    acceso_post(p)
    docs = list(db.comments.find({"post_id": p["_id"]}))
    cuenta, mios = likes_de("comment", [c["_id"] for c in docs])
    fotos = fotos_de([c["autor"] for c in docs])
    return jsonify(arboles.construir_arbol_comentarios(docs, cuenta, mios, fotos))


@app.post("/api/posts/<post_id>/comentarios")
@login_required
def comentar(post_id):
    pid = oid(post_id)
    d = datos()
    texto = str(d.get("texto", "")).strip()
    if not 1 <= len(texto) <= 500:
        raise ErrorApi("El comentario debe tener entre 1 y 500 caracteres")
    p = db.posts.find_one({"_id": pid})
    if not p:
        raise ErrorApi("Publicacion no encontrada", 404)
    acceso_post(p)
    padre = None
    if d.get("parent_id"):
        padre = oid(d["parent_id"])
        if not db.comments.find_one({"_id": padre, "post_id": pid}, {"_id": 1}):
            raise ErrorApi("Comentario padre invalido", 400)
    u = db.users.find_one({"_id": yo()}, {"nombres": 1})
    db.comments.insert_one({"post_id": pid, "parent_id": padre, "autor": u["_id"],
                            "autor_nombre": u["nombres"], "texto": texto,
                            "creado": datetime.now(timezone.utc)})
    return jsonify(ok=True), 201


@app.post("/api/likes/<tipo>/<obj_id>")
@login_required
def like(tipo, obj_id):
    """Alterna el 'me gusta' del usuario sobre una publicacion o un comentario."""
    if tipo not in ("post", "comment"):
        raise ErrorApi("Tipo invalido")
    o = oid(obj_id)
    obj = db.posts.find_one({"_id": o}) if tipo == "post" else db.comments.find_one({"_id": o})
    if not obj:
        raise ErrorApi("No encontrado", 404)
    acceso_post(obj if tipo == "post" else (db.posts.find_one({"_id": obj["post_id"]}) or {}))
    clave = {"tipo": tipo, "obj": o, "user": yo()}
    if db.likes.delete_one(clave).deleted_count:
        liked = False
    else:
        try:
            db.likes.insert_one({**clave, "creado": datetime.now(timezone.utc)})
        except DuplicateKeyError:
            pass
        liked = True
    return jsonify(liked=liked, total=db.likes.count_documents({"tipo": tipo, "obj": o}))


# ---------- grupos (un grupo es el CONJUNTO de sus miembros) ----------
def es_admin_grupo(g, me_id):
    """El creador y los miembros con rol 'admin' pueden editar el grupo."""
    if g["creador"] == me_id:
        return True
    return db.group_members.find_one({"grupo_id": g["_id"], "user": me_id, "rol": "admin"}, {"_id": 1}) is not None


def resumen_grupo(g, me_id):
    return {"id": str(g["_id"]), "nombre": g["nombre"], "descripcion": g.get("descripcion", ""),
            "foto": str(g["foto_id"]) if g.get("foto_id") else None,
            "puedo_editar": es_admin_grupo(g, me_id),
            "miembros": db.group_members.count_documents({"grupo_id": g["_id"]}),
            "soy_miembro": db.group_members.find_one({"grupo_id": g["_id"], "user": me_id}, {"_id": 1}) is not None,
            "soy_creador": g["creador"] == me_id}


@app.get("/api/grupos")
@login_required
def grupos():
    me_id = yo()
    return jsonify([resumen_grupo(g, me_id) for g in db.groups.find().sort("creado", -1).limit(100)])


@app.post("/api/grupos")
@login_required
def crear_grupo():
    d = datos()
    nombre = " ".join(str(d.get("nombre", "")).split())
    desc = str(d.get("descripcion", "")).strip()[:200]
    if not 3 <= len(nombre) <= 60:
        raise ErrorApi("El nombre debe tener entre 3 y 60 caracteres")
    ahora = datetime.now(timezone.utc)
    try:
        r = db.groups.insert_one({"nombre": nombre, "nombre_norm": nombre.lower(), "descripcion": desc,
                                  "creador": yo(), "creado": ahora})
    except DuplicateKeyError:
        raise ErrorApi("Ya existe un grupo con ese nombre", 409)
    db.group_members.insert_one({"grupo_id": r.inserted_id, "user": yo(), "rol": "admin", "desde": ahora})
    return jsonify(id=str(r.inserted_id)), 201


@app.get("/api/grupos/<gid>")
@login_required
def ver_grupo(gid):
    g = db.groups.find_one({"_id": oid(gid)})
    if not g:
        raise ErrorApi("Grupo no encontrado", 404)
    ids = [m["user"] for m in db.group_members.find({"grupo_id": g["_id"]}).limit(30)]
    nombres = sorted(u["nombres"] for u in db.users.find({"_id": {"$in": ids}}, {"nombres": 1}))
    return jsonify({**resumen_grupo(g, yo()), "nombres_miembros": nombres})


@app.post("/api/grupos/<gid>/unirse")
@login_required
def unirse_grupo(gid):
    g = db.groups.find_one({"_id": oid(gid)})
    if not g:
        raise ErrorApi("Grupo no encontrado", 404)
    clave = {"grupo_id": g["_id"], "user": yo()}
    if db.group_members.find_one(clave):
        if g["creador"] == yo():
            raise ErrorApi("El creador no puede salirse de su grupo")
        db.group_members.delete_one(clave)
        return jsonify(miembro=False)
    try:
        db.group_members.insert_one({**clave, "rol": "miembro", "desde": datetime.now(timezone.utc)})
    except DuplicateKeyError:
        pass
    return jsonify(miembro=True)


@app.put("/api/grupos/<gid>/foto")
@login_required
def foto_grupo(gid):
    """Pone o quita la foto del grupo. Solo el creador o un administrador del grupo."""
    g = db.groups.find_one({"_id": oid(gid)})
    if not g:
        raise ErrorApi("Grupo no encontrado", 404)
    if not es_admin_grupo(g, yo()):
        raise ErrorApi("Solo el creador o un administrador puede cambiar la foto del grupo", 403)
    d = datos()
    actual = g.get("foto_id")
    if d.get("foto_id"):
        nueva = oid(d["foto_id"])
        if not db.images.find_one({"_id": nueva, "owner": yo()}, {"_id": 1}):
            raise ErrorApi("Imagen invalida")
        db.groups.update_one({"_id": g["_id"]}, {"$set": {"foto_id": nueva}})
    else:
        nueva = None
        db.groups.update_one({"_id": g["_id"]}, {"$unset": {"foto_id": ""}})
    if actual and actual != nueva:
        db.images.delete_one({"_id": actual})          # no dejar fotos viejas huerfanas
    return jsonify(resumen_grupo(db.groups.find_one({"_id": g["_id"]}), yo()))


# ---------- buscador rapido (personas y grupos) ----------
@app.get("/api/buscar-rapido")
@login_required
def buscar_rapido():
    q = str(request.args.get("q", "")).strip()[:60]
    if len(q) < 2:
        return jsonify(personas=[], grupos=[])
    rx = {"$regex": re.escape(q), "$options": "i"}      # re.escape evita inyectar expresiones regulares
    yo_id = yo()
    rels = servicios.relaciones_con(yo_id)
    bloqueadores = [ObjectId(k) for k, v in rels.items()
                    if v["estado"] == "BLOQUEADA" and v.get("bloqueado_por") != yo_id]
    filtro = {"$and": [{"$or": [{"nombres": rx}, {"escuela": rx}, {"facultad": rx}]},
                       {"_id": {"$ne": yo_id}}, {"_id": {"$nin": bloqueadores}}]}
    personas = [publico(u, resumen_relacion(yo_id, rels.get(str(u["_id"]))))
                for u in db.users.find(filtro, PROY).limit(20)]
    return jsonify(personas=personas, grupos=[resumen_grupo(g, yo_id) for g in db.groups.find({"nombre": rx}).limit(10)])


if __name__ == "__main__":
    app.run(debug=os.getenv("APP_ENV") != "production")