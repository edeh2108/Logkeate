"""Conexion a MongoDB. La URI se lee de variables de entorno (.env)."""
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "unmsm_social")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
db = client[DB_NAME]


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
    db.friend_requests.create_index("emisor")                         # relaciones_con(): buscar por emisor
    db.friend_requests.create_index("receptor")                       # ... o por receptor
    db.academic_units.create_index("path")
    db.comments.create_index([("post_id", 1), ("creado", 1)])
    db.posts.create_index([("creado", -1)])
    db.posts.create_index("grupo_id")
    db.posts.create_index("autor")
    db.likes.create_index([("tipo", 1), ("obj", 1), ("user", 1)], unique=True)   # un usuario, un "me gusta" por objeto
    db.groups.create_index("nombre_norm", unique=True)
    db.group_members.create_index([("grupo_id", 1), ("user", 1)], unique=True)   # pertenencia = par (grupo, usuario) sin repetir
    db.group_members.create_index("user")
    db.users.create_index("nombres")
    db.messages.create_index([("par", 1), ("_id", 1)])                 # historial de una conversacion
    db.messages.create_index([("receptor", 1), ("leido", 1)])          # contador de no leidos
    db.messages.create_index([("emisor", 1), ("creado", -1)])          # limite de mensajes por minuto