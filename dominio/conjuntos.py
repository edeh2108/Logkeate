"""TEORIA DE CONJUNTOS aplicada a cursos, intereses y seguidores de foros.

Cada estudiante tiene un conjunto de cursos A (ej. {INF101, MAT201}).
  A ∩ B  : cursos en comun            A ∪ B : cursos de cualquiera de los dos
  A \\ B  : cursos solo de A           |A ∪ B| = |A| + |B| - |A ∩ B|  (inclusion-exclusion)
Python implementa `set` con tablas hash: pertenencia O(1), interseccion O(min(|A|,|B|)).
Convertir listas a set elimina duplicados (en un conjunto no importa orden ni repeticion).
"""


def interseccion(a, b) -> set:
    return set(a) & set(b)


def union(*conjuntos) -> set:
    return set().union(*map(set, conjuntos))


def diferencia(a, b) -> set:
    return set(a) - set(b)


def jaccard(a, b) -> float:
    """|A ∩ B| / |A ∪ B|  (0.0 si ambos vacios)."""
    a, b = set(a), set(b)
    u = a | b
    return len(a & b) / len(u) if u else 0.0
