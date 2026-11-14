import flet as ft
import psycopg2

import db
from ui.carrito import Carrito
from ui.colores import opciones_color
from ui.pedidos import (
    ESTADOS_PEDIDO,
    METODOS_PAGO,
    crear_fila_pedido_admin,
    crear_resumen_pedido,
)


def main(page: ft.Page):
    page.title = "E-commerce Universitario"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.AUTO

    # Estado de la sesión (cada pestaña del navegador tiene el suyo)
    sesion = {"usuario": None}
    compra_pendiente_login = {"value": False}

    def es_admin():
        u = sesion["usuario"]
        return bool(u and u["es_admin"])

    def puede_gestionar():
        u = sesion["usuario"]
        return bool(u and (u["es_admin"] or u["puede_gestionar"]))

    def cerrar_dialogo():
        page.pop_dialog()

    def ancho_dialogo(maximo):
        return min(maximo, max(220, (page.width or 1200) - 64))

    def alto_lista_dialogo(maximo):
        return min(maximo, max(140, (page.height or 800) * 0.55))

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
    carrito = Carrito(
        page=page,
        obtener_stock=lambda producto_id: ejecutar_bd(db.obtener_stock_total, producto_id),
        notificar=notificar,
        ancho=ancho_dialogo,
        cerrar_dialogo=cerrar_dialogo,
        continuar_compra=lambda: comenzar_compra(),
        color_primario=paleta["primario"],
    )

    #reg
    campo_reg_usuario = ft.TextField(label="Nuevo Usuario", prefix_icon="person", width=ancho_dialogo(300))
    campo_reg_correo = ft.TextField(label="Correo Electrónico", prefix_icon="email", width=ancho_dialogo(300))
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
        compra_pendiente_login["value"] = False
        cerrar_dialogo()

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

        cerrar_dialogo()
        if creado_por_admin:
            # El admin crea la cuenta pero sigue con su propia sesión
            notificar(f"Usuario '{resultado['usuario']}' creado correctamente.")
        else:
            sesion["usuario"] = resultado
            actualizar_ui_sesion()
            notificar(f"¡Bienvenido, {resultado['usuario']}! Tu cuenta fue creada.")
            if compra_pendiente_login["value"]:
                compra_pendiente_login["value"] = False
                iniciar_checkout()

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
    def abrir_registro(como_admin=False):
        limpiar_registro()
        check_reg_gestion.visible = como_admin and es_admin()
        campo_reg_usuario.width = ancho_dialogo(300)
        campo_reg_correo.width = ancho_dialogo(300)
        campo_reg_password.width = ancho_dialogo(300)
        ventana_registro.title = ft.Text("Crear Usuario (Admin)" if check_reg_gestion.visible else "Crear Cuenta")
        page.show_dialog(ventana_registro)

    def mostrar_dialogo_registro(e):
        cerrar_dialogo()
        abrir_registro(como_admin=False)

    #login
    campo_usuario = ft.TextField(label="Correo o Usuario", prefix_icon="person", width=ancho_dialogo(300))
    campo_password = ft.TextField(label="Contraseña", prefix_icon="lock", password=True, can_reveal_password=True, width=300)
    error_login = ft.Text("", color="red", size=13)

    def mostrar_dialogo_login(e):
        campo_usuario.value = ""
        campo_password.value = ""
        error_login.value = ""
        campo_usuario.width = ancho_dialogo(300)
        campo_password.width = ancho_dialogo(300)
        page.show_dialog(ventana_login)

    def cerrar_login(e):
        compra_pendiente_login["value"] = False
        cerrar_dialogo()

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
        continuar_compra = compra_pendiente_login["value"]
        compra_pendiente_login["value"] = False
        cerrar_dialogo()
        actualizar_ui_sesion()
        notificar(f"¡Hola, {usuario['usuario']}!")
        if continuar_compra:
            iniciar_checkout()

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

    estado_compra = {
        "sucursal_id": None,
        "sucursal_nombre": "",
        "tipo_entrega": None,
        "datos_envio": None,
    }
    campo_sucursal_compra = ft.Dropdown(
        label="Sucursal disponible",
        width=ancho_dialogo(360),
        options=[],
    )
    error_sucursal_compra = ft.Text("", color="red", size=13)

    def abrir_paso_entrega(e):
        if not campo_sucursal_compra.value:
            error_sucursal_compra.value = "Selecciona una sucursal."
            page.update()
            return
        estado_compra["sucursal_id"] = int(campo_sucursal_compra.value)
        estado_compra["sucursal_nombre"] = next(
            opcion.text
            for opcion in campo_sucursal_compra.options
            if opcion.key == campo_sucursal_compra.value
        )
        texto_sucursal_entrega.value = f"Sucursal elegida: {estado_compra['sucursal_nombre']}"
        cerrar_dialogo()
        campo_tipo_entrega.value = None
        campo_nombre_envio.value = ""
        campo_direccion_envio.value = ""
        campo_localidad_envio.value = ""
        campo_telefono_envio.value = ""
        error_entrega.value = ""
        actualizar_campos_entrega()
        page.show_dialog(ventana_entrega)

    ventana_sucursal_compra = ft.AlertDialog(
        title=ft.Text("Paso 1: Selecciona una sucursal"),
        content=ft.Column(
            [
                ft.Text("Elige una sucursal con existencias para todo tu carrito."),
                campo_sucursal_compra,
                error_sucursal_compra,
            ],
            tight=True,
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda e: cerrar_dialogo()),
            ft.Button(
                content="Continuar",
                on_click=abrir_paso_entrega,
                bgcolor=paleta["primario"],
                color="white",
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    campo_tipo_entrega = ft.Dropdown(
        label="Forma de entrega",
        width=ancho_dialogo(360),
        options=[
            ft.DropdownOption(key="retiro", text="Retiro en sucursal"),
            ft.DropdownOption(key="envio", text="Envío a domicilio"),
        ],
    )
    campo_nombre_envio = ft.TextField(label="Nombre de quien recibe", width=ancho_dialogo(360), visible=False)
    campo_direccion_envio = ft.TextField(label="Dirección", width=ancho_dialogo(360), visible=False)
    campo_localidad_envio = ft.TextField(label="Ciudad o localidad", width=ancho_dialogo(360), visible=False)
    campo_telefono_envio = ft.TextField(label="Teléfono de contacto", width=ancho_dialogo(360), visible=False)
    error_entrega = ft.Text("", color="red", size=13)
    texto_sucursal_entrega = ft.Text()

    def actualizar_campos_entrega(e=None):
        es_envio = campo_tipo_entrega.value == "envio"
        for campo in (
            campo_nombre_envio,
            campo_direccion_envio,
            campo_localidad_envio,
            campo_telefono_envio,
        ):
            campo.visible = es_envio
        page.update()

    campo_tipo_entrega.on_select = actualizar_campos_entrega

    def volver_a_sucursal(e):
        cerrar_dialogo()
        page.show_dialog(ventana_sucursal_compra)

    def abrir_paso_pago(e):
        tipo_entrega = campo_tipo_entrega.value
        if tipo_entrega not in ("retiro", "envio"):
            error_entrega.value = "Selecciona una forma de entrega."
            page.update()
            return
        datos_envio = None
        if tipo_entrega == "envio":
            datos_envio = {
                "nombre": campo_nombre_envio.value,
                "direccion": campo_direccion_envio.value,
                "localidad": campo_localidad_envio.value,
                "telefono": campo_telefono_envio.value,
            }
            if any(not (valor or "").strip() for valor in datos_envio.values()):
                error_entrega.value = "Completa todos los datos de envío."
                page.update()
                return

        estado_compra["tipo_entrega"] = tipo_entrega
        estado_compra["datos_envio"] = datos_envio
        cerrar_dialogo()
        opciones_pago = []
        if tipo_entrega == "retiro":
            opciones_pago.append(
                ft.DropdownOption(key="efectivo_local", text="Efectivo al retirar en el local")
            )
        opciones_pago.extend([
            ft.DropdownOption(key="transferencia", text="Transferencia bancaria"),
            ft.DropdownOption(key="tarjeta_credito", text="Tarjeta de crédito"),
            ft.DropdownOption(key="tarjeta_debito", text="Tarjeta de débito"),
        ])
        campo_metodo_pago.options = opciones_pago
        campo_metodo_pago.value = None
        error_pago.value = ""
        detalle_pago.value = (
            f"Sucursal: {estado_compra['sucursal_nombre']}\n"
            f"Entrega: {'Retiro en sucursal' if tipo_entrega == 'retiro' else 'Envío a domicilio'}"
        )
        if datos_envio:
            detalle_pago.value += (
                f"\nRecibe: {datos_envio['nombre']}"
                f"\nDirección: {datos_envio['direccion']}"
                f"\nLocalidad: {datos_envio['localidad']}"
                f"\nTeléfono: {datos_envio['telefono']}"
            )
        page.show_dialog(ventana_pago)

    ventana_entrega = ft.AlertDialog(
        title=ft.Text("Paso 2: Forma de entrega"),
        content=ft.Column(
            [
                texto_sucursal_entrega,
                campo_tipo_entrega,
                campo_nombre_envio,
                campo_direccion_envio,
                campo_localidad_envio,
                campo_telefono_envio,
                error_entrega,
            ],
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions=[
            ft.TextButton("Volver", on_click=volver_a_sucursal),
            ft.Button(
                content="Continuar",
                on_click=abrir_paso_pago,
                bgcolor=paleta["primario"],
                color="white",
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    campo_metodo_pago = ft.Dropdown(
        label="Método de pago",
        width=ancho_dialogo(360),
        options=[],
    )
    detalle_pago = ft.Text()
    error_pago = ft.Text("", color="red", size=13)
    estado_confirmacion = {"procesando": False, "confirmado": False}

    def volver_a_entrega(e):
        cerrar_dialogo()
        page.show_dialog(ventana_entrega)

    def confirmar_pedido(e):
        if estado_confirmacion["procesando"] or estado_confirmacion["confirmado"]:
            return
        if not campo_metodo_pago.value:
            error_pago.value = "Selecciona un método de pago."
            page.update()
            return
        estado_confirmacion["procesando"] = True
        boton_confirmar_pedido.disabled = True
        page.update()
        try:
            ok, resultado = ejecutar_bd(
                db.crear_pedido,
                sesion["usuario"]["id"],
                estado_compra["sucursal_id"],
                carrito.items_pedido(),
                estado_compra["tipo_entrega"],
                campo_metodo_pago.value,
                estado_compra["datos_envio"],
            )
        finally:
            estado_confirmacion["procesando"] = False
            boton_confirmar_pedido.disabled = estado_confirmacion["confirmado"]
        if not ok:
            error_pago.value = resultado
            page.update()
            return

        estado_confirmacion["confirmado"] = True
        boton_confirmar_pedido.disabled = True
        carrito.limpiar()
        cerrar_dialogo()
        cargar_catalogo(barra_busqueda.value or "")
        texto_confirmacion.value = (
            f"Pedido #{resultado['id']} registrado.\n\n"
            f"Sucursal: {resultado['sucursal']}\n"
            f"Entrega: {'Retiro en sucursal' if resultado['tipo_entrega'] == 'retiro' else 'Envío a domicilio'}\n"
            f"Pago elegido: {METODOS_PAGO[resultado['metodo_pago']]}\n"
            f"Total: ${resultado['total']:.2f}\n"
            "El pago quedó pendiente de coordinación; esta aplicación no procesó ningún cobro."
        )
        page.show_dialog(ventana_confirmacion)

    boton_confirmar_pedido = ft.Button(
        content="Confirmar compra",
        on_click=confirmar_pedido,
        bgcolor=paleta["primario"],
        color="white",
    )
    ventana_pago = ft.AlertDialog(
        title=ft.Text("Paso 3: Método de pago"),
        content=ft.Column(
            [detalle_pago, campo_metodo_pago, error_pago],
            tight=True,
        ),
        actions=[
            ft.TextButton("Volver", on_click=volver_a_entrega),
            boton_confirmar_pedido,
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    texto_confirmacion = ft.Text()
    ventana_confirmacion = ft.AlertDialog(
        title=ft.Text("Pedido registrado"),
        content=texto_confirmacion,
        actions=[
            ft.TextButton("Cerrar", on_click=lambda e: cerrar_dialogo()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def iniciar_checkout():
        estado_confirmacion["confirmado"] = False
        boton_confirmar_pedido.disabled = False
        campo_sucursal_compra.width = ancho_dialogo(360)
        campo_tipo_entrega.width = ancho_dialogo(360)
        campo_metodo_pago.width = ancho_dialogo(360)
        for campo in (
            campo_nombre_envio,
            campo_direccion_envio,
            campo_localidad_envio,
            campo_telefono_envio,
        ):
            campo.width = ancho_dialogo(360)
        ok, sucursales = ejecutar_bd(
            db.listar_sucursales_disponibles,
            carrito.items_pedido(),
        )
        if not ok:
            notificar(sucursales, "red")
            return
        if not sucursales:
            notificar("No hay una sucursal con stock suficiente para todo tu carrito.", "red")
            return

        campo_sucursal_compra.options = [
            ft.DropdownOption(
                key=str(sucursal["id"]),
                text=sucursal["nombre"],
            )
            for sucursal in sucursales
        ]
        campo_sucursal_compra.value = None
        error_sucursal_compra.value = ""
        if carrito.dialogo.open:
            cerrar_dialogo()
        page.show_dialog(ventana_sucursal_compra)

    def comenzar_compra():
        if not carrito.productos:
            notificar("El carrito está vacío.", "red")
            return
        if sesion["usuario"] is None:
            compra_pendiente_login["value"] = True
            cerrar_dialogo()
            mostrar_dialogo_login(None)
            return
        iniciar_checkout()

    #admin
    lista_usuarios_admin = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        height=alto_lista_dialogo(350),
        width=ancho_dialogo(450),
    )

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
        cerrar_dialogo()
        ok, usuarios = ejecutar_bd(db.listar_usuarios, sesion["usuario"]["id"])
        if not ok:
            notificar(usuarios, "red")
            return
        lista_usuarios_admin.height = alto_lista_dialogo(350)
        lista_usuarios_admin.width = ancho_dialogo(450)
        lista_usuarios_admin.controls = [crear_fila_usuario(u) for u in usuarios]
        page.show_dialog(ventana_admin)

    def cerrar_admin(e):
        cerrar_dialogo()

    ventana_admin = ft.AlertDialog(
        title=ft.Text("Administrar Usuarios"),
        content=lista_usuarios_admin,
        actions=[ft.TextButton("Cerrar", on_click=cerrar_admin)],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    lista_mis_pedidos = ft.Column(
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        height=alto_lista_dialogo(450),
        width=ancho_dialogo(620),
    )
    ventana_mis_pedidos = ft.AlertDialog(
        title=ft.Text("Mis compras"),
        content=lista_mis_pedidos,
        actions=[ft.TextButton("Cerrar", on_click=lambda e: cerrar_dialogo())],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def abrir_mis_pedidos(e):
        cerrar_dialogo()
        lista_mis_pedidos.height = alto_lista_dialogo(450)
        lista_mis_pedidos.width = ancho_dialogo(620)
        ok, pedidos = ejecutar_bd(
            db.listar_pedidos_usuario,
            sesion["usuario"]["id"],
        )
        if not ok:
            notificar(pedidos, "red")
            return
        lista_mis_pedidos.controls = (
            [crear_resumen_pedido(pedido, paleta["superficie"]) for pedido in pedidos]
            if pedidos
            else [ft.Text("Todavía no tienes compras registradas.", italic=True)]
        )
        page.show_dialog(ventana_mis_pedidos)

    campo_busqueda_pedidos = ft.TextField(
        label="ID de compra o nombre de usuario",
        width=ancho_dialogo(400),
        on_submit=lambda e: buscar_pedidos_admin(e),
    )
    error_busqueda_pedidos = ft.Text("", color="red", size=13)
    lista_pedidos_admin = ft.Column(
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        height=alto_lista_dialogo(400),
        width=ancho_dialogo(650),
    )
    estado_pedido_a_eliminar = {"id": None}

    def guardar_estado_pedido(pedido_id, selector_estado):
        ok, resultado = ejecutar_bd(
            db.actualizar_estado_pedido,
            sesion["usuario"]["id"],
            pedido_id,
            selector_estado.value,
        )
        if not ok:
            notificar(resultado, "red")
            cargar_resultados_pedidos_admin()
            page.update()
            return
        notificar(f"Compra #{pedido_id}: {ESTADOS_PEDIDO[resultado]}.")
        cargar_resultados_pedidos_admin()
        page.update()

    def volver_a_pedidos_admin(e):
        cerrar_dialogo()
        cargar_resultados_pedidos_admin()
        page.show_dialog(ventana_pedidos_admin)

    def eliminar_pedido_confirmado(e):
        pedido_id = estado_pedido_a_eliminar["id"]
        cerrar_dialogo()
        ok, resultado = ejecutar_bd(
            db.eliminar_pedido_admin,
            sesion["usuario"]["id"],
            pedido_id,
        )
        if not ok:
            notificar(resultado, "red")
        else:
            notificar(f"Compra #{pedido_id} eliminada y stock restituido.")
        cargar_resultados_pedidos_admin()
        page.show_dialog(ventana_pedidos_admin)

    ventana_confirmar_eliminar_pedido = ft.AlertDialog(
        title=ft.Text("Eliminar compra"),
        content=ft.Text(
            "La compra se eliminará y sus unidades se devolverán al inventario. "
            "Esta acción no se puede deshacer."
        ),
        actions=[
            ft.TextButton("Volver", on_click=volver_a_pedidos_admin),
            ft.Button(
                content="Eliminar compra",
                on_click=eliminar_pedido_confirmado,
                bgcolor="red",
                color="white",
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def solicitar_eliminacion_pedido(pedido_id):
        estado_pedido_a_eliminar["id"] = pedido_id
        cerrar_dialogo()
        page.show_dialog(ventana_confirmar_eliminar_pedido)

    def cargar_resultados_pedidos_admin():
        ok, pedidos = ejecutar_bd(
            db.buscar_pedidos_admin,
            sesion["usuario"]["id"],
            campo_busqueda_pedidos.value,
        )
        if not ok:
            error_busqueda_pedidos.value = pedidos
            lista_pedidos_admin.controls.clear()
            return
        error_busqueda_pedidos.value = ""
        lista_pedidos_admin.controls = (
            [
                crear_fila_pedido_admin(
                    pedido,
                    paleta["superficie"],
                    ancho_dialogo,
                    guardar_estado_pedido,
                    solicitar_eliminacion_pedido,
                )
                for pedido in pedidos
            ]
            if pedidos
            else [ft.Text("No se encontraron compras.", italic=True)]
        )

    def buscar_pedidos_admin(e):
        cargar_resultados_pedidos_admin()
        page.update()

    ventana_pedidos_admin = ft.AlertDialog(
        title=ft.Text("Buscar compras"),
        content=ft.Column(
            [
                ft.Row(
                    [
                        campo_busqueda_pedidos,
                        ft.Button(
                            content="Buscar",
                            icon="search",
                            on_click=buscar_pedidos_admin,
                            bgcolor=paleta["primario"],
                            color="white",
                        ),
                    ],
                    wrap=True,
                ),
                error_busqueda_pedidos,
                lista_pedidos_admin,
            ],
            spacing=10,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions=[ft.TextButton("Cerrar", on_click=lambda e: cerrar_dialogo())],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def abrir_pedidos_admin(e):
        cerrar_dialogo()
        lista_pedidos_admin.height = alto_lista_dialogo(400)
        lista_pedidos_admin.width = ancho_dialogo(650)
        campo_busqueda_pedidos.width = ancho_dialogo(400)
        campo_busqueda_pedidos.value = ""
        error_busqueda_pedidos.value = ""
        lista_pedidos_admin.controls.clear()
        page.show_dialog(ventana_pedidos_admin)

    #user
    contenido_perfil = ft.Column(tight=True)

    def cerrar_perfil(e):
        cerrar_dialogo()

    def cerrar_sesion(e):
        sesion["usuario"] = None
        cerrar_dialogo()
        actualizar_ui_sesion()
        notificar("Sesión cerrada.", "blue")

    def admin_crear_usuario(e):
        cerrar_dialogo()
        abrir_registro(como_admin=True)

    def abrir_perfil():
        u = sesion["usuario"]
        rol = "Administrador" if u["es_admin"] else ("Gestor de productos" if u["puede_gestionar"] else "Cliente")
        contenido_perfil.controls = [
            ft.Text(f"Usuario: {u['usuario']}"),
            ft.Text(f"Correo: {u['correo']}"),
            ft.Text(f"Rol: {rol}", weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.TextButton(
                "Mis compras",
                icon="receipt_long",
                on_click=abrir_mis_pedidos,
            ),
        ]
        if u["es_admin"]:
            contenido_perfil.controls += [
                ft.TextButton("Crear usuario", icon="person_add", on_click=admin_crear_usuario),
                ft.TextButton("Administrar usuarios y permisos", icon="admin_panel_settings", on_click=abrir_admin_usuarios),
                ft.TextButton(
                    "Buscar compras",
                    icon="manage_search",
                    on_click=abrir_pedidos_admin,
                ),
            ]
        page.show_dialog(ventana_perfil)

    ventana_perfil = ft.AlertDialog(
        title=ft.Text("Mi Perfil"),
        content=contenido_perfil,
        actions=[
            ft.TextButton("Cerrar", on_click=cerrar_perfil),
            ft.Button(content="Cerrar sesión", bgcolor=paleta["primario"], color="white", on_click=cerrar_sesion),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
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
        nombre: ft.Dropdown(
            label=etiqueta,
            value=paleta[nombre],
            options=opciones_color(paleta[nombre]),
            enable_filter=True,
            enable_search=True,
            menu_height=350,
            menu_width=ancho_dialogo(360),
            width=ancho_dialogo(340),
        )
        for nombre, etiqueta in (
            ("fondo", "Fondo de la página"),
            ("superficie", "Tarjetas y ventanas"),
            ("primario", "Botones principales"),
            ("acento", "Color de acento"),
        )
    }
    error_paleta = ft.Text("", color="red", size=13)

    def cerrar_paleta(e):
        cerrar_dialogo()

    def abrir_paleta(e):
        for nombre, campo in campos_paleta.items():
            campo.value = paleta[nombre]
            campo.options = opciones_color(paleta[nombre])
            campo.width = ancho_dialogo(340)
            campo.menu_width = ancho_dialogo(360)
        error_paleta.value = ""
        page.show_dialog(ventana_paleta)

    def guardar_personalizacion(e):
        nueva_paleta = {
            nombre: campo.value
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
        cerrar_dialogo()
        aplicar_paleta()
        actualizar_menu_categorias()
        cargar_catalogo(barra_busqueda.value or "")
        notificar("Paleta de colores guardada.")

    ventana_paleta = ft.AlertDialog(
        title=ft.Text("Personalizar colores"),
        content=ft.Column(
            [
                ft.Text("Elige entre una amplia variedad de colores con vista previa."),
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
    boton_personalizar_paleta = ft.Button(
        content="Personalizar colores",
        icon="palette",
        on_click=abrir_paleta,
        visible=False,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
    )

    #prod
    campo_prod_nombre = ft.TextField(label="Nombre", width=ancho_dialogo(300))
    campo_prod_precio = ft.TextField(label="Precio ($)", prefix_icon="attach_money", width=ancho_dialogo(300), keyboard_type=ft.KeyboardType.NUMBER)
    campo_prod_categoria = ft.TextField(label="Categoría", width=ancho_dialogo(300))
    campo_prod_imagen = ft.TextField(label="URL de imagen (opcional)", width=ancho_dialogo(300))
    campo_prod_descripcion = ft.TextField(label="Descripción", multiline=True, width=ancho_dialogo(300))
    error_producto = ft.Text("", color="red", size=13)

    def abrir_agregar_producto(e):
        for campo in (
            campo_prod_nombre,
            campo_prod_precio,
            campo_prod_categoria,
            campo_prod_imagen,
            campo_prod_descripcion,
        ):
            campo.width = ancho_dialogo(300)
        for campo in (
            campo_prod_nombre,
            campo_prod_precio,
            campo_prod_categoria,
            campo_prod_imagen,
            campo_prod_descripcion,
        ):
            campo.value = ""
        error_producto.value = ""
        page.show_dialog(ventana_producto)

    def cerrar_agregar_producto(e):
        cerrar_dialogo()

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
        cerrar_dialogo()
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
        cerrar_dialogo()
        actualizar_menu_categorias()
        cargar_catalogo()
        notificar(f"'{nombre}' eliminado.", "orange")

    #catalogo
    producto_detalle = {"producto": None}

    def cerrar_detalle(e):
        cerrar_dialogo()

    def crear_contenido_detalle(producto):
        ancho = min((page.width or 1100) * 0.9, 960)
        alto = min(ancho * 9 / 16, (page.height or 800) * 0.6)
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
            campo_imagen = ft.TextField(
                label="URL de la imagen",
                value=producto["imagen_url"],
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

            def guardar_imagen(e):
                producto_actual = producto_detalle["producto"]
                ok, msg = ejecutar_bd(
                    db.actualizar_imagen,
                    sesion["usuario"]["id"],
                    producto_actual["id"],
                    campo_imagen.value,
                )
                if not ok:
                    notificar(msg, "red")
                    return
                notificar("Imagen actualizada.")
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
                campo_imagen,
                ft.TextButton("Guardar imagen", on_click=guardar_imagen),
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
                on_click=lambda e: carrito.agregar(producto),
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
        page.show_dialog(ventana_detalle)

    def refrescar_detalle(producto_id):
        ok, productos = ejecutar_bd(db.listar_productos, "")
        if not ok:
            notificar(productos, "red")
            return
        producto = next((p for p in productos if p["id"] == producto_id), None)
        if producto is None:
            cerrar_dialogo()
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

    for ventana in (
        carrito.dialogo,
        ventana_registro,
        ventana_login,
        ventana_sucursal_compra,
        ventana_entrega,
        ventana_pago,
        ventana_confirmacion,
        ventana_admin,
        ventana_mis_pedidos,
        ventana_confirmar_eliminar_pedido,
        ventana_pedidos_admin,
        ventana_perfil,
        ventana_paleta,
        ventana_producto,
        ventana_detalle,
    ):
        ventana.scrollable = True

    def crear_tarjeta(producto):
        acciones = [
            ft.Button(
                content="Agregar al carrito",
                icon="add_shopping_cart",
                on_click=lambda e: carrito.agregar(producto),
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
            carrito.boton,
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