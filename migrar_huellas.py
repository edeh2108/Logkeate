"""Migracion de UNA sola vez: calcula la huella de identidad de las cuentas antiguas.
Ejecutar:  python migrar_huellas.py   (es idempotente: se puede repetir)
Si dos cuentas antiguas son la misma persona, la segunda queda marcada como DUPLICADO
y NO se modifica: revisala a mano (borrala o cambia su nombre/escuela)."""
from db import db, crear_indices
from dominio import validacion


def main():
    ok = dup = 0
    for u in db.users.find({"huella": {"$exists": False}}):
        h = validacion.huella_identidad(u["nombres"], u.get("escuela_id"))
        if db.users.count_documents({"huella": h}, limit=1):
            print("DUPLICADO, revisar:", u["email"])
            dup += 1
            continue
        db.users.update_one({"_id": u["_id"]}, {"$set": {"huella": h}})
        ok += 1
    crear_indices()
    print(f"Listo: {ok} cuentas actualizadas, {dup} duplicadas para revisar.")


if __name__ == "__main__":
    main()
