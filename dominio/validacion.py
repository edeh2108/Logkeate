"""LOGICA PROPOSICIONAL aplicada al registro de usuarios.

Proposiciones atomicas:
    p : "el correo termina exactamente en @unmsm.edu.pe"
    q : "la contrasena tiene >= 8 caracteres, una letra y un digito"
    r : "el correo ya esta registrado"

Formula del registro:      V  =  p  ∧  q  ∧  ¬r
Solo hay 1 fila de 8 en la tabla de verdad donde V = verdadero (p=V, q=V, r=F).
Por De Morgan, el registro se RECHAZA cuando   ¬V  ≡  ¬p ∨ ¬q ∨ r.
Los `and` de Python usan evaluacion en cortocircuito: si p es falso, q ni se evalua.

RELACION DE EQUIVALENCIA aplicada a la identidad (una persona = una cuenta):
    a ~ b  <=>  huella(a) = huella(b)
Es reflexiva, simetrica y transitiva (la igualdad de huellas lo hereda de la igualdad).
Cada clase de equivalencia admite UNA sola cuenta (indice unico en MongoDB).
"""
import hashlib
import re
import unicodedata

# ^ y $ garantizan que el correo TERMINA exactamente en @unmsm.edu.pe
# (rechaza subdominios como a@x.unmsm.edu.pe y a@unmsm.edu.pe.evil.com)
_RE_CORREO = re.compile(r"^[a-z0-9._%+-]+@unmsm\.edu\.pe$")
_RE_CODIGO = re.compile(r"^\d{8}$")


def correo_institucional(email: str) -> bool:
    return bool(_RE_CORREO.fullmatch(email.strip().lower()))


def normalizar_correo(email) -> str:
    """Forma canonica del correo: minusculas, sin espacios y sin la etiqueta '+algo'.
    ana+2@unmsm.edu.pe y ANA@unmsm.edu.pe llegan al MISMO buzon que ana@unmsm.edu.pe,
    asi que deben contar como el mismo correo (misma clase de equivalencia)."""
    e = str(email).strip().lower()
    local, arroba, dominio = e.partition("@")
    return f"{local.split('+', 1)[0]}{arroba}{dominio}"


def normalizar_nombre(nombre) -> str:
    """Forma canonica del nombre: sin tildes, minusculas y palabras ordenadas.
    'Pérez  Ana' y 'ana perez' caen en la misma clase de equivalencia."""
    t = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode().lower()
    return " ".join(sorted(re.findall(r"[a-z]+", t)))


def codigo_valido(codigo) -> bool:
    """Codigo de estudiante: exactamente 8 digitos."""
    return bool(_RE_CODIGO.fullmatch(str(codigo).strip()))


def huella_identidad(nombres, escuela_id) -> str:
    """Representante de la clase de equivalencia: a ~ b  <=>  huella(a) == huella(b).
    El ciclo NO entra: cambia cada semestre y permitiria duplicarse con solo cambiarlo."""
    base = f"{normalizar_nombre(nombres)}|{escuela_id}"
    return hashlib.sha256(base.encode()).hexdigest()


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