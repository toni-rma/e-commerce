import flet as ft

def main(page: ft.Page):
    page.title = "E-commerce Universitario"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    
    productos_en_carrito = []
    
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
                lista_items_carrito.controls.append(ft.Text(f"• {item['nombre']} - ${item['precio']}"))
                total += float(item["precio"])
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
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
    )

    # Lógica y componentes de Registro
    campo_reg_usuario = ft.TextField(label="Nuevo Usuario", prefix_icon="person", width=300)
    campo_reg_correo = ft.TextField(label="Correo Electrónico", prefix_icon="email", width=300)
    campo_reg_password = ft.TextField(label="Contraseña", prefix_icon="lock", password=True, can_reveal_password=True, width=300)

    def cerrar_registro(e):
        ventana_registro.open = False
        page.update()

    def procesar_registro(e):
        print(f"Registro exitoso - Usuario: {campo_reg_usuario.value}, Correo: {campo_reg_correo.value}")
        ventana_registro.open = False
        boton_usuario.content = ft.Text("👤 Mi Perfil", size=16, weight=ft.FontWeight.BOLD)
        page.update()

    ventana_registro = ft.AlertDialog(
        title=ft.Text("Crear Cuenta"),
        content=ft.Column([
            campo_reg_usuario,
            campo_reg_correo,
            campo_reg_password,
        ], tight=True, alignment=ft.MainAxisAlignment.CENTER),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_registro),
            ft.Button(content="Registrarse", bgcolor="blue", color="white", on_click=procesar_registro),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(ventana_registro)

    def mostrar_dialogo_registro(e):
        ventana_login.open = False # Cierra el login primero
        ventana_registro.open = True
        page.update()

    # Lógica y componentes de Inicio de Sesión
    campo_usuario = ft.TextField(label="Correo o Usuario", prefix_icon="person", width=300)
    campo_password = ft.TextField(label="Contraseña", prefix_icon="lock", password=True, can_reveal_password=True, width=300)

    def mostrar_dialogo_login(e):
        ventana_login.open = True
        page.update()

    def cerrar_login(e):
        ventana_login.open = False
        page.update()

    def procesar_login(e):
        print(f"Intento de acceso - Usuario: {campo_usuario.value}, Pass: {campo_password.value}")
        ventana_login.open = False
        boton_usuario.content = ft.Text("👤 Mi Perfil", size=16, weight=ft.FontWeight.BOLD)
        page.update()

    ventana_login = ft.AlertDialog(
        title=ft.Text("Iniciar Sesión"),
        content=ft.Column([
            campo_usuario,
            campo_password,
            ft.TextButton("¿No tienes cuenta? Regístrate aquí", on_click=mostrar_dialogo_registro) # Evento on_click agregado
        ], tight=True, alignment=ft.MainAxisAlignment.CENTER),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_login),
            ft.Button(content="Acceder", bgcolor="green", color="white", on_click=procesar_login), 
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.overlay.append(ventana_login)

    boton_usuario = ft.Button(
        content=ft.Text("👤 Iniciar Sesión", size=16, weight=ft.FontWeight.BOLD),
        on_click=mostrar_dialogo_login,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
    )

    barra_busqueda = ft.TextField(
        hint_text="Buscar productos...",
        prefix_icon="search",
        border_radius=20,
        height=45,
        content_padding=10,
        expand=True,
        bgcolor="#e9ecef", 
        border_color="transparent" 
    )

    def crear_tarjeta(nombre, precio, url_imagen):
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Image(src=url_imagen, width=150, height=150, border_radius=10),
                    ft.Text(nombre, size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(f"${precio}", size=16, color="green"),
                    ft.Button(
                        content="Agregar al carrito", 
                        icon="add_shopping_cart", 
                        on_click=lambda e: agregar_al_carrito(e, nombre, precio)
                    )
                ], 
                alignment=ft.MainAxisAlignment.CENTER, 
                horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20,
                width=220
            )
        )

    catalogo = ft.Row(
        wrap=True,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=20,
        run_spacing=20
    )

    catalogo.controls.append(crear_tarjeta("Mochila", "45.00", "https://picsum.photos/200/200?1"))
    catalogo.controls.append(crear_tarjeta("Cuaderno", "12.50", "https://picsum.photos/200/200?2"))
    catalogo.controls.append(crear_tarjeta("Bolígrafo", "3.00", "https://picsum.photos/200/200?3"))
    catalogo.controls.append(crear_tarjeta("Calculadora", "25.00", "https://picsum.photos/200/200?4"))

    navbar = ft.Container(
        content=ft.Row([
            ft.Text("Catálogo", size=30, weight=ft.FontWeight.W_900), 
            barra_busqueda,
            boton_usuario, 
            boton_ver_carrito
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=20),
        bgcolor="#ffffff", 
        padding=15,
        border_radius=10
    )

    page.add(
        navbar,
        catalogo
    )

if __name__ == "__main__":
    print("Iniciando servidor web...")
    print("http://localhost:8551")
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8551, host="0.0.0.0")

#python3 -m venv venv  !!No se olviden de activar el virtual enviroment
#source venv/bin/activate