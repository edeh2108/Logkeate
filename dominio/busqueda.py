"""Algebra de Boole: el filtro de busqueda es un arbol de expresion (AST)
con operadores AND, OR, NOT y predicados simples. Se compila a una consulta MongoDB.

Ejemplo AST:
{"op":"OR","args":[
   {"op":"AND","args":[{"campo":"facultad","cmp":"==","valor":"FISI"},
                       {"campo":"ciclo","cmp":">=","valor":5}]},
   {"campo":"intereses","cmp":"CONTAINS","valor":"deportes"}]}
"""

# campo -> (tipo, operadores permitidos). La lista blanca evita inyeccion NoSQL.
CAMPOS = {
    "facultad":  (str, {"==", "CONTAINS"}),
    "ciclo":     (int, {"==", ">=", "<=", ">", "<"}),
    "intereses": (str, {"==", "CONTAINS"}),
    "cursos":    (str, {"==", "CONTAINS"}),
}
OPS = {"==": "$eq", ">=": "$gte", "<=": "$lte", ">": "$gt", "<": "$lt", "CONTAINS": "$eq"}
NORMALIZAR = {"facultad": str.upper, "intereses": str.lower, "cursos": str.upper}
MAX_PROFUNDIDAD = 5
MAX_ARGS = 10


class FiltroInvalido(ValueError):
    pass


def compilar(nodo: dict, prof: int = 0) -> dict:
    if not isinstance(nodo, dict) or prof > MAX_PROFUNDIDAD:
        raise FiltroInvalido("Filtro mal formado o demasiado profundo")
    op = nodo.get("op")
    if op in ("AND", "OR"):
        args = nodo.get("args")
        if not isinstance(args, list) or not 1 <= len(args) <= MAX_ARGS:
            raise FiltroInvalido("Cantidad de argumentos invalida")
        return {"$and" if op == "AND" else "$or": [compilar(a, prof + 1) for a in args]}
    if op == "NOT":
        return {"$nor": [compilar(nodo.get("arg"), prof + 1)]}   # NOT p  ==  $nor [p]
    # Predicado atomico
    campo, cmp_, valor = nodo.get("campo"), nodo.get("cmp"), nodo.get("valor")
    if campo not in CAMPOS:
        raise FiltroInvalido(f"Campo no permitido: {campo}")
    tipo, permitidos = CAMPOS[campo]
    if cmp_ not in permitidos:
        raise FiltroInvalido(f"Operador {cmp_} no permitido para {campo}")
    try:
        valor = tipo(valor)
    except (TypeError, ValueError):
        raise FiltroInvalido(f"Valor invalido para {campo}")
    if campo in NORMALIZAR:
        valor = NORMALIZAR[campo](valor.strip())
    # $eq sobre un campo-arreglo (intereses, cursos) equivale a "el conjunto contiene el elemento"
    return {campo: {OPS[cmp_]: valor}}
