"""Capa de acceso a datos (PostgreSQL) para el E-commerce Universitario."""
import hashlib
import hmac
import os
import re
import secrets
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

import psycopg2
import psycopg2.extras
from psycopg2 import errors

# Carga opcional de un archivo .env (pip install python-dotenv)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "ecommerce"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

# Administrador inicial del sitio (se crea solo si no existe ningún admin)
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@ecommerce.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


class ErrorValidacion(Exception):
    """Error con un mensaje apto para mostrar al usuario."""


class ErrorPermiso(Exception):
    """El usuario no tiene permiso para realizar la acción."""


# --------------------------------------------------------------------------
# Conexión
# --------------------------------------------------------------------------
@contextmanager
def conexion():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# --------------------------------------------------------------------------
# Contraseñas (PBKDF2-SHA256, solo librería estándar)
# --------------------------------------------------------------------------
_ITERACIONES = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERACIONES)
    return f"pbkdf2_sha256${_ITERACIONES}${salt.hex()}${h.hex()}"


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        _, iteraciones, salt_hex, hash_hex = almacenado.split("$")
        calc = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iteraciones)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calc.hex(), hash_hex)


# --------------------------------------------------------------------------
# Esquema
# --------------------------------------------------------------------------
_ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id              SERIAL PRIMARY KEY,
    usuario         VARCHAR(50)  NOT NULL,
    correo          VARCHAR(120) NOT NULL,
    password_hash   TEXT         NOT NULL,
    es_admin        BOOLEAN      NOT NULL DEFAULT FALSE,
    puede_gestionar BOOLEAN      NOT NULL DEFAULT FALSE,
    creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_usuario ON usuarios (LOWER(usuario));
CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_correo  ON usuarios (LOWER(correo));

CREATE TABLE IF NOT EXISTS productos (
    id         SERIAL PRIMARY KEY,
    nombre     VARCHAR(100)  NOT NULL,
    precio     NUMERIC(10,2) NOT NULL CHECK (precio >= 0),
    imagen_url TEXT          NOT NULL DEFAULT '',
    creado_por INTEGER       REFERENCES usuarios(id) ON DELETE SET NULL,
    creado_en  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
"""

_PRODUCTOS_INICIALES = [
    ("Mochila", "45.00", "https://picsum.photos/200/200?1"),
    ("Cuaderno", "12.50", "https://picsum.photos/200/200?2"),
    ("Bolígrafo", "3.00", "https://picsum.photos/200/200?3"),
    ("Calculadora", "25.00", "https://picsum.photos/200/200?4"),
]


def inicializar_bd():
    """Crea las tablas, el administrador inicial y productos de ejemplo."""
    with conexion() as conn, _cursor(conn) as cur:
        cur.execute(_ESQUEMA)

        cur.execute("SELECT 1 FROM usuarios WHERE es_admin LIMIT 1")
        if cur.fetchone() is None:
            cur.execute(
                """INSERT INTO usuarios (usuario, correo, password_hash, es_admin, puede_gestionar)
                   VALUES (%s, %s, %s, TRUE, TRUE) ON CONFLICT DO NOTHING""",
                (ADMIN_USER, ADMIN_EMAIL, hash_password(ADMIN_PASSWORD)),
            )
            print(f"[BD] Administrador inicial creado: usuario='{ADMIN_USER}'")

        cur.execute("SELECT 1 FROM productos LIMIT 1")
        if cur.fetchone() is None:
            cur.executemany(
                "INSERT INTO productos (nombre, precio, imagen_url) VALUES (%s, %s, %s)",
                _PRODUCTOS_INICIALES,
            )


# --------------------------------------------------------------------------
# Usuarios
# --------------------------------------------------------------------------
_CAMPOS_USUARIO = "id, usuario, correo, es_admin, puede_gestionar"
_RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _es_admin(cur, usuario_id) -> bool:
    if usuario_id is None:
        return False
    cur.execute("SELECT es_admin FROM usuarios WHERE id = %s", (usuario_id,))
    fila = cur.fetchone()
    return bool(fila and fila["es_admin"])


def _puede_gestionar(cur, usuario_id) -> bool:
    if usuario_id is None:
        return False
    cur.execute(
        "SELECT es_admin OR puede_gestionar AS ok FROM usuarios WHERE id = %s",
        (usuario_id,),
    )
    fila = cur.fetchone()
    return bool(fila and fila["ok"])


def registrar_usuario(usuario, correo, password, puede_gestionar=False, admin_id=None):
    """Crea un usuario. Solo un admin (admin_id) puede otorgar 'puede_gestionar'."""
    usuario = (usuario or "").strip()
    correo = (correo or "").strip()
    password = password or ""

    if len(usuario) < 3:
        raise ErrorValidacion("El usuario debe tener al menos 3 caracteres.")
    if not _RE_CORREO.match(correo):
        raise ErrorValidacion("El correo electrónico no es válido.")
    if len(password) < 6:
        raise ErrorValidacion("La contraseña debe tener al menos 6 caracteres.")

    with conexion() as conn, _cursor(conn) as cur:
        if puede_gestionar and not _es_admin(cur, admin_id):
            raise ErrorPermiso("Solo el administrador puede otorgar ese permiso.")
        try:
            cur.execute(
                f"""INSERT INTO usuarios (usuario, correo, password_hash, puede_gestionar)
                    VALUES (%s, %s, %s, %s) RETURNING {_CAMPOS_USUARIO}""",
                (usuario, correo, hash_password(password), bool(puede_gestionar)),
            )
        except errors.UniqueViolation as e:
            if e.diag.constraint_name == "ux_usuarios_correo":
                raise ErrorValidacion("Ese correo ya está registrado.") from None
            raise ErrorValidacion("Ese nombre de usuario ya existe.") from None
        return dict(cur.fetchone())


def iniciar_sesion(identificador, password):
    """Devuelve el usuario (dict) si las credenciales son correctas, o None."""
    identificador = (identificador or "").strip()
    if not identificador or not password:
        return None
    with conexion() as conn, _cursor(conn) as cur:
        cur.execute(
            f"""SELECT {_CAMPOS_USUARIO}, password_hash FROM usuarios
                WHERE LOWER(usuario) = LOWER(%s) OR LOWER(correo) = LOWER(%s)""",
            (identificador, identificador),
        )
        fila = cur.fetchone()
    if fila and verificar_password(password, fila["password_hash"]):
        fila = dict(fila)
        fila.pop("password_hash")
        return fila
    return None


def obtener_usuario(usuario_id):
    with conexion() as conn, _cursor(conn) as cur:
        cur.execute(f"SELECT {_CAMPOS_USUARIO} FROM usuarios WHERE id = %s", (usuario_id,))
        fila = cur.fetchone()
    return dict(fila) if fila else None


def listar_usuarios(admin_id):
    with conexion() as conn, _cursor(conn) as cur:
        if not _es_admin(cur, admin_id):
            raise ErrorPermiso("Solo el administrador puede ver los usuarios.")
        cur.execute(f"SELECT {_CAMPOS_USUARIO} FROM usuarios ORDER BY id")
        return [dict(f) for f in cur.fetchall()]


def cambiar_permiso_gestion(admin_id, usuario_id, valor: bool):
    with conexion() as conn, _cursor(conn) as cur:
        if not _es_admin(cur, admin_id):
            raise ErrorPermiso("Solo el administrador puede cambiar permisos.")
        cur.execute(
            "UPDATE usuarios SET puede_gestionar = %s WHERE id = %s AND NOT es_admin",
            (bool(valor), usuario_id),
        )


# --------------------------------------------------------------------------
# Productos
# --------------------------------------------------------------------------
def listar_productos(filtro=""):
    with conexion() as conn, _cursor(conn) as cur:
        cur.execute(
            """SELECT id, nombre, precio, imagen_url FROM productos
               WHERE nombre ILIKE %s ORDER BY id""",
            (f"%{filtro.strip()}%",),
        )
        return [dict(f) for f in cur.fetchall()]


def agregar_producto(usuario_id, nombre, precio, imagen_url=""):
    nombre = (nombre or "").strip()
    if not nombre:
        raise ErrorValidacion("El nombre es obligatorio.")
    try:
        precio = Decimal(str(precio).replace(",", ".").strip())
    except InvalidOperation:
        raise ErrorValidacion("El precio no es válido.") from None
    if precio < 0:
        raise ErrorValidacion("El precio no puede ser negativo.")
    imagen_url = (imagen_url or "").strip() or f"https://picsum.photos/seed/{secrets.token_hex(4)}/200/200"

    with conexion() as conn, _cursor(conn) as cur:
        if not _puede_gestionar(cur, usuario_id):
            raise ErrorPermiso("No tienes permiso para agregar productos.")
        cur.execute(
            """INSERT INTO productos (nombre, precio, imagen_url, creado_por)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (nombre, precio, imagen_url, usuario_id),
        )
        return cur.fetchone()["id"]


def eliminar_producto(usuario_id, producto_id):
    with conexion() as conn, _cursor(conn) as cur:
        if not _puede_gestionar(cur, usuario_id):
            raise ErrorPermiso("No tienes permiso para eliminar productos.")
        cur.execute("DELETE FROM productos WHERE id = %s", (producto_id,))
