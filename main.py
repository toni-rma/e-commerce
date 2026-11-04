import flet as ft
import psycopg2

import db


def main(page: ft.Page):
    page.title = "E-commerce Universitario"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.AUTO

    # Estado de la sesión (cada pestaña del navegador tiene el suyo)
    sesion = {"usuario": None}
    productos_en_carrito = []

    def es_admin():
        u = sesion["usuario"]
        return bool(u and u["es_admin"])

    def puede_gestionar():
        u = sesion["usuario"]
        return bool(u and (u["es_admin"] or u["puede_gestionar"]))

    # ------------------------------------------------------------------
    # Notificaciones
    # ------------------------------------------------------------------
    aviso = ft.SnackBar(content=ft.Text(""))
    page.overlay.append(aviso)

    def notificar(mensaje, color="green"):
        aviso.content = ft.Text(mensaje, color="white")
        aviso.bgcolor = color
        aviso.open = True
        page.update()

    def ejecutar_bd(funcion, *args, **kwargs):
        """Ejecuta una función de db y traduce errores a mensajes. Devuelve (ok, resultado|mensaje)."""
        try:
            return True, funcion(*args, **kwargs)
        except (db.ErrorValidacion, db.ErrorPermiso) as ex:
            return False, str(ex)
        except psycopg2.Error as ex:
            print(f"[BD] Error: {ex}")
            return False, "Error de conexión con la base de datos."

    # ------------------------------------------------------------------
    # Carrito
    # ------------------------------------------------------------------
    texto_carrito = ft.Text(f"🛒 Carrito: {len(productos_en_carrito)}", size=20, weight=ft.FontWeight.BOLD)
    lista_items_carrito = ft.Column()

    def agregar_al_carrito(e, nombre_producto, precio_producto):
        productos_en_carrito.append({"nombre": nombre_producto, "precio": precio_producto})
        texto_carrito.value = f"🛒 Carrito: {len(productos_en_carrito)}"
        page.update()

    def cerrar_carrito(e):
        ventana_carrito.open = False
        page.update()

    def finalizar_compra(e):
        productos_en_carrito.clear()
        texto_carrito.value = f"🛒 Carrito: {len(productos_en_carrito)}"
        ventana_carrito.open = False
        page.update()

    def abrir_carrito(e):
        lista_items_carrito.controls.clear()
        total = 0
        if not productos_en_carrito:
            lista_items_carrito.controls.append(ft.Text("El carrito está vacío.", italic=True))
        else:
            for item in productos_en_carrito:
                lista_items_carrito.controls.append(ft.Text(f"• {item['nombre']} - ${item['precio']:.2f}"))
                total += item["precio"]
            lista_items_carrito.controls.append(ft.Divider())
            lista_items_carrito.controls.append(ft.Text(f"Total: ${total:.2f}", weight=ft.FontWeight.BOLD, size=18))

        ventana_carrito.open = True
        page.update()

    ventana_carrito = ft.AlertDialog(
        title=ft.Text("Tu Carrito de Compras"),
        content=lista_items_carrito,
        actions=[
            ft.TextButton("Cerrar", on_click=cerrar_carrito),
            ft.Button(content="Finalizar Compra", bgcolor="blue", color="white", on_click=finalizar_compra),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(ventana_carrito)

    boton_ver_carrito = ft.Button(
        content=texto_carrito,
        on_click=abrir_carrito,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
    )

    # ------------------------------------------------------------------
    # Registro
    # ------------------------------------------------------------------
    campo_reg_usuario = ft.TextField(label="Nuevo Usuario", prefix_icon="person", width=300)
    campo_reg_correo = ft.TextField(label="Correo Electrónico", prefix_icon="email", width=300)
    campo_reg_password = ft.TextField(label="Contraseña", prefix_icon="lock", password=True, can_reveal_password=True, width=300)
    # Opción oculta: solo visible cuando el administrador crea el usuario
    check_reg_gestion = ft.Checkbox(label="Puede agregar/quitar productos", value=False, visible=False)
    error_registro = ft.Text("", color="red", size=13)

    def limpiar_registro():
        for campo in (campo_reg_usuario, campo_reg_correo, campo_reg_password):
            campo.value = ""
        check_reg_gestion.value = False
        error_registro.value = ""

    def cerrar_registro(e):
        ventana_registro.open = False
        page.update()

    def procesar_registro(e):
        creado_por_admin = es_admin()
        ok, resultado = ejecutar_bd(
            db.registrar_usuario,
            campo_reg_usuario.value,
            campo_reg_correo.value,
            campo_reg_password.value,
            puede_gestionar=creado_por_admin and check_reg_gestion.value,
            admin_id=sesion["usuario"]["id"] if creado_por_admin else None,
        )
        if not ok:
            error_registro.value = resultado
            page.update()
            return

        ventana_registro.open = False
        if creado_por_admin:
            # El admin crea la cuenta pero sigue con su propia sesión
            notificar(f"Usuario '{resultado['usuario']}' creado correctamente.")
        else:
            sesion["usuario"] = resultado
            actualizar_ui_sesion()
            notificar(f"¡Bienvenido, {resultado['usuario']}! Tu cuenta fue creada.")

    ventana_registro = ft.AlertDialog(
        title=ft.Text("Crear Cuenta"),
        content=ft.Column([
            campo_reg_usuario,
            campo_reg_correo,
            campo_reg_password,
            check_reg_gestion,
            error_registro,
        ], tight=True, alignment=ft.MainAxisAlignment.CENTER),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_registro),
            ft.Button(content="Registrarse", bgcolor="blue", color="white", on_click=procesar_registro),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(ventana_registro)

    def abrir_registro(como_admin=False):
        limpiar_registro()
        check_reg_gestion.visible = como_admin and es_admin()
        ventana_registro.title = ft.Text("Crear Usuario (Admin)" if check_reg_gestion.visible else "Crear Cuenta")
        ventana_registro.open = True
        page.update()

    def mostrar_dialogo_registro(e):
        ventana_login.open = False  # Cierra el login primero
        abrir_registro(como_admin=False)

    # ------------------------------------------------------------------
    # Inicio de sesión
    # ------------------------------------------------------------------
    campo_usuario = ft.TextField(label="Correo o Usuario", prefix_icon="person", width=300)
    campo_password = ft.TextField(label="Contraseña", prefix_icon="lock", password=True, can_reveal_password=True, width=300)
    error_login = ft.Text("", color="red", size=13)

    def mostrar_dialogo_login(e):
        campo_usuario.value = ""
        campo_password.value = ""
        error_login.value = ""
        ventana_login.open = True
        page.update()

    def cerrar_login(e):
        ventana_login.open = False
        page.update()

    def procesar_login(e):
        ok, usuario = ejecutar_bd(db.iniciar_sesion, campo_usuario.value, campo_password.value)
        if not ok:
            error_login.value = usuario
            page.update()
            return
        if usuario is None:
            error_login.value = "Usuario o contraseña incorrectos."
            campo_password.value = ""
            page.update()
            return

        sesion["usuario"] = usuario
        ventana_login.open = False
        actualizar_ui_sesion()
        notificar(f"¡Hola, {usuario['usuario']}!")

    campo_password.on_submit = procesar_login

    ventana_login = ft.AlertDialog(
        title=ft.Text("Iniciar Sesión"),
        content=ft.Column([
            campo_usuario,
            campo_password,
            error_login,
            ft.TextButton("¿No tienes cuenta? Regístrate aquí", on_click=mostrar_dialogo_registro),
        ], tight=True, alignment=ft.MainAxisAlignment.CENTER),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_login),
            ft.Button(content="Acceder", bgcolor="green", color="white", on_click=procesar_login),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(ventana_login)

    # ------------------------------------------------------------------
    # Panel de administración de usuarios (solo admin)
    # ------------------------------------------------------------------
    lista_usuarios_admin = ft.Column(scroll=ft.ScrollMode.AUTO, height=350, width=450)

    def cambiar_permiso(usuario_id, switch):
        ok, msg = ejecutar_bd(db.cambiar_permiso_gestion, sesion["usuario"]["id"], usuario_id, switch.value)
        if ok:
            notificar("Permiso actualizado.")
        else:
            switch.value = not switch.value
            notificar(msg, "red")

    def crear_fila_usuario(u):
        if u["es_admin"]:
            control = ft.Text("Administrador", italic=True, color="blue")
        else:
            control = ft.Switch(label="Gestiona productos", value=u["puede_gestionar"])
            control.on_change = lambda e, uid=u["id"], sw=control: cambiar_permiso(uid, sw)
        return ft.Row([
            ft.Column([
                ft.Text(u["usuario"], weight=ft.FontWeight.BOLD),
                ft.Text(u["correo"], size=12, color="grey"),
            ], spacing=0, expand=True),
            control,
        ])

    def abrir_admin_usuarios(e):
        ventana_perfil.open = False
        ok, usuarios = ejecutar_bd(db.listar_usuarios, sesion["usuario"]["id"])
        if not ok:
            notificar(usuarios, "red")
            return
        lista_usuarios_admin.controls = [crear_fila_usuario(u) for u in usuarios]
        ventana_admin.open = True
        page.update()

    def cerrar_admin(e):
        ventana_admin.open = False
        page.update()

    ventana_admin = ft.AlertDialog(
        title=ft.Text("Administrar Usuarios"),
        content=lista_usuarios_admin,
        actions=[ft.TextButton("Cerrar", on_click=cerrar_admin)],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(ventana_admin)

    # ------------------------------------------------------------------
    # Perfil / cerrar sesión
    # ------------------------------------------------------------------
    contenido_perfil = ft.Column(tight=True)

    def cerrar_perfil(e):
        ventana_perfil.open = False
        page.update()

    def cerrar_sesion(e):
        sesion["usuario"] = None
        ventana_perfil.open = False
        actualizar_ui_sesion()
        notificar("Sesión cerrada.", "blue")

    def admin_crear_usuario(e):
        ventana_perfil.open = False
        abrir_registro(como_admin=True)

    def abrir_perfil():
        u = sesion["usuario"]
        rol = "Administrador" if u["es_admin"] else ("Gestor de productos" if u["puede_gestionar"] else "Cliente")
        contenido_perfil.controls = [
            ft.Text(f"Usuario: {u['usuario']}"),
            ft.Text(f"Correo: {u['correo']}"),
            ft.Text(f"Rol: {rol}", weight=ft.FontWeight.BOLD),
        ]
        if u["es_admin"]:
            contenido_perfil.controls += [
                ft.Divider(),
                ft.TextButton("Crear usuario", icon="person_add", on_click=admin_crear_usuario),
                ft.TextButton("Administrar usuarios y permisos", icon="admin_panel_settings", on_click=abrir_admin_usuarios),
            ]
        ventana_perfil.open = True
        page.update()

    ventana_perfil = ft.AlertDialog(
        title=ft.Text("Mi Perfil"),
        content=contenido_perfil,
        actions=[
            ft.TextButton("Cerrar", on_click=cerrar_perfil),
            ft.Button(content="Cerrar sesión", bgcolor="red", color="white", on_click=cerrar_sesion),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(ventana_perfil)

    def click_boton_usuario(e):
        if sesion["usuario"]:
            abrir_perfil()
        else:
            mostrar_dialogo_login(e)

    boton_usuario = ft.Button(
        content=ft.Text("👤 Iniciar Sesión", size=16, weight=ft.FontWeight.BOLD),
        on_click=click_boton_usuario,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
    )

    # ------------------------------------------------------------------
    # Agregar producto (admin o usuarios con permiso)
    # ------------------------------------------------------------------
    campo_prod_nombre = ft.TextField(label="Nombre", width=300)
    campo_prod_precio = ft.TextField(label="Precio ($)", prefix_icon="attach_money", width=300, keyboard_type=ft.KeyboardType.NUMBER)
    campo_prod_imagen = ft.TextField(label="URL de imagen (opcional)", width=300)
    error_producto = ft.Text("", color="red", size=13)

    def abrir_agregar_producto(e):
        for campo in (campo_prod_nombre, campo_prod_precio, campo_prod_imagen):
            campo.value = ""
        error_producto.value = ""
        ventana_producto.open = True
        page.update()

    def cerrar_agregar_producto(e):
        ventana_producto.open = False
        page.update()

    def guardar_producto(e):
        ok, msg = ejecutar_bd(
            db.agregar_producto,
            sesion["usuario"]["id"] if sesion["usuario"] else None,
            campo_prod_nombre.value,
            campo_prod_precio.value,
            campo_prod_imagen.value,
        )
        if not ok:
            error_producto.value = msg
            page.update()
            return
        ventana_producto.open = False
        cargar_catalogo()
        notificar("Producto agregado.")

    ventana_producto = ft.AlertDialog(
        title=ft.Text("Nuevo Producto"),
        content=ft.Column([campo_prod_nombre, campo_prod_precio, campo_prod_imagen, error_producto], tight=True),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_agregar_producto),
            ft.Button(content="Guardar", bgcolor="green", color="white", on_click=guardar_producto),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(ventana_producto)

    boton_agregar_producto = ft.Button(
        content="Agregar producto",
        icon="add",
        on_click=abrir_agregar_producto,
        visible=False,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
    )

    def eliminar_producto(producto_id, nombre):
        ok, msg = ejecutar_bd(db.eliminar_producto, sesion["usuario"]["id"] if sesion["usuario"] else None, producto_id)
        if not ok:
            notificar(msg, "red")
            return
        cargar_catalogo()
        notificar(f"'{nombre}' eliminado.", "orange")

    # ------------------------------------------------------------------
    # Catálogo
    # ------------------------------------------------------------------
    def crear_tarjeta(producto_id, nombre, precio, url_imagen):
        controles = [
            ft.Image(src=url_imagen, width=150, height=150, border_radius=10),
            ft.Text(nombre, size=20, weight=ft.FontWeight.BOLD),
            ft.Text(f"${precio:.2f}", size=16, color="green"),
            ft.Button(
                content="Agregar al carrito",
                icon="add_shopping_cart",
                on_click=lambda e: agregar_al_carrito(e, nombre, precio),
            ),
        ]
        if puede_gestionar():
            controles.append(
                ft.TextButton(
                    "Eliminar",
                    icon="delete",
                    style=ft.ButtonStyle(color="red"),
                    on_click=lambda e: eliminar_producto(producto_id, nombre),
                )
            )
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controles,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=20,
                width=220,
            )
        )

    catalogo = ft.Row(
        wrap=True,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=20,
        run_spacing=20,
    )

    def cargar_catalogo(filtro=""):
        ok, productos = ejecutar_bd(db.listar_productos, filtro)
        if not ok:
            catalogo.controls = [ft.Text(productos, color="red")]
        elif not productos:
            catalogo.controls = [ft.Text("No se encontraron productos.", italic=True)]
        else:
            catalogo.controls = [
                crear_tarjeta(p["id"], p["nombre"], float(p["precio"]), p["imagen_url"]) for p in productos
            ]
        page.update()

    barra_busqueda = ft.TextField(
        hint_text="Buscar productos...",
        prefix_icon="search",
        border_radius=20,
        height=45,
        content_padding=10,
        expand=True,
        bgcolor="#e9ecef",
        border_color="transparent",
        on_change=lambda e: cargar_catalogo(e.control.value or ""),
    )

    # ------------------------------------------------------------------
    # Actualiza la interfaz según la sesión
    # ------------------------------------------------------------------
    def actualizar_ui_sesion():
        u = sesion["usuario"]
        if u:
            # Refresca permisos desde la BD por si el admin los cambió
            ok, actualizado = ejecutar_bd(db.obtener_usuario, u["id"])
            if ok and actualizado:
                sesion["usuario"] = u = actualizado
            boton_usuario.content = ft.Text(f"👤 {u['usuario']}", size=16, weight=ft.FontWeight.BOLD)
        else:
            boton_usuario.content = ft.Text("👤 Iniciar Sesión", size=16, weight=ft.FontWeight.BOLD)
        boton_agregar_producto.visible = puede_gestionar()
        cargar_catalogo(barra_busqueda.value or "")

    navbar = ft.Container(
        content=ft.Row([
            ft.Text("Catálogo", size=30, weight=ft.FontWeight.W_900),
            barra_busqueda,
            boton_agregar_producto,
            boton_usuario,
            boton_ver_carrito,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=20),
        bgcolor="#ffffff",
        padding=15,
        border_radius=10,
    )

    page.add(navbar, catalogo)
    cargar_catalogo()


if __name__ == "__main__":
    try:
        db.inicializar_bd()
    except psycopg2.Error as ex:
        print("No se pudo conectar a PostgreSQL. Revisa DB_HOST, DB_NAME, DB_USER y DB_PASSWORD.")
        print(ex)
        raise SystemExit(1)

    print("Iniciando servidor web...")
    print("http://localhost:8551")
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8551, host="0.0.0.0")
