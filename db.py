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

CREATE TABLE IF NOT EXISTS pedidos (
    id                SERIAL PRIMARY KEY,
    usuario_id        INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    sucursal_id       INTEGER REFERENCES sucursales(id) ON DELETE SET NULL,
    sucursal_nombre   VARCHAR(100) NOT NULL,
    tipo_entrega      VARCHAR(10) NOT NULL CHECK (tipo_entrega IN ('retiro', 'envio')),
    metodo_pago       VARCHAR(30) NOT NULL CHECK (
        metodo_pago IN ('efectivo_local', 'transferencia', 'tarjeta_credito', 'tarjeta_debito')
    ),
    nombre_envio      VARCHAR(100),
    direccion_envio   VARCHAR(250),
    localidad_envio   VARCHAR(100),
    telefono_envio    VARCHAR(30),
    total             NUMERIC(10,2) NOT NULL CHECK (total >= 0),
    estado            VARCHAR(20) NOT NULL DEFAULT 'pendiente' CHECK (
        estado IN ('pendiente', 'en_preparacion', 'listo', 'entregado', 'cancelado')
    ),
    stock_reintegrado BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (metodo_pago <> 'efectivo_local' OR tipo_entrega = 'retiro'),
    CHECK (
        (tipo_entrega = 'envio'
         AND nombre_envio IS NOT NULL
         AND direccion_envio IS NOT NULL
         AND localidad_envio IS NOT NULL
         AND telefono_envio IS NOT NULL)
        OR tipo_entrega = 'retiro'
    )
);
CREATE INDEX IF NOT EXISTS ix_pedidos_usuario_creado
    ON pedidos (usuario_id, creado_en DESC);

CREATE TABLE IF NOT EXISTS pedido_productos (
    id              SERIAL PRIMARY KEY,
    pedido_id       INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    producto_id     INTEGER REFERENCES productos(id) ON DELETE SET NULL,
    producto_nombre VARCHAR(100) NOT NULL,
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0)
);
CREATE INDEX IF NOT EXISTS ix_pedido_productos_pedido
    ON pedido_productos (pedido_id);

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
        cur.execute(
            """ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS estado VARCHAR(20)
               NOT NULL DEFAULT 'pendiente' CHECK (
                   estado IN ('pendiente', 'en_preparacion', 'listo', 'entregado', 'cancelado')
               )"""
        )
        cur.execute(
            """ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS stock_reintegrado BOOLEAN
               NOT NULL DEFAULT FALSE"""
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


def obtener_stock_total(producto_id):
    with conexion() as conn, _cursor(conn) as cur:
        cur.execute(
            """SELECT COALESCE(SUM(cantidad), 0) AS stock
               FROM inventario_productos
               WHERE producto_id = %s""",
            (producto_id,),
        )
        return cur.fetchone()["stock"]


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


def actualizar_imagen(usuario_id, producto_id, imagen_url):
    imagen_url = (imagen_url or "").strip()
    if not imagen_url:
        raise ErrorValidacion("La URL de la imagen es obligatoria.")

    with conexion() as conn, _cursor(conn) as cur:
        if not _puede_gestionar(cur, usuario_id):
            raise ErrorPermiso("No tienes permiso para modificar productos.")
        cur.execute(
            "UPDATE productos SET imagen_url = %s WHERE id = %s",
            (imagen_url, producto_id),
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


def _normalizar_items_pedido(items):
    if not isinstance(items, (list, tuple)) or not items:
        raise ErrorValidacion("El carrito está vacío.")

    cantidades = {}
    for item in items:
        if not isinstance(item, dict):
            raise ErrorValidacion("Los productos del carrito no son válidos.")
        producto_id = item.get("producto_id")
        cantidad = item.get("cantidad")
        if isinstance(producto_id, bool) or isinstance(cantidad, bool):
            raise ErrorValidacion("Los productos del carrito no son válidos.")
        try:
            producto_id = int(producto_id)
            cantidad = int(cantidad)
        except (TypeError, ValueError):
            raise ErrorValidacion("Los productos del carrito no son válidos.") from None
        if producto_id <= 0 or cantidad <= 0:
            raise ErrorValidacion("Los productos del carrito no son válidos.")
        cantidades[producto_id] = cantidades.get(producto_id, 0) + cantidad
    return cantidades


def listar_sucursales_disponibles(items):
    """Lista sucursales con stock suficiente para todos los productos del pedido."""
    cantidades = _normalizar_items_pedido(items)
    producto_ids = sorted(cantidades)
    with conexion() as conn, _cursor(conn) as cur:
        cur.execute(
            """SELECT i.sucursal_id, s.nombre AS sucursal, i.producto_id, i.cantidad
               FROM inventario_productos i
               JOIN sucursales s ON s.id = i.sucursal_id
               WHERE i.producto_id = ANY(%s)
               ORDER BY i.sucursal_id, i.producto_id""",
            (producto_ids,),
        )
        sucursales = {}
        for fila in cur.fetchall():
            existencias = sucursales.setdefault(
                fila["sucursal_id"],
                {"id": fila["sucursal_id"], "nombre": fila["sucursal"], "stock": {}},
            )
            existencias["stock"][fila["producto_id"]] = fila["cantidad"]

    return [
        {"id": sucursal["id"], "nombre": sucursal["nombre"]}
        for sucursal in sucursales.values()
        if all(
            sucursal["stock"].get(producto_id, 0) >= cantidad
            for producto_id, cantidad in cantidades.items()
        )
    ]


def crear_pedido(
    usuario_id,
    sucursal_id,
    items,
    tipo_entrega,
    metodo_pago,
    datos_envio=None,
):
    """Registra el pedido y descuenta existencias en una única transacción."""
    cantidades = _normalizar_items_pedido(items)
    if tipo_entrega not in ("retiro", "envio"):
        raise ErrorValidacion("Selecciona retiro en sucursal o envío a domicilio.")
    if metodo_pago not in (
        "efectivo_local",
        "transferencia",
        "tarjeta_credito",
        "tarjeta_debito",
    ):
        raise ErrorValidacion("Selecciona un método de pago válido.")
    if metodo_pago == "efectivo_local" and tipo_entrega != "retiro":
        raise ErrorValidacion("El efectivo solo está disponible para retiro en sucursal.")

    envio = {}
    if tipo_entrega == "envio":
        if not isinstance(datos_envio, dict):
            raise ErrorValidacion("Completa todos los datos de envío.")
        limites = {
            "nombre": 100,
            "direccion": 250,
            "localidad": 100,
            "telefono": 30,
        }
        for campo, limite in limites.items():
            valor = datos_envio.get(campo)
            if not isinstance(valor, str):
                raise ErrorValidacion("Completa todos los datos de envío.")
            valor = valor.strip()
            if not valor:
                raise ErrorValidacion("Completa todos los datos de envío.")
            if len(valor) > limite:
                raise ErrorValidacion(f"El campo de envío '{campo}' supera el largo permitido.")
            envio[campo] = valor

    try:
        sucursal_id = int(sucursal_id)
    except (TypeError, ValueError):
        raise ErrorValidacion("Selecciona una sucursal válida.") from None

    with conexion() as conn, _cursor(conn) as cur:
        cur.execute("SELECT id, nombre FROM sucursales WHERE id = %s", (sucursal_id,))
        sucursal = cur.fetchone()
        if sucursal is None:
            raise ErrorValidacion("La sucursal seleccionada ya no existe.")

        cur.execute("SELECT id FROM usuarios WHERE id = %s", (usuario_id,))
        if cur.fetchone() is None:
            raise ErrorValidacion("Inicia sesión para realizar la compra.")

        productos = []
        total = Decimal("0.00")
        for producto_id, cantidad in sorted(cantidades.items()):
            cur.execute(
                """SELECT p.nombre, p.precio, i.cantidad
                   FROM inventario_productos i
                   JOIN productos p ON p.id = i.producto_id
                   WHERE i.producto_id = %s AND i.sucursal_id = %s
                   FOR UPDATE OF i""",
                (producto_id, sucursal_id),
            )
            producto = cur.fetchone()
            if producto is None or producto["cantidad"] < cantidad:
                nombre = producto["nombre"] if producto else f"producto #{producto_id}"
                raise ErrorValidacion(
                    f"No hay stock suficiente de '{nombre}' en {sucursal['nombre']}."
                )
            productos.append({
                "id": producto_id,
                "nombre": producto["nombre"],
                "cantidad": cantidad,
                "precio": producto["precio"],
            })
            total += producto["precio"] * cantidad

        cur.execute(
            """INSERT INTO pedidos
               (usuario_id, sucursal_id, sucursal_nombre, tipo_entrega, metodo_pago,
                nombre_envio, direccion_envio, localidad_envio, telefono_envio, total)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                usuario_id,
                sucursal_id,
                sucursal["nombre"],
                tipo_entrega,
                metodo_pago,
                envio.get("nombre"),
                envio.get("direccion"),
                envio.get("localidad"),
                envio.get("telefono"),
                total,
            ),
        )
        pedido_id = cur.fetchone()["id"]

        for producto in productos:
            cur.execute(
                """INSERT INTO pedido_productos
                   (pedido_id, producto_id, producto_nombre, cantidad, precio_unitario)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    pedido_id,
                    producto["id"],
                    producto["nombre"],
                    producto["cantidad"],
                    producto["precio"],
                ),
            )
            cur.execute(
                """UPDATE inventario_productos
                   SET cantidad = cantidad - %s
                   WHERE producto_id = %s AND sucursal_id = %s AND cantidad >= %s""",
                (producto["cantidad"], producto["id"], sucursal_id, producto["cantidad"]),
            )
            if cur.rowcount != 1:
                raise ErrorValidacion(
                    f"No hay stock suficiente de '{producto['nombre']}' para completar la compra."
                )

        return {
            "id": pedido_id,
            "total": total,
            "sucursal": sucursal["nombre"],
            "tipo_entrega": tipo_entrega,
            "metodo_pago": metodo_pago,
            "estado": "pendiente",
        }


def _restaurar_stock_pedido(cur, pedido_id, sucursal_id):
    if sucursal_id is None:
        return
    cur.execute(
        """SELECT producto_id, cantidad
           FROM pedido_productos
           WHERE pedido_id = %s AND producto_id IS NOT NULL""",
        (pedido_id,),
    )
    for producto in cur.fetchall():
        cur.execute(
            """INSERT INTO inventario_productos (producto_id, sucursal_id, cantidad)
               VALUES (%s, %s, %s)
               ON CONFLICT (producto_id, sucursal_id)
               DO UPDATE SET cantidad = inventario_productos.cantidad + EXCLUDED.cantidad""",
            (producto["producto_id"], sucursal_id, producto["cantidad"]),
        )


def _agregar_productos_a_pedidos(cur, pedidos):
    if not pedidos:
        return []
    pedidos_por_id = {pedido["id"]: dict(pedido, productos=[]) for pedido in pedidos}
    cur.execute(
        """SELECT pedido_id, producto_nombre, cantidad, precio_unitario
           FROM pedido_productos
           WHERE pedido_id = ANY(%s)
           ORDER BY pedido_id, id""",
        (list(pedidos_por_id),),
    )
    for producto in cur.fetchall():
        pedidos_por_id[producto["pedido_id"]]["productos"].append({
            "nombre": producto["producto_nombre"],
            "cantidad": producto["cantidad"],
            "precio_unitario": producto["precio_unitario"],
        })
    return list(pedidos_por_id.values())


def listar_pedidos_usuario(usuario_id):
    with conexion() as conn, _cursor(conn) as cur:
        cur.execute(
            """SELECT id, usuario_id, sucursal_nombre, tipo_entrega, metodo_pago,
                      nombre_envio, direccion_envio, localidad_envio, telefono_envio,
                      total, estado, creado_en
               FROM pedidos
               WHERE usuario_id = %s
               ORDER BY creado_en DESC, id DESC""",
            (usuario_id,),
        )
        return _agregar_productos_a_pedidos(cur, cur.fetchall())


def buscar_pedidos_admin(admin_id, busqueda):
    busqueda = (busqueda or "").strip()
    if not busqueda:
        raise ErrorValidacion("Escribe un ID de compra o un nombre de usuario.")
    if len(busqueda) > 120:
        raise ErrorValidacion("La búsqueda no puede superar los 120 caracteres.")

    with conexion() as conn, _cursor(conn) as cur:
        if not _es_admin(cur, admin_id):
            raise ErrorPermiso("Solo el administrador puede buscar compras.")
        cur.execute(
            """SELECT p.id, p.usuario_id, u.usuario AS nombre_usuario,
                      p.sucursal_nombre, p.tipo_entrega, p.metodo_pago,
                      p.nombre_envio, p.direccion_envio, p.localidad_envio,
                      p.telefono_envio, p.total, p.estado, p.creado_en
               FROM pedidos p
               JOIN usuarios u ON u.id = p.usuario_id
               WHERE p.id::TEXT = %s OR u.usuario ILIKE %s
               ORDER BY p.creado_en DESC, p.id DESC
               LIMIT 100""",
            (busqueda, f"%{busqueda}%"),
        )
        return _agregar_productos_a_pedidos(cur, cur.fetchall())


def actualizar_estado_pedido(admin_id, pedido_id, nuevo_estado):
    transiciones = {
        "pendiente": {"en_preparacion", "cancelado"},
        "en_preparacion": {"listo", "cancelado"},
        "listo": {"entregado", "cancelado"},
        "entregado": set(),
        "cancelado": set(),
    }
    if nuevo_estado not in transiciones:
        raise ErrorValidacion("El estado seleccionado no es válido.")

    with conexion() as conn, _cursor(conn) as cur:
        if not _es_admin(cur, admin_id):
            raise ErrorPermiso("Solo el administrador puede modificar compras.")
        cur.execute(
            "SELECT estado, sucursal_id, stock_reintegrado FROM pedidos WHERE id = %s FOR UPDATE",
            (pedido_id,),
        )
        pedido = cur.fetchone()
        if pedido is None:
            raise ErrorValidacion("La compra ya no existe.")
        if nuevo_estado == pedido["estado"]:
            return nuevo_estado
        if nuevo_estado not in transiciones[pedido["estado"]]:
            raise ErrorValidacion(
                f"No se puede cambiar el estado de '{pedido['estado']}' a '{nuevo_estado}'."
            )
        if nuevo_estado == "cancelado" and not pedido["stock_reintegrado"]:
            _restaurar_stock_pedido(cur, pedido_id, pedido["sucursal_id"])
            cur.execute(
                "UPDATE pedidos SET estado = %s, stock_reintegrado = TRUE WHERE id = %s",
                (nuevo_estado, pedido_id),
            )
        else:
            cur.execute(
                "UPDATE pedidos SET estado = %s WHERE id = %s",
                (nuevo_estado, pedido_id),
            )
        return nuevo_estado


def eliminar_pedido_admin(admin_id, pedido_id):
    with conexion() as conn, _cursor(conn) as cur:
        if not _es_admin(cur, admin_id):
            raise ErrorPermiso("Solo el administrador puede eliminar compras.")
        cur.execute(
            "SELECT sucursal_id, stock_reintegrado, estado FROM pedidos WHERE id = %s FOR UPDATE",
            (pedido_id,),
        )
        pedido = cur.fetchone()
        if pedido is None:
            raise ErrorValidacion("La compra ya no existe.")
        if not pedido["stock_reintegrado"] and pedido["estado"] != "entregado":
            _restaurar_stock_pedido(cur, pedido_id, pedido["sucursal_id"])
        cur.execute("DELETE FROM pedidos WHERE id = %s", (pedido_id,))


def eliminar_producto(usuario_id, producto_id):
    with conexion() as conn, _cursor(conn) as cur:
        if not _puede_gestionar(cur, usuario_id):
            raise ErrorPermiso("No tienes permiso para eliminar productos.")
        cur.execute("DELETE FROM productos WHERE id = %s", (producto_id,))
