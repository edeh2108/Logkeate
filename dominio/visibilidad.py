"""Reglas de visibilidad como PROPOSICIONES y operaciones de CONJUNTOS.

Muro:  ver(v, d)  =  (v = d)  ∨  (v ∈ Amigos(d))
Chat:  cada mensaje m tiene un conjunto B(m) de usuarios que lo ocultaron.
       visible(m, u)  <=>  u ∉ B(m)
       se purga       <=>  {a, b} ⊆ B(m)   (los dos participantes lo ocultaron)
"""


def puede_ver_muro(visitante, dueno, amigos_del_dueno) -> bool:
    return visitante == dueno or visitante in set(amigos_del_dueno)


def mensaje_visible(borrado_para, usuario) -> bool:
    return usuario not in set(borrado_para)


def debe_purgarse(borrado_para, a, b) -> bool:
    return {a, b} <= set(borrado_para)