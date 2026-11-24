"""Capa de persistencia: conecta el dominio (FSM, grafo) con MongoDB."""
from pymongo.errors import DuplicateKeyError

from db import db
from dominio import validacion
from dominio.solicitud_fsm import Solicitud, E, Ev, TransicionInvalida


class Conflicto(Exception):
    pass


def clave_par(a, b) -> str:
    x, y = sorted([str(a), str(b)])
    return f"{x}|{y}"


def _arista(a, b):
    """Par canonico (u < v): la simetria de la relacion de amistad se cumple por construccion."""
    return (a, b) if str(a) < str(b) else (b, a)


def aplicar_evento(actor, otro, evento: Ev) -> E:
    par = clave_par(actor, otro)
    doc = db.friend_requests.find_one({"par": par})
    if doc:
        sol = Solicitud(doc["emisor"], doc["receptor"], E(doc["estado"]), doc.get("bloqueado_por"))
    else:
        sol = Solicitud()
    previo = sol.estado
    nuevo = sol.aplicar(evento, actor, otro)          # puede lanzar TransicionInvalida

    campos = {"emisor": sol.emisor, "receptor": sol.receptor,
              "estado": nuevo.value, "bloqueado_por": sol.bloqueado_por}
    if doc is None:
        try:
            db.friend_requests.insert_one({"par": par, **campos, "historial": sol.historial})
        except DuplicateKeyError:
            raise Conflicto("Otra operacion se adelanto; intenta de nuevo")
    else:
        # Control optimista: solo actualiza si el estado sigue siendo el que leimos
        res = db.friend_requests.update_one(
            {"par": par, "estado": previo.value},
            {"$set": campos, "$push": {"historial": sol.historial[-1]}},
        )
        if res.matched_count == 0:
            raise Conflicto("Otra operacion se adelanto; intenta de nuevo")

    # Efectos sobre el grafo de amistades
    u, v = _arista(actor, otro)
    if nuevo == E.ACEPTADA:
        db.friendships.update_one({"u": u, "v": v}, {"$setOnInsert": {"u": u, "v": v}}, upsert=True)
    elif previo == E.ACEPTADA:
        db.friendships.delete_one({"u": u, "v": v})
    return nuevo


def vecinos(uid) -> list:
    """Lista de adyacencia de un vertice (amigos)."""
    docs = db.friendships.find({"$or": [{"u": uid}, {"v": uid}]})
    return [d["v"] if d["u"] == uid else d["u"] for d in docs]


def grafo_amistades() -> dict:
    """Lista de adyacencia de TODA la red con UNA sola consulta: {vertice: [amigos]}.
    El BFS trabaja luego en memoria, en vez de hacer una consulta a la BD por cada vertice visitado."""
    ady = {}
    for d in db.friendships.find({}, {"u": 1, "v": 1, "_id": 0}):
        ady.setdefault(d["u"], []).append(d["v"])
        ady.setdefault(d["v"], []).append(d["u"])
    return ady


def relaciones_con(me) -> dict:
    """{str(otro_id): doc_solicitud} para todas las solicitudes donde participa `me`."""
    out = {}
    for d in db.friend_requests.find({"$or": [{"emisor": me}, {"receptor": me}]}):
        otro = d["receptor"] if d["emisor"] == me else d["emisor"]
        out[str(otro)] = d
    return out


def correo_ya_registrado(email: str) -> bool:
    """True si ya existe una cuenta con ese correo. Compara su forma canonica, asi que
    mayusculas, espacios o alias con '+' no sirven para crear una segunda cuenta.
    (El indice unico de MongoDB sigue siendo la ultima barrera si dos registros chocan a la vez.)"""
    canon = validacion.normalizar_correo(email)
    return db.users.count_documents({"email": {"$in": [canon, str(email).strip().lower()]}}, limit=1) > 0


def identidad_ya_registrada(huella, codigo=None, excepto=None) -> bool:
    """True si ya hay una cuenta con la misma huella de identidad (o el mismo codigo de estudiante).
    `excepto` = _id del propio usuario (para no chocar consigo mismo al editar el perfil)."""
    condiciones = [{"huella": huella}] + ([{"codigo": codigo}] if codigo else [])
    q = {"$or": condiciones}
    if excepto is not None:
        q["_id"] = {"$ne": excepto}
    return db.users.count_documents(q, limit=1) > 0