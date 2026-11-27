import unittest
from datetime import datetime, timedelta, timezone

from dominio import validacion, busqueda, conjuntos, grafo, arboles, visibilidad
from dominio.solicitud_fsm import Solicitud, Ev, E, TransicionInvalida


class TestLogica(unittest.TestCase):
    def test_correos(self):
        ok = ["ana.perez@unmsm.edu.pe", "A@UNMSM.EDU.PE", "juan_1@unmsm.edu.pe"]
        mal = ["a@gmail.com", "a@unmsm.edu.pe.evil.com", "a@x.unmsm.edu.pe", "a@unmsm.edu", "@unmsm.edu.pe", "a@unmsm.edu.pex"]
        for c in ok:
            self.assertTrue(validacion.correo_institucional(c), c)
        for c in mal:
            self.assertFalse(validacion.correo_institucional(c), c)

    def test_registro_tabla_de_verdad(self):
        self.assertTrue(validacion.registro_valido("a@unmsm.edu.pe", "clave1234", False))
        self.assertFalse(validacion.registro_valido("a@unmsm.edu.pe", "clave1234", True))
        self.assertFalse(validacion.registro_valido("a@gmail.com", "clave1234", False))
        self.assertFalse(validacion.registro_valido("a@unmsm.edu.pe", "corta", False))


class TestBusqueda(unittest.TestCase):
    def test_or_and(self):
        q = busqueda.compilar({"op": "OR", "args": [
            {"op": "AND", "args": [{"campo": "facultad", "cmp": "==", "valor": "fisi"},
                                   {"campo": "ciclo", "cmp": ">=", "valor": "5"}]},
            {"campo": "intereses", "cmp": "CONTAINS", "valor": "Deportes"}]})
        self.assertEqual(q, {"$or": [{"$and": [{"facultad": {"$eq": "FISI"}}, {"ciclo": {"$gte": 5}}]},
                                     {"intereses": {"$eq": "deportes"}}]})

    def test_rechaza_campos_y_operadores(self):
        for malo in [{"campo": "pass_hash", "cmp": "==", "valor": "x"},
                     {"campo": "ciclo", "cmp": "CONTAINS", "valor": 3},
                     {"campo": "ciclo", "cmp": ">=", "valor": "abc"},
                     {"op": "XOR"}]:
            with self.assertRaises(busqueda.FiltroInvalido):
                busqueda.compilar(malo)


class TestConjuntos(unittest.TestCase):
    def test_ops(self):
        a, b = {"INF1", "MAT1", "FIS1"}, {"MAT1", "FIS1", "QUI1"}
        self.assertEqual(conjuntos.interseccion(a, b), {"MAT1", "FIS1"})
        self.assertEqual(len(conjuntos.union(a, b)), 4)
        self.assertEqual(conjuntos.diferencia(a, b), {"INF1"})
        self.assertAlmostEqual(conjuntos.jaccard(a, b), 0.5)
        self.assertEqual(conjuntos.jaccard([], []), 0.0)


class TestGrafo(unittest.TestCase):
    G = {"A": ["B"], "B": ["A", "C"], "C": ["B", "D"], "D": ["C"], "E": []}

    def test_bfs(self):
        v = lambda x: self.G[x]
        self.assertEqual(grafo.grados_de_separacion("A", "D", v), (3, ["A", "B", "C", "D"]))
        self.assertEqual(grafo.grados_de_separacion("A", "A", v), (0, ["A"]))
        self.assertEqual(grafo.grados_de_separacion("A", "E", v)[0], None)
        self.assertEqual(grafo.grados_de_separacion("A", "D", v, max_prof=2)[0], None)

    def test_camino_minimo_con_ciclo(self):
        G = {1: [2, 3], 2: [1, 4], 3: [1, 4], 4: [2, 3, 5], 5: [4]}
        self.assertEqual(grafo.grados_de_separacion(1, 5, lambda x: G[x])[0], 3)

    def test_apreton_de_manos(self):
        grados = [len(v) for v in self.G.values()]
        self.assertTrue(grafo.verificar_apreton_de_manos(grados, 3))


class TestFSM(unittest.TestCase):
    def test_flujo_feliz(self):
        s = Solicitud()
        self.assertEqual(s.aplicar(Ev.ENVIAR, "A", "B"), E.PENDIENTE)
        self.assertEqual(s.aplicar(Ev.ACEPTAR, "B"), E.ACEPTADA)
        self.assertEqual(s.aplicar(Ev.ELIMINAR, "A"), E.INEXISTENTE)
        self.assertEqual(len(s.historial), 3)

    def test_rechazo_y_reenvio(self):
        s = Solicitud()
        s.aplicar(Ev.ENVIAR, "A", "B")
        s.aplicar(Ev.RECHAZAR, "B")
        self.assertEqual(s.estado, E.RECHAZADA)
        self.assertEqual(s.aplicar(Ev.ENVIAR, "A", "B"), E.PENDIENTE)

    def test_guardas(self):
        s = Solicitud()
        s.aplicar(Ev.ENVIAR, "A", "B")
        with self.assertRaises(TransicionInvalida):
            s.aplicar(Ev.ACEPTAR, "A")        # el emisor no puede aceptar
        with self.assertRaises(TransicionInvalida):
            s.aplicar(Ev.CANCELAR, "B")       # el receptor no puede cancelar
        with self.assertRaises(TransicionInvalida):
            s.aplicar(Ev.ENVIAR, "B", "A")    # ya hay una pendiente

    def test_bloqueo(self):
        s = Solicitud()
        s.aplicar(Ev.ENVIAR, "A", "B")
        s.aplicar(Ev.BLOQUEAR, "B")
        self.assertEqual(s.estado, E.BLOQUEADA)
        with self.assertRaises(TransicionInvalida):
            s.aplicar(Ev.ENVIAR, "A", "B")
        with self.assertRaises(TransicionInvalida):
            s.aplicar(Ev.DESBLOQUEAR, "A")    # solo quien bloqueo
        self.assertEqual(s.aplicar(Ev.DESBLOQUEAR, "B"), E.INEXISTENTE)


class TestArboles(unittest.TestCase):
    def test_comentarios(self):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mk = lambda i, p, m: {"_id": i, "parent_id": p, "autor_nombre": "x", "texto": str(i),
                              "creado": t0 + timedelta(minutes=m)}
        docs = [mk(3, 2, 3), mk(1, None, 1), mk(2, 1, 2), mk(4, None, 4)]
        arbol = arboles.construir_arbol_comentarios(docs)
        self.assertEqual([n["texto"] for n in arbol], ["1", "4"])
        self.assertEqual(arbol[0]["hijos"][0]["hijos"][0]["texto"], "3")

    def test_unidades(self):
        docs = [{"_id": "u", "nombre": "U", "tipo": "universidad", "parent_id": None, "nivel": 0},
                {"_id": "a", "nombre": "A", "tipo": "area", "parent_id": "u", "nivel": 1},
                {"_id": "f", "nombre": "F", "tipo": "facultad", "parent_id": "a", "nivel": 2}]
        raiz = arboles.construir_arbol_unidades(docs)
        self.assertEqual(raiz["hijos"][0]["hijos"][0]["id"], "f")

class TestExtrasMatematicos(unittest.TestCase):
    def test_tabla_verdad_una_sola_fila_verdadera(self):
        t = validacion.tabla_verdad()
        self.assertEqual(len(t), 8)
        self.assertEqual([f for f in t if f["V"]], [{"p": True, "q": True, "r": False, "V": True}])

    def test_estadisticas_arbol_n_menos_1_aristas(self):
        raiz = {"hijos": [{"hijos": [{"hijos": []}, {"hijos": []}]}, {"hijos": []}]}
        st = arboles.estadisticas_arbol(raiz)
        self.assertEqual(st, {"nodos": 5, "hojas": 3, "altura": 2, "aristas": 4})
        self.assertEqual(arboles.estadisticas_arbol(None)["nodos"], 0)

class TestLikesEnArbol(unittest.TestCase):
    def test_comentarios_con_likes(self):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        docs = [{"_id": 1, "texto": "a", "creado": t0, "parent_id": None},
                {"_id": 2, "texto": "b", "creado": t0 + timedelta(minutes=1), "parent_id": 1}]
        raiz = arboles.construir_arbol_comentarios(docs, {1: 3}, {2})
        self.assertEqual((raiz[0]["likes"], raiz[0]["yo_like"]), (3, False))
        self.assertEqual((raiz[0]["hijos"][0]["likes"], raiz[0]["hijos"][0]["yo_like"]), (0, True))

class TestCorreoCanonico(unittest.TestCase):
    def test_normalizar_correo(self):
        n = validacion.normalizar_correo
        self.assertEqual(n("  ANA@UNMSM.EDU.PE "), "ana@unmsm.edu.pe")
        self.assertEqual(n("ana+2@unmsm.edu.pe"), "ana@unmsm.edu.pe")
        self.assertEqual(n("ana+a+b@unmsm.edu.pe"), "ana@unmsm.edu.pe")
        self.assertEqual(n("sin-arroba"), "sin-arroba")


class TestIdentidad(unittest.TestCase):
    """Relacion de equivalencia: a ~ b  <=>  huella(a) = huella(b)."""

    def test_normalizar_nombre(self):
        n = validacion.normalizar_nombre
        self.assertEqual(n("Ana  Pérez"), n("PEREZ ana"))     # tildes, mayusculas, espacios y orden
        self.assertNotEqual(n("Ana Pérez"), n("Ana Pérez López"))

    def test_huella_es_relacion_de_equivalencia(self):
        h = validacion.huella_identidad
        a, b, c = h("Ana  Pérez", "fisi_x"), h("PEREZ ana", "fisi_x"), h("ana perez", "fisi_x")
        self.assertEqual(a, a)                                  # reflexiva
        self.assertEqual((a == b), (b == a))                    # simetrica
        self.assertTrue(a == b and b == c and a == c)           # transitiva
        self.assertNotEqual(a, h("Ana Pérez", "med_y"))         # otra escuela = otra clase

    def test_codigo_estudiante(self):
        self.assertTrue(validacion.codigo_valido("20200123"))
        self.assertTrue(validacion.codigo_valido(" 20200123 "))
        for malo in ["2020012", "202001234", "2020012a", ""]:
            self.assertFalse(validacion.codigo_valido(malo), malo)


class TestVisibilidad(unittest.TestCase):
    def test_muro(self):
        self.assertTrue(visibilidad.puede_ver_muro("A", "A", []))          # v = d
        self.assertTrue(visibilidad.puede_ver_muro("A", "B", ["A", "C"]))  # v ∈ Amigos(d)
        self.assertFalse(visibilidad.puede_ver_muro("X", "B", ["A", "C"]))

    def test_mensajes_ocultos(self):
        self.assertTrue(visibilidad.mensaje_visible(["A"], "B"))
        self.assertFalse(visibilidad.mensaje_visible(["A"], "A"))
        self.assertFalse(visibilidad.debe_purgarse(["A"], "A", "B"))
        self.assertTrue(visibilidad.debe_purgarse(["B", "A", "A"], "A", "B"))


if __name__ == "__main__":
    unittest.main()