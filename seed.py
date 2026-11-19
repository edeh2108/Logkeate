"""Carga inicial: arbol academico UNMSM (todas las escuelas de pregrado) e indices.
Ejecutar UNA vez:  python seed.py   (es idempotente: se puede repetir)."""
import re
import unicodedata

from db import db, crear_indices


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


# Escuelas profesionales segun la lista oficial de la Oficina Central de Admision (examen 2027-I).
# Cada escuela aparece UNA vez (las sedes S.J.L. y Huaral son la misma carrera).
# La agrupacion en facultades se dedujo de los codigos de la OCA: verificala con la web oficial.
ARBOL = {
    "salud": ("Ciencias de la Salud", [
        ("MED", "Medicina", ["Medicina Humana", "Obstetricia", "Enfermería", "Nutrición",
                             "Tecnología Médica en Laboratorio Clínico y Anatomía Patológica",
                             "Tecnología Médica en Radiología", "Tecnología Médica en Terapia Física y Rehabilitación",
                             "Tecnología Médica en Terapia Ocupacional"]),
        ("ODO", "Odontología", ["Odontología"]),
        ("FARM", "Farmacia y Bioquímica", ["Farmacia y Bioquímica", "Ciencias de los Alimentos", "Toxicología"]),
        ("VET", "Medicina Veterinaria", ["Medicina Veterinaria"]),
    ]),
    "basicas": ("Ciencias Básicas", [
        ("BIO", "Ciencias Biológicas", ["Ciencias Biológicas", "Genética y Biotecnología", "Microbiología y Parasitología"]),
        ("FIS", "Ciencias Físicas", ["Física", "Ingeniería Mecánica de Fluidos", "Geofísica", "Ciencia de Materiales y Nanotecnología"]),
        ("MAT", "Ciencias Matemáticas", ["Matemática", "Estadística", "Investigación Operativa", "Computación Científica"]),
        ("FQIQ", "Química e Ingeniería Química", ["Química", "Ingeniería Química", "Ingeniería Agroindustrial",
                                                   "Ingeniería del Agua y Tecnologías de Tratamiento"]),
    ]),
    "ing": ("Ingeniería", [
        ("FISI", "Ingeniería de Sistemas e Informática", ["Ingeniería de Sistemas", "Ingeniería de Software",
                                                          "Ciencia de la Computación", "Ingeniería de Inteligencia Artificial"]),
        ("FIEE", "Ingeniería Electrónica y Eléctrica", ["Ingeniería Electrónica", "Ingeniería Eléctrica", "Ingeniería de Telecomunicaciones",
                                                         "Ingeniería Biomédica", "Ingeniería Mecatrónica", "Ingeniería Nuclear"]),
        ("FIGMMG", "Ingeniería Geológica, Minera, Metalúrgica, Geográfica, Civil y Ambiental",
         ["Ingeniería Geológica", "Ingeniería de Minas", "Ingeniería Metalúrgica", "Ingeniería Geográfica",
          "Ingeniería Civil", "Ingeniería Ambiental", "Arquitectura y Urbanismo"]),
        ("FII", "Ingeniería Industrial", ["Ingeniería Industrial", "Ingeniería Textil y Confecciones", "Ingeniería de Seguridad y Salud en el Trabajo",
                                          "Ingeniería Logística y Cadena de Suministro Digital", "Ingeniería de Transporte y Sistemas Ferroviarios"]),
    ]),
    "econ": ("Ciencias Económicas y de la Gestión", [
        ("FCA", "Ciencias Administrativas", ["Administración", "Administración de Turismo", "Administración de Negocios Internacionales",
                                             "Administración de la Gastronomía", "Administración Marítima y Portuaria", "Marketing"]),
        ("FCC", "Ciencias Contables", ["Contabilidad", "Gestión Tributaria", "Auditoría Empresarial y del Sector Público",
                                       "Presupuesto y Finanzas Públicas", "Criminalística Financiera Forense"]),
        ("FCE", "Ciencias Económicas", ["Economía", "Economía Pública", "Economía Internacional"]),
    ]),
    "hum": ("Humanidades y Ciencias Jurídicas y Sociales", [
        ("DER", "Derecho y Ciencia Política", ["Derecho", "Ciencia Política"]),
        ("LET", "Letras y Ciencias Humanas", ["Literatura", "Filosofía", "Lingüística", "Comunicación Social", "Arte",
                                              "Bibliotecología y Ciencias de la Información", "Danza", "Conservación y Restauración",
                                              "Lenguas, Traducción e Interpretación"]),
        ("EDU", "Educación", ["Educación Inicial", "Educación Primaria", "Educación Secundaria", "Educación Física"]),
        ("SOC", "Ciencias Sociales", ["Historia", "Sociología", "Antropología", "Arqueología", "Trabajo Social", "Geografía"]),
        ("PSI", "Psicología", ["Psicología", "Psicología Organizacional y de la Gestión Humana"]),
    ]),
}


def put(_id, nombre, tipo, parent, path, nivel, **extra):
    db.academic_units.replace_one(
        {"_id": _id},
        {"_id": _id, "nombre": nombre, "tipo": tipo, "parent_id": parent, "path": path, "nivel": nivel, **extra},
        upsert=True)


def main():
    crear_indices()
    put("unmsm", "Universidad Nacional Mayor de San Marcos", "universidad", None, "/unmsm", 0)
    for area_id, (area_nombre, facultades) in ARBOL.items():
        a_id = f"area_{area_id}"
        put(a_id, area_nombre, "area", "unmsm", f"/unmsm/{a_id}", 1)
        for sigla, f_nombre, escuelas in facultades:
            f_id = sigla.lower()
            put(f_id, f_nombre, "facultad", a_id, f"/unmsm/{a_id}/{f_id}", 2, sigla=sigla)
            for e in escuelas:
                e_id = f"{f_id}_{slug(e)}"
                put(e_id, e, "escuela", f_id, f"/unmsm/{a_id}/{f_id}/{e_id}", 3)
    # Quita unidades que ya no existen en la lista oficial (p. ej. nombres antiguos)
    vigentes = {"unmsm"} | {f"area_{a}" for a in ARBOL}
    for a, (_, facs) in ARBOL.items():
        for sigla, _, escuelas in facs:
            vigentes.add(sigla.lower())
            vigentes |= {f"{sigla.lower()}_{slug(e)}" for e in escuelas}
    db.academic_units.delete_many({"_id": {"$nin": list(vigentes)}})
    # Los cursos ya no forman parte del perfil: se eliminan de las cuentas que los tenian guardados
    r = db.users.update_many({"cursos": {"$exists": True}}, {"$unset": {"cursos": ""}})
    print("Listo:", db.academic_units.count_documents({}), "unidades;", "cursos borrados de", r.modified_count, "cuentas")


if __name__ == "__main__":
    main()