"""Automata finito determinista M = (Q, Sigma, delta, q0, F) para la solicitud de amistad."""
from enum import Enum
from datetime import datetime, timezone


class E(str, Enum):  # Q: estados
    INEXISTENTE = "INEXISTENTE"
    PENDIENTE = "PENDIENTE"
    ACEPTADA = "ACEPTADA"
    RECHAZADA = "RECHAZADA"
    BLOQUEADA = "BLOQUEADA"


class Ev(str, Enum):  # Sigma: eventos
    ENVIAR = "enviar"
    ACEPTAR = "aceptar"
    RECHAZAR = "rechazar"
    CANCELAR = "cancelar"
    ELIMINAR = "eliminar_amigo"
    BLOQUEAR = "bloquear"
    DESBLOQUEAR = "desbloquear"


Q0 = E.INEXISTENTE          # estado inicial
F = {E.ACEPTADA}            # estados de aceptacion

DELTA = {                   # delta: Q x Sigma -> Q (funcion parcial)
    (E.INEXISTENTE, Ev.ENVIAR): E.PENDIENTE,
    (E.INEXISTENTE, Ev.BLOQUEAR): E.BLOQUEADA,
    (E.PENDIENTE, Ev.ACEPTAR): E.ACEPTADA,
    (E.PENDIENTE, Ev.RECHAZAR): E.RECHAZADA,
    (E.PENDIENTE, Ev.CANCELAR): E.INEXISTENTE,
    (E.PENDIENTE, Ev.BLOQUEAR): E.BLOQUEADA,
    (E.RECHAZADA, Ev.ENVIAR): E.PENDIENTE,
    (E.RECHAZADA, Ev.BLOQUEAR): E.BLOQUEADA,
    (E.ACEPTADA, Ev.ELIMINAR): E.INEXISTENTE,
    (E.ACEPTADA, Ev.BLOQUEAR): E.BLOQUEADA,
    (E.BLOQUEADA, Ev.DESBLOQUEAR): E.INEXISTENTE,
}


class TransicionInvalida(Exception):
    pass


class Solicitud:
    def __init__(self, emisor=None, receptor=None, estado=Q0, bloqueado_por=None):
        self.emisor, self.receptor = emisor, receptor
        self.estado, self.bloqueado_por = estado, bloqueado_por
        self.historial = []

    def _guarda(self, ev, actor) -> bool:
        """Condiciones sobre el actor (guardas de las transiciones)."""
        if ev in (Ev.ACEPTAR, Ev.RECHAZAR):
            return actor == self.receptor
        if ev == Ev.CANCELAR:
            return actor == self.emisor
        if ev == Ev.DESBLOQUEAR:
            return actor == self.bloqueado_por
        return True

    def aplicar(self, ev: Ev, actor, otro=None) -> E:
        """Aplica un evento. `otro` = el otro usuario (necesario en 'enviar')."""
        destino = DELTA.get((self.estado, ev))
        if destino is None:
            raise TransicionInvalida(f"'{ev.value}' no es posible desde el estado {self.estado.value}")
        if not self._guarda(ev, actor):
            raise TransicionInvalida(f"El usuario no puede ejecutar '{ev.value}' en esta solicitud")
        if ev == Ev.ENVIAR:
            self.emisor, self.receptor = actor, otro
        if ev == Ev.BLOQUEAR:
            self.bloqueado_por = actor
        if destino == E.INEXISTENTE:
            self.bloqueado_por = None
        self.historial.append({
            "de": self.estado.value, "evento": ev.value, "a": destino.value,
            "ts": datetime.now(timezone.utc),
        })
        self.estado = destino
        return destino
