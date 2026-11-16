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
    db.friendships.create_index([("u", 1), ("v", 1)], unique=True)    # sin aristas paralelas
    db.friendships.create_index("v")
    db.friend_requests.create_index("par", unique=True)               # una solicitud por pareja
    db.forum_follows.create_index([("seguidor", 1), ("foro_id", 1)], unique=True)
    db.academic_units.create_index("path")
    db.comments.create_index([("post_id", 1), ("creado", 1)])
    db.posts.create_index([("creado", -1)])
    db.posts.create_index("grupo_id")
    db.likes.create_index([("tipo", 1), ("obj", 1), ("user", 1)], unique=True)   # un usuario, un "me gusta" por objeto
    db.groups.create_index("nombre_norm", unique=True)
    db.group_members.create_index([("grupo_id", 1), ("user", 1)], unique=True)   # pertenencia = par (grupo, usuario) sin repetir
    db.users.create_index("nombres")