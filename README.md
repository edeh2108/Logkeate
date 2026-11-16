# Red Social UNMSM (Matemáticas Discretas)

Flask + MongoDB + HTML/CSS/JS puro. Solo correos `@unmsm.edu.pe`.

## Estructura
```
app.py            rutas Flask (API + sirve el frontend)
db.py             conexión MongoDB e índices
servicios.py      persistencia: autómata + grafo en MongoDB
seed.py           carga árbol académico y foros (ejecutar 1 vez)
dominio/          matemática discreta pura (sin BD, probada con tests)
  validacion.py   lógica proposicional
  busqueda.py     álgebra de Boole (AST -> consulta Mongo)
  conjuntos.py    ∩, ∪, \, Jaccard
  grafo.py        BFS / grados de separación
  solicitud_fsm.py  autómata finito de la solicitud
  arboles.py      comentarios anidados y jerarquía UNMSM
static/           index.html, style.css, app.js
tests/            python -m unittest discover -s tests -t .
```

## 1. Ejecutar en local (Windows, CMD)
```
cd unmsm-social
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
Edita `.env` (ver sección 2), luego:
```
python seed.py
python app.py
```
Abre http://127.0.0.1:5000. Pruebas: `python -m unittest discover -s tests -t .`

## 2. Conectar MongoDB (elige UNA opción)
**A) MongoDB Atlas (nube, nivel gratuito M0, sin tarjeta)**
1. Crea cuenta en https://www.mongodb.com/atlas y un cluster gratuito (M0).
2. *Database Access* → crea un usuario con contraseña (sin caracteres raros; si los tiene, codifícalos en la URL).
3. *Network Access* → *Add IP Address*. Para probar en local: "Add current IP". Para desplegar en Render: `0.0.0.0/0` (Render gratis no tiene IP fija; la protección es la contraseña del usuario).
4. *Connect* → *Drivers* → copia la cadena `mongodb+srv://...` y ponla en `.env`:
   `MONGO_URI=mongodb+srv://USUARIO:CLAVE@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
5. `DB_NAME=unmsm_social`

**B) MongoDB local**: instala MongoDB Community Server (con Compass). Con el servicio iniciado, el `.env.example` ya apunta a `mongodb://localhost:27017`.

`python seed.py` crea los índices, el árbol académico y los foros. Es idempotente.

## 3. Desplegar (Render, ejemplo)
1. Sube el proyecto a GitHub (`.env` está en `.gitignore`; nunca lo subas).
2. Ejecuta `python seed.py` una vez apuntando a Atlas (tu `.env` local con la URI de Atlas).
3. En https://render.com: *New → Web Service* → conecta el repositorio.
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. *Environment*: `MONGO_URI`, `DB_NAME`, `SECRET_KEY` (cadena larga aleatoria), `APP_ENV=production`.
5. Despliega y abre la URL `https://....onrender.com`.

Verifica los límites vigentes del plan gratuito de Render y Atlas antes de depender de ellos (por ejemplo, el servicio gratuito puede "dormirse" tras inactividad).
`gunicorn` no corre en Windows: solo se usa en el servidor; en local usa `python app.py`.

## Seguridad incluida
Contraseñas con hash, sesión en cookie HttpOnly/SameSite, lista blanca de campos en el buscador (anti-inyección NoSQL), `textContent` en el frontend (anti-XSS), validación de ObjectId, control optimista en el autómata.

## Limitaciones (menciónalas en el informe)
- La regex valida el *formato* del correo, no que sea tuyo. Para cerrar el sistema de verdad hace falta un token de verificación enviado por correo.
- Datos de `seed.py` son una muestra de facultades/escuelas: complétalos con la web oficial.
- Sin protección CSRF con token ni límite de intentos de login (mejoras posibles).
