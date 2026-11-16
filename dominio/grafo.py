"""TEORIA DE GRAFOS: G = (V, E) no dirigido y simple.
    V = estudiantes (vertices)        E = amistades aceptadas (aristas {u, v})
La amistad como RELACION es: simetrica (u~v => v~u), irreflexiva (nadie es amigo de si mismo)
y NO transitiva (amigo de mi amigo no es necesariamente mi amigo).
Grados de separacion = distancia minima d(u,v) = longitud del camino mas corto.
BFS la calcula en O(V+E) porque explora por niveles (todos los de distancia k antes que k+1).
"""
from collections import deque


def grados_de_separacion(origen, destino, vecinos, max_prof=None):
    """Devuelve (distancia, camino). distancia=None si no hay camino.
    `vecinos(v)` -> iterable de adyacentes (inyectada para poder probar sin BD)."""
    if origen == destino:
        return 0, [origen]
    visitado = {origen}
    padre = {origen: None}
    cola = deque([(origen, 0)])
    while cola:
        actual, d = cola.popleft()
        if max_prof is not None and d >= max_prof:
            continue
        for v in vecinos(actual):
            if v in visitado:
                continue
            visitado.add(v)
            padre[v] = actual
            if v == destino:
                camino, n = [], v
                while n is not None:
                    camino.append(n)
                    n = padre[n]
                camino.reverse()
                return len(camino) - 1, camino
            cola.append((v, d + 1))
    return None, []


def verificar_apreton_de_manos(grados: list, n_aristas: int) -> bool:
    """Lema del apreton de manos: suma de grados = 2|E|."""
    return sum(grados) == 2 * n_aristas
