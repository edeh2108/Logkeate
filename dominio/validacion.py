"""LOGICA PROPOSICIONAL aplicada al registro de usuarios.

Proposiciones atomicas:
    p : "el correo termina exactamente en @unmsm.edu.pe"
    q : "la contrasena tiene >= 8 caracteres, una letra y un digito"
    r : "el correo ya esta registrado"

Formula del registro:      V  =  p  ∧  q  ∧  ¬r
Solo hay 1 fila de 8 en la tabla de verdad donde V = verdadero (p=V, q=V, r=F).
Por De Morgan, el registro se RECHAZA cuando   ¬V  ≡  ¬p ∨ ¬q ∨ r.
Los `and` de Python usan evaluacion en cortocircuito: si p es falso, q ni se evalua.
"""
import re

# ^ y $ garantizan que el correo TERMINA exactamente en @unmsm.edu.pe
# (rechaza subdominios como a@x.unmsm.edu.pe y a@unmsm.edu.pe.evil.com)
_RE_CORREO = re.compile(r"^[a-z0-9._%+-]+@unmsm\.edu\.pe$")


def correo_institucional(email: str) -> bool:
    return bool(_RE_CORREO.fullmatch(email.strip().lower()))


def normalizar_correo(email) -> str:
    """Forma canonica del correo: minusculas, sin espacios y sin la etiqueta '+algo'.
    ana+2@unmsm.edu.pe y ANA@unmsm.edu.pe llegan al MISMO buzon que ana@unmsm.edu.pe,
    asi que deben contar como el mismo correo (misma clase de equivalencia)."""
    e = str(email).strip().lower()
    local, arroba, dominio = e.partition("@")
    return f"{local.split('+', 1)[0]}{arroba}{dominio}"


def password_valida(password: str) -> bool:
    return (
        len(password) >= 8
        and any(c.isdigit() for c in password)
        and any(c.isalpha() for c in password)
    )


def registro_valido(email: str, password: str, existe_email: bool) -> bool:
    """V = p ∧ q ∧ ¬r  (conjuncion de tres literales)."""
    return correo_institucional(email) and password_valida(password) and not existe_email


def tabla_verdad() -> list:
    """Las 2^3 = 8 filas de (p, q, r) con el valor de V = p ∧ q ∧ ¬r."""
    return [{"p": p, "q": q, "r": r, "V": p and q and not r}
            for p in (True, False) for q in (True, False) for r in (True, False)]