"""Conexion a MongoDB. La URI se lee de variables de entorno (.env)."""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "unmsm_social")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
db = client[DB_NAME]


def _indice_ttl(coleccion, campo="expira"):
    """Indice TTL: MongoDB borra solo los documentos cuando `campo` (una fecha) ya paso.
    Si existia un indice normal sobre ese campo (version anterior), se reemplaza."""
    try:
        coleccion.create_index(campo, expireAfterSeconds=0)
    except OperationFailure:
        coleccion.drop_index(f"{campo}_1")
        coleccion.create_index(campo, expireAfterSeconds=0)


def crear_indices():
    """Indices que materializan las restricciones matematicas del modelo."""
    db.users.create_index("email", unique=True)                       # un correo = un vertice
    # Una persona = una cuenta (clase de equivalencia). Parciales: las cuentas antiguas
    # que aun no tienen estos campos no chocan entre si.
    db.users.create_index("huella", unique=True, partialFilterExpression={"huella": {"$type": "string"}})
    db.users.create_index("codigo", unique=True, partialFilterExpression={"codigo": {"$type": "string"}})
    db.friendships.create_index([("u", 1), ("v", 1)], unique=True)    # sin aristas paralelas
    db.friendships.create_index("v")
    db.friend_requests.create_index("par", unique=True)               # una solicitud por pareja
    db.academic_units.create_index("path")
    db.comments.create_index([("post_id", 1), ("creado", 1)])
    db.posts.create_index([("creado", -1)])
    db.posts.create_index("grupo_id")
    db.posts.create_index("autor")
    db.likes.create_index([("tipo", 1), ("obj", 1), ("user", 1)], unique=True)   # un usuario, un "me gusta" por objeto
    db.groups.create_index("nombre_norm", unique=True)
    db.group_members.create_index([("grupo_id", 1), ("user", 1)], unique=True)   # pertenencia = par (grupo, usuario) sin repetir
    db.users.create_index("nombres")
    db.messages.create_index([("par", 1), ("_id", 1)])                 # historial de una conversacion
    db.messages.create_index([("receptor", 1), ("leido", 1)])          # contador de no leidos
    db.messages.create_index([("emisor", 1), ("creado", -1)])          # limite de mensajes por minuto
    db.stories.create_index([("autor", 1), ("creado", 1)])             # historias de un autor
    # Historias: duran 24 h y MongoDB las borra solas (con su imagen, comentarios y reacciones)
    _indice_ttl(db.stories)
    _indice_ttl(db.story_comments)
    _indice_ttl(db.story_reactions)
    _indice_ttl(db.images)                                             # solo las imagenes con campo `expira`
    db.story_comments.create_index([("historia_id", 1), ("creado", 1)])
    db.story_reactions.create_index([("historia_id", 1), ("user", 1)], unique=True)   # una reaccion por persona
    db.messages.create_index([("par", 1), ("modificado", 1)])          # cambios (editados/eliminados) del chat
    # Reportes: una cuenta solo puede reportar a otra UNA vez por ciclo (mientras el reporte siga activo)
    db.reports.create_index([("reportado", 1), ("reportante", 1)], unique=True,
                            partialFilterExpression={"activo": True})
    db.reports.create_index("reportado")
    db.reports.create_index("reportante")
    db.friend_requests.create_index("receptor")                        # contador de solicitudes recibidas
    db.friend_requests.create_index("emisor")
    # Archivos adjuntos: los que se suben y nunca se usan caducan solos (campo `expira`)
    _indice_ttl(db.files)
    db.files.create_index("owner")
    db.posts.create_index("archivo_id", sparse=True)
    db.messages.create_index("archivo_id", sparse=True)