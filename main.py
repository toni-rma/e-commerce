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

    #notify
    aviso = ft.SnackBar(content=ft.Text(""))
    page.overlay.append(aviso)

    def notificar(mensaje, color=None):
        aviso.content = ft.Text(mensaje, color="white")
        aviso.bgcolor = color or paleta["primario"]
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

    paleta = dict(db.PALETA_PREDETERMINADA)
    ok, paleta_guardada = ejecutar_bd(db.obtener_paleta)
    if ok:
        paleta.update(paleta_guardada)

    #cart
    texto_carrito = ft.Text(f"🛒 Carrito: {len(productos_en_carrito)}", size=20, weight=ft.FontWeight.BOLD)
    lista_items_carrito = ft.Column(tight=True, spacing=8)

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
            ft.Button(content="Finalizar Compra", bgcolor=paleta["primario"], color="white", on_click=finalizar_compra),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(ventana_carrito)

    boton_ver_carrito = ft.Button(
        content=texto_carrito,
        on_click=abrir_carrito,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
    )


    #reg
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
            ft.Button(content="Registrarse", bgcolor=paleta["primario"], color="white", on_click=procesar_registro),
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

    #login
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
            ft.Button(content="Acceder", bgcolor=paleta["primario"], color="white", on_click=procesar_login),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(ventana_login)

    #admin
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
    #user
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
            ft.Button(content="Cerrar sesión", bgcolor=paleta["primario"], color="white", on_click=cerrar_sesion),
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

    campos_paleta = {
        "fondo": ft.TextField(label="Fondo de la página", width=300),
        "superficie": ft.TextField(label="Tarjetas y ventanas", width=300),
        "primario": ft.TextField(label="Botones principales", width=300),
        "acento": ft.TextField(label="Color de acento", width=300),
    }
    error_paleta = ft.Text("", color="red", size=13)

    def cerrar_paleta(e):
        ventana_paleta.open = False
        page.update()

    def abrir_paleta(e):
        for nombre, campo in campos_paleta.items():
            campo.value = paleta[nombre]
        error_paleta.value = ""
        ventana_paleta.open = True
        page.update()

    def guardar_personalizacion(e):
        nueva_paleta = {
            nombre: campo.value.strip()
            for nombre, campo in campos_paleta.items()
        }
        ok, resultado = ejecutar_bd(
            db.guardar_paleta,
            sesion["usuario"]["id"],
            nueva_paleta,
        )
        if not ok:
            error_paleta.value = resultado
            page.update()
            return

        paleta.update(nueva_paleta)
        ventana_paleta.open = False
        aplicar_paleta()
        actualizar_menu_categorias()
        cargar_catalogo(barra_busqueda.value or "")
        notificar("Paleta de colores guardada.")

    ventana_paleta = ft.AlertDialog(
        title=ft.Text("Personalizar colores"),
        content=ft.Column(
            [
                ft.Text("Ingresa colores hexadecimales, por ejemplo #1976D2."),
                *campos_paleta.values(),
                error_paleta,
            ],
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_paleta),
            ft.Button(
                content="Guardar",
                on_click=guardar_personalizacion,
                bgcolor=paleta["primario"],
                color="white",
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(ventana_paleta)

    boton_personalizar_paleta = ft.Button(
        content="Personalizar colores",
        icon="palette",
        on_click=abrir_paleta,
        visible=False,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
    )

    #prod
    campo_prod_nombre = ft.TextField(label="Nombre", width=300)
    campo_prod_precio = ft.TextField(label="Precio ($)", prefix_icon="attach_money", width=300, keyboard_type=ft.KeyboardType.NUMBER)
    campo_prod_categoria = ft.TextField(label="Categoría", width=300)
    campo_prod_imagen = ft.TextField(label="URL de imagen (opcional)", width=300)
    campo_prod_descripcion = ft.TextField(label="Descripción", multiline=True, width=300)
    error_producto = ft.Text("", color="red", size=13)

    def abrir_agregar_producto(e):
        for campo in (
            campo_prod_nombre,
            campo_prod_precio,
            campo_prod_categoria,
            campo_prod_imagen,
            campo_prod_descripcion,
        ):
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
            campo_prod_descripcion.value,
            campo_prod_categoria.value,
        )
        if not ok:
            error_producto.value = msg
            page.update()
            return
        ventana_producto.open = False
        actualizar_menu_categorias()
        cargar_catalogo()
        notificar("Producto agregado.")

    ventana_producto = ft.AlertDialog(
        title=ft.Text("Nuevo Producto"),
        content=ft.Column([
            campo_prod_nombre,
            campo_prod_precio,
            campo_prod_categoria,
            campo_prod_imagen,
            campo_prod_descripcion,
            error_producto,
        ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_agregar_producto),
            ft.Button(content="Guardar", bgcolor=paleta["primario"], color="white", on_click=guardar_producto),
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
        ventana_detalle.open = False
        actualizar_menu_categorias()
        cargar_catalogo()
        notificar(f"'{nombre}' eliminado.", "orange")

    #catalogo
    producto_detalle = {"producto": None}

    def cerrar_detalle(e):
        ventana_detalle.open = False
        page.update()

    def crear_contenido_detalle(producto):
        ancho = min((page.width or 1100) * 0.9, 960)
        alto = ancho * 9 / 16
        imagen = ft.Container(
            content=ft.Column(
                [
                    ft.Image(
                        src=producto["imagen_url"],
                        width=ancho * 0.32,
                        height=alto * 0.55,
                        border_radius=10,
                    ),
                    ft.Text(
                        producto["nombre"],
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(f"${float(producto['precio']):.2f}", size=20, color=paleta["acento"]),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
            width=ancho * 0.38,
            height=alto,
            padding=12,
        )
        controles = [
            ft.Text(
                f"Categoría: {producto['categoria']}",
                size=16,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Text("Descripción", size=16, weight=ft.FontWeight.BOLD),
            ft.Text(producto["descripcion"] or "Sin descripción disponible."),
            ft.Text("Disponibilidad por sucursal", size=16, weight=ft.FontWeight.BOLD),
        ]
        if producto["sucursales"]:
            controles.extend(
                ft.Text(
                    f"{sucursal['nombre']}: {sucursal['cantidad']} "
                    f"{'unidad' if sucursal['cantidad'] == 1 else 'unidades'}"
                )
                for sucursal in producto["sucursales"]
            )
        else:
            controles.append(ft.Text("Sin disponibilidad registrada.", italic=True))

        if puede_gestionar():
            campo_categoria = ft.TextField(
                label="Editar categoría",
                value=producto["categoria"],
            )
            campo_descripcion = ft.TextField(
                label="Editar descripción",
                value=producto["descripcion"],
                multiline=True,
            )
            campo_sucursal = ft.TextField(label="Sucursal")
            campo_cantidad = ft.TextField(
                label="Cantidad",
                keyboard_type=ft.KeyboardType.NUMBER,
            )

            def guardar_descripcion(e):
                producto_actual = producto_detalle["producto"]
                ok, msg = ejecutar_bd(
                    db.actualizar_descripcion,
                    sesion["usuario"]["id"],
                    producto_actual["id"],
                    campo_descripcion.value,
                )
                if not ok:
                    notificar(msg, "red")
                    return
                notificar("Descripción actualizada.")
                refrescar_detalle(producto_actual["id"])

            def guardar_categoria(e):
                producto_actual = producto_detalle["producto"]
                ok, msg = ejecutar_bd(
                    db.actualizar_categoria,
                    sesion["usuario"]["id"],
                    producto_actual["id"],
                    campo_categoria.value,
                )
                if not ok:
                    notificar(msg, "red")
                    return
                notificar("Categoría actualizada.")
                actualizar_menu_categorias()
                refrescar_detalle(producto_actual["id"])

            def guardar_stock(e):
                producto_actual = producto_detalle["producto"]
                ok, msg = ejecutar_bd(
                    db.actualizar_stock,
                    sesion["usuario"]["id"],
                    producto_actual["id"],
                    campo_sucursal.value,
                    campo_cantidad.value,
                )
                if not ok:
                    notificar(msg, "red")
                    return
                notificar("Disponibilidad actualizada.")
                refrescar_detalle(producto_actual["id"])

            controles.extend([
                ft.Divider(),
                campo_categoria,
                ft.TextButton("Guardar categoría", on_click=guardar_categoria),
                campo_descripcion,
                ft.TextButton("Guardar descripción", on_click=guardar_descripcion),
                ft.Text("Agregar o actualizar stock", weight=ft.FontWeight.BOLD),
                campo_sucursal,
                campo_cantidad,
                ft.Button(
                    content="Guardar disponibilidad",
                    icon="inventory",
                    on_click=guardar_stock,
                    bgcolor=paleta["primario"],
                    color="white",
                ),
            ])

        controles.append(
            ft.Button(
                content="Agregar al carrito",
                icon="add_shopping_cart",
                bgcolor=paleta["primario"],
                color="white",
                on_click=lambda e: agregar_al_carrito(
                    e,
                    producto["nombre"],
                    float(producto["precio"]),
                ),
            )
        )
        if puede_gestionar():
            controles.append(
                ft.TextButton(
                    "Eliminar producto",
                    icon="delete",
                    style=ft.ButtonStyle(color="red"),
                    on_click=lambda e: eliminar_producto(
                        producto["id"],
                        producto["nombre"],
                    ),
                )
            )

        return ft.Container(
            content=ft.Row(
                [
                    imagen,
                    ft.Container(
                        content=ft.Column(
                            controles,
                            spacing=12,
                            scroll=ft.ScrollMode.AUTO,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        ),
                        width=ancho * 0.62,
                        height=alto,
                        padding=12,
                    ),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            width=ancho,
            height=alto,
        )

    def abrir_detalle(producto):
        producto_detalle["producto"] = producto
        ventana_detalle.title = ft.Text("Detalle del producto")
        ventana_detalle.content = crear_contenido_detalle(producto)
        ventana_detalle.open = True
        page.update()

    def refrescar_detalle(producto_id):
        ok, productos = ejecutar_bd(db.listar_productos, "")
        if not ok:
            notificar(productos, "red")
            return
        producto = next((p for p in productos if p["id"] == producto_id), None)
        if producto is None:
            ventana_detalle.open = False
            notificar("El producto ya no existe.", "red")
        else:
            producto_detalle["producto"] = producto
            ventana_detalle.title = ft.Text("Detalle del producto")
            ventana_detalle.content = crear_contenido_detalle(producto)
        cargar_catalogo(barra_busqueda.value or "")

    ventana_detalle = ft.AlertDialog(
        title=ft.Text("Producto"),
        content=ft.Column([], tight=True),
        actions=[ft.TextButton("Cerrar", on_click=cerrar_detalle)],
        actions_alignment=ft.MainAxisAlignment.END,
        modal=True,
    )
    page.overlay.append(ventana_detalle)

    def crear_tarjeta(producto):
        acciones = [
            ft.Button(
                content="Agregar al carrito",
                icon="add_shopping_cart",
                on_click=lambda e: agregar_al_carrito(
                    e,
                    producto["nombre"],
                    float(producto["precio"]),
                ),
            )
        ]
        if puede_gestionar():
            acciones.append(
                ft.TextButton(
                    "Eliminar",
                    icon="delete",
                    style=ft.ButtonStyle(color="red"),
                    on_click=lambda e: eliminar_producto(
                        producto["id"],
                        producto["nombre"],
                    ),
                )
            )

        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Column([
                            ft.Image(
                                src=producto["imagen_url"],
                                width=150,
                                height=150,
                                border_radius=10,
                            ),
                            ft.Text(
                                producto["nombre"],
                                size=20,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                producto["categoria"],
                                size=13,
                                italic=True,
                                color="grey",
                            ),
                            ft.Text(
                                f"${float(producto['precio']):.2f}",
                                size=16,
                                color=paleta["acento"],
                            ),
                            ft.Text("Ver detalles", size=12, italic=True, color="grey"),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        on_click=lambda e: abrir_detalle(producto),
                        ink=True,
                    ),
                    ft.Row(acciones, alignment=ft.MainAxisAlignment.CENTER, wrap=True),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=16,
                width=260,
                bgcolor=paleta["superficie"],
            ),
            shape=ft.RoundedRectangleBorder(radius=18),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

    catalogo = ft.Row(
        wrap=True,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=20,
        run_spacing=20,
    )

    categoria_seleccionada = {"id": None}
    categoria_sin_cambio = object()
    menu_categorias = ft.Column(spacing=6)

    def actualizar_menu_categorias():
        ok, categorias = ejecutar_bd(db.listar_categorias)
        if not ok:
            menu_categorias.controls = [ft.Text(categorias, color="red")]
            page.update()
            return

        if categoria_seleccionada["id"] is not None and not any(
            categoria["id"] == categoria_seleccionada["id"]
            for categoria in categorias
        ):
            categoria_seleccionada["id"] = None

        menu_categorias.controls = [
            ft.Text("Categorías", size=18, weight=ft.FontWeight.BOLD),
            ft.Button(
                content="Todas",
                on_click=lambda e: seleccionar_categoria(None),
                bgcolor=(
                    paleta["primario"]
                    if categoria_seleccionada["id"] is None
                    else paleta["superficie"]
                ),
                color=(
                    "white"
                    if categoria_seleccionada["id"] is None
                    else paleta["primario"]
                ),
            ),
        ]
        menu_categorias.controls.extend(
            ft.Button(
                content=categoria["nombre"],
                on_click=lambda e, categoria_id=categoria["id"]: seleccionar_categoria(
                    categoria_id
                ),
                bgcolor=(
                    paleta["primario"]
                    if categoria["id"] == categoria_seleccionada["id"]
                    else paleta["superficie"]
                ),
                color=(
                    "white"
                    if categoria["id"] == categoria_seleccionada["id"]
                    else paleta["primario"]
                ),
            )
            for categoria in categorias
        )
        page.update()

    def seleccionar_categoria(categoria_id):
        categoria_seleccionada["id"] = categoria_id
        actualizar_menu_categorias()
        cargar_catalogo(categoria_id=categoria_id)

    def cargar_catalogo(filtro=None, categoria_id=categoria_sin_cambio):
        if categoria_id is not categoria_sin_cambio:
            categoria_seleccionada["id"] = categoria_id
        if filtro is None:
            filtro = barra_busqueda.value or ""
        ok, productos = ejecutar_bd(
            db.listar_productos,
            filtro,
            categoria_seleccionada["id"],
        )
        if not ok:
            catalogo.controls = [ft.Text(productos, color="red")]
        elif not productos:
            catalogo.controls = [ft.Text("No se encontraron productos.", italic=True)]
        else:
            catalogo.controls = [crear_tarjeta(p) for p in productos]
        page.update()

    barra_busqueda = ft.TextField(
        hint_text="Buscar productos...",
        prefix_icon="search",
        border_radius=20,
        height=45,
        content_padding=10,
        expand=True,
        bgcolor=paleta["superficie"],
        border_color="transparent",
        on_change=lambda e: cargar_catalogo(e.control.value or ""),
    )

    menu_lateral_categorias = ft.Container(
        content=menu_categorias,
        width=220,
        padding=12,
        bgcolor=paleta["superficie"],
        border_radius=12,
    )

    #update
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
        boton_personalizar_paleta.visible = es_admin()
        cargar_catalogo(barra_busqueda.value or "")

    def aplicar_paleta():
        page.bgcolor = paleta["fondo"]
        page.theme = ft.Theme(color_scheme_seed=paleta["primario"])
        navbar.bgcolor = paleta["superficie"]
        barra_busqueda.bgcolor = paleta["superficie"]

        visitados = set()

        def aplicar_a_control(control):
            if control is None or isinstance(control, (str, int, float, bool)):
                return
            identidad = id(control)
            if identidad in visitados:
                return
            visitados.add(identidad)

            if isinstance(control, ft.Button):
                control.bgcolor = paleta["primario"]
                control.color = "white"
            elif isinstance(control, ft.Card):
                control.bgcolor = paleta["superficie"]
            elif isinstance(control, ft.AlertDialog):
                control.bgcolor = paleta["superficie"]
            elif isinstance(control, ft.SnackBar):
                control.bgcolor = paleta["primario"]

            for atributo in ("content", "title", "icon", "controls", "actions"):
                hijos = getattr(control, atributo, None)
                if isinstance(hijos, (list, tuple)):
                    for hijo in hijos:
                        aplicar_a_control(hijo)
                elif hijos is not None:
                    aplicar_a_control(hijos)

        for control in (*page.controls, *page.overlay):
            aplicar_a_control(control)

    navbar = ft.Container(
        content=ft.Row([
            ft.Text("Catálogo", size=30, weight=ft.FontWeight.W_900),
            barra_busqueda,
            boton_agregar_producto,
            boton_personalizar_paleta,
            boton_usuario,
            boton_ver_carrito,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=20),
        bgcolor=paleta["superficie"],
        padding=15,
        border_radius=10,
    )

    contenido_catalogo = ft.Row(
        [
            menu_lateral_categorias,
            ft.Container(content=catalogo, expand=True),
        ],
        spacing=16,
        vertical_alignment=ft.CrossAxisAlignment.START,
        expand=True,
    )

    page.add(navbar, contenido_catalogo)
    aplicar_paleta()
    actualizar_menu_categorias()
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


#python3 -m venv venv  !!No se olviden de activar el virtual enviroment
#source venv/bin/activate