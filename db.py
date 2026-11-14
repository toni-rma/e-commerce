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

#carga .env
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

# Administrador inicial del sitio (se crea solo si no existe ningún admin).
# Las variables de entorno permiten configurar credenciales distintas.
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@ecommerce.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")


class ErrorValidacion(Exception):
    """Error con un mensaje apto para mostrar al usuario."""


class ErrorPermiso(Exception):
    """El usuario no tiene permiso para realizar la acción."""


#con
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


#pass
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



#datebase
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

CREATE TABLE IF NOT EXISTS categorias (
    id     SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_categorias_nombre
    ON categorias (LOWER(nombre));

CREATE TABLE IF NOT EXISTS productos (
    id         SERIAL PRIMARY KEY,
    nombre     VARCHAR(100)  NOT NULL,
    precio     NUMERIC(10,2) NOT NULL CHECK (precio >= 0),
    imagen_url TEXT          NOT NULL DEFAULT '',
    descripcion TEXT         NOT NULL DEFAULT '',
    categoria_id INTEGER     REFERENCES categorias(id) ON DELETE SET NULL,
    creado_por INTEGER       REFERENCES usuarios(id) ON DELETE SET NULL,
    creado_en  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sucursales (
    id     SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_sucursales_nombre
    ON sucursales (LOWER(nombre));

CREATE TABLE IF NOT EXISTS inventario_productos (
    producto_id  INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    sucursal_id  INTEGER NOT NULL REFERENCES sucursales(id) ON DELETE CASCADE,
    cantidad     INTEGER NOT NULL CHECK (cantidad >= 0),
    PRIMARY KEY (producto_id, sucursal_id)
);

CREATE TABLE IF NOT EXISTS paleta_pagina (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    fondo      VARCHAR(7) NOT NULL,
    superficie VARCHAR(7) NOT NULL,
    primario   VARCHAR(7) NOT NULL,
    acento     VARCHAR(7) NOT NULL
);
"""

PALETA_PREDETERMINADA = {
    "fondo": "#F5F7FB",
    "superficie": "#FFFFFF",
    "primario": "#1976D2",
    "acento": "#2E7D32",
}

_PRODUCTOS_INICIALES = [
    ("Mochila", "45.00", "https://picsum.photos/200/200?1", "Mochila para uso diario."),
    ("Cuaderno", "12.50", "https://picsum.photos/200/200?2", "Cuaderno para notas y apuntes."),
    ("Bolígrafo", "3.00", "https://picsum.photos/200/200?3", "Bolígrafo para escritura diaria."),
    ("Calculadora", "25.00", "https://picsum.photos/200/200?4", "Calculadora para operaciones y cálculos."),
]


def _obtener_categoria_id(cur, nombre):
    nombre = (nombre or "").strip()
    if not nombre:
        raise ErrorValidacion("La categoría es obligatoria.")
    if len(nombre) > 100:
        raise ErrorValidacion("La categoría no puede superar los 100 caracteres.")
    cur.execute(
        "INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING",
        (nombre,),
    )
    cur.execute(
        "SELECT id FROM categorias WHERE LOWER(nombre) = LOWER(%s)",
        (nombre,),
    )
    fila = cur.fetchone()
    if fila is None:
        raise ErrorValidacion("No se pudo guardar la categoría.")
    return fila["id"]


def inicializar_bd():
    """Crea las tablas, el admin inicial y productos de ej."""
    with conexion() as conn, _cursor(conn) as cur:
        cur.execute(_ESQUEMA)
        cur.execute(
            "ALTER TABLE productos ADD COLUMN IF NOT EXISTS descripcion TEXT NOT NULL DEFAULT ''"
        )
        cur.execute(
            """ALTER TABLE productos ADD COLUMN IF NOT EXISTS categoria_id INTEGER
               REFERENCES categorias(id) ON DELETE SET NULL"""
        )
        categoria_sin_asignar = _obtener_categoria_id(cur, "Sin categoría")
        cur.execute(
            "UPDATE productos SET categoria_id = %s WHERE categoria_id IS NULL",
            (categoria_sin_asignar,),
        )
        cur.execute(
            """INSERT INTO paleta_pagina (id, fondo, superficie, primario, acento)
               VALUES (1, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING""",
            tuple(PALETA_PREDETERMINADA.values()),
        )

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
            for nombre, precio, imagen_url, descripcion in _PRODUCTOS_INICIALES:
                categoria = "Electrónica" if nombre == "Calculadora" else "Papelería y útiles"
                cur.execute(
                    """INSERT INTO productos
                       (nombre, precio, imagen_url, descripcion, categoria_id)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (
                        nombre,
                        precio,
                        imagen_url,
                        descripcion,
                        _obtener_categoria_id(cur, categoria),
                    ),
                )


#users
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


def obtener_paleta():
    with conexion() as conn, _cursor(conn) as cur:
        cur.execute(
            "SELECT fondo, superficie, primario, acento FROM paleta_pagina WHERE id = 1"
        )
        fila = cur.fetchone()
    return dict(fila) if fila else dict(PALETA_PREDETERMINADA)


def guardar_paleta(admin_id, paleta):
    if not isinstance(paleta, dict) or set(paleta) != set(PALETA_PREDETERMINADA):
        raise ErrorValidacion("La paleta de colores no es válida.")
    for color in paleta.values():
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise ErrorValidacion("Usa colores hexadecimales con el formato #RRGGBB.")

    with conexion() as conn, _cursor(conn) as cur:
        if not _es_admin(cur, admin_id):
            raise ErrorPermiso("Solo el administrador puede personalizar la página.")
        cur.execute(
            """UPDATE paleta_pagina
               SET fondo = %s, superficie = %s, primario = %s, acento = %s
               WHERE id = 1""",
            tuple(paleta[campo] for campo in PALETA_PREDETERMINADA),
        )
        if cur.rowcount == 0:
            raise ErrorValidacion("No se encontró la configuración de colores.")


#productos
def listar_categorias():
    with conexion() as conn, _cursor(conn) as cur:
        cur.execute(
            """SELECT DISTINCT c.id, c.nombre
               FROM categorias c
               JOIN productos p ON p.categoria_id = c.id
               ORDER BY c.nombre"""
        )
        return [dict(fila) for fila in cur.fetchall()]


def listar_productos(filtro="", categoria_id=None):
    with conexion() as conn, _cursor(conn) as cur:
        cur.execute(
            """SELECT p.id, p.nombre, p.precio, p.imagen_url, p.descripcion,
                      c.nombre AS categoria, s.nombre AS sucursal, i.cantidad
               FROM productos p
               LEFT JOIN categorias c ON c.id = p.categoria_id
               LEFT JOIN inventario_productos i ON i.producto_id = p.id
               LEFT JOIN sucursales s ON s.id = i.sucursal_id
               WHERE (p.nombre ILIKE %s OR c.nombre ILIKE %s)
                 AND (%s IS NULL OR c.id = %s)
               ORDER BY p.id, s.nombre""",
            (
                f"%{filtro.strip()}%",
                f"%{filtro.strip()}%",
                categoria_id,
                categoria_id,
            ),
        )
        productos = {}
        for fila in cur.fetchall():
            producto = productos.setdefault(
                fila["id"],
                {
                    "id": fila["id"],
                    "nombre": fila["nombre"],
                    "precio": fila["precio"],
                    "imagen_url": fila["imagen_url"],
                    "descripcion": fila["descripcion"],
                    "categoria": fila["categoria"] or "Sin categoría",
                    "sucursales": [],
                },
            )
            if fila["sucursal"] is not None:
                producto["sucursales"].append({
                    "nombre": fila["sucursal"],
                    "cantidad": fila["cantidad"],
                })
        return list(productos.values())


def agregar_producto(
    usuario_id,
    nombre,
    precio,
    imagen_url="",
    descripcion="",
    categoria="Sin categoría",
):
    nombre = (nombre or "").strip()
    descripcion = (descripcion or "").strip()
    categoria = (categoria or "").strip()
    if not nombre:
        raise ErrorValidacion("El nombre es obligatorio.")
    if not categoria:
        raise ErrorValidacion("La categoría es obligatoria.")
    if len(categoria) > 100:
        raise ErrorValidacion("La categoría no puede superar los 100 caracteres.")
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
        categoria_id = _obtener_categoria_id(cur, categoria)
        cur.execute(
            """INSERT INTO productos
               (nombre, precio, imagen_url, descripcion, categoria_id, creado_por)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (nombre, precio, imagen_url, descripcion, categoria_id, usuario_id),
        )
        return cur.fetchone()["id"]


def actualizar_categoria(usuario_id, producto_id, categoria):
    categoria = (categoria or "").strip()
    if not categoria:
        raise ErrorValidacion("La categoría es obligatoria.")
    if len(categoria) > 100:
        raise ErrorValidacion("La categoría no puede superar los 100 caracteres.")

    with conexion() as conn, _cursor(conn) as cur:
        if not _puede_gestionar(cur, usuario_id):
            raise ErrorPermiso("No tienes permiso para modificar productos.")
        categoria_id = _obtener_categoria_id(cur, categoria)
        cur.execute(
            "UPDATE productos SET categoria_id = %s WHERE id = %s",
            (categoria_id, producto_id),
        )
        if cur.rowcount == 0:
            raise ErrorValidacion("El producto ya no existe.")


def actualizar_descripcion(usuario_id, producto_id, descripcion):
    descripcion = (descripcion or "").strip()
    with conexion() as conn, _cursor(conn) as cur:
        if not _puede_gestionar(cur, usuario_id):
            raise ErrorPermiso("No tienes permiso para modificar productos.")
        cur.execute(
            "UPDATE productos SET descripcion = %s WHERE id = %s",
            (descripcion, producto_id),
        )
        if cur.rowcount == 0:
            raise ErrorValidacion("El producto ya no existe.")


def actualizar_stock(usuario_id, producto_id, sucursal, cantidad):
    sucursal = (sucursal or "").strip()
    if not sucursal:
        raise ErrorValidacion("El nombre de la sucursal es obligatorio.")
    try:
        cantidad = int(str(cantidad).strip())
    except (TypeError, ValueError):
        raise ErrorValidacion("La cantidad debe ser un número entero.") from None
    if cantidad < 0:
        raise ErrorValidacion("La cantidad no puede ser negativa.")

    with conexion() as conn, _cursor(conn) as cur:
        if not _puede_gestionar(cur, usuario_id):
            raise ErrorPermiso("No tienes permiso para modificar el inventario.")
        cur.execute("SELECT 1 FROM productos WHERE id = %s", (producto_id,))
        if cur.fetchone() is None:
            raise ErrorValidacion("El producto ya no existe.")
        cur.execute(
            """INSERT INTO sucursales (nombre) VALUES (%s)
               ON CONFLICT DO NOTHING""",
            (sucursal,),
        )
        cur.execute(
            "SELECT id FROM sucursales WHERE LOWER(nombre) = LOWER(%s)",
            (sucursal,),
        )
        sucursal_id = cur.fetchone()["id"]
        cur.execute(
            """INSERT INTO inventario_productos (producto_id, sucursal_id, cantidad)
               VALUES (%s, %s, %s)
               ON CONFLICT (producto_id, sucursal_id)
               DO UPDATE SET cantidad = EXCLUDED.cantidad""",
            (producto_id, sucursal_id, cantidad),
        )


def eliminar_producto(usuario_id, producto_id):
    with conexion() as conn, _cursor(conn) as cur:
        if not _puede_gestionar(cur, usuario_id):
            raise ErrorPermiso("No tienes permiso para eliminar productos.")
        cur.execute("DELETE FROM productos WHERE id = %s", (producto_id,))
