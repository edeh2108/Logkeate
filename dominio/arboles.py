"""Arboles: comentarios anidados y jerarquia academica.
Una lista plana (cada elemento con parent_id) se convierte en arbol en O(n)."""


def construir_arbol_comentarios(docs: list, likes=None, mios=None, fotos=None) -> list:
    likes, mios, fotos = likes or {}, mios or set(), fotos or {}
    nodos = {
        d["_id"]: {
            "id": str(d["_id"]), "autor": d.get("autor_nombre", ""),
            "texto": d["texto"], "fecha": d["creado"].isoformat(), "hijos": [],
            "likes": likes.get(d["_id"], 0), "yo_like": d["_id"] in mios,
            "autor_foto": fotos.get(d.get("autor")),
        }
        for d in docs
    }
    raices = []
    for d in sorted(docs, key=lambda x: x["creado"]):   # mantiene orden cronologico entre hermanos
        padre = d.get("parent_id")
        destino = nodos[padre]["hijos"] if padre in nodos else raices
        destino.append(nodos[d["_id"]])
    return raices


def construir_arbol_unidades(docs: list):
    nodos = {d["_id"]: {"id": d["_id"], "nombre": d["nombre"], "tipo": d["tipo"], "hijos": []} for d in docs}
    raiz = None
    for d in sorted(docs, key=lambda x: (x["nivel"], x["nombre"])):
        if d.get("parent_id") in nodos:
            nodos[d["parent_id"]]["hijos"].append(nodos[d["_id"]])
        else:
            raiz = nodos[d["_id"]]
    return raiz
def estadisticas_arbol(raiz) -> dict:
    """n nodos, hojas, altura y aristas = n-1 (teorema de caracterizacion de arboles)."""
    if raiz is None:
        return {"nodos": 0, "hojas": 0, "altura": 0, "aristas": 0}
    nodos = hojas = 0
    pila = [(raiz, 0)]
    altura = 0
    while pila:
        n, prof = pila.pop()
        nodos += 1
        altura = max(altura, prof)
        if n["hijos"]:
            pila.extend((h, prof + 1) for h in n["hijos"])
        else:
            hojas += 1
    return {"nodos": nodos, "hojas": hojas, "altura": altura, "aristas": nodos - 1}