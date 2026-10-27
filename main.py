import flet as ft

def main(page: ft.Page):
    # Configuración de la página web
    page.title = "E-commerce Universitario"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    # Obliga a centrar todos los elementos de la página horizontalmente
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    
    # Estado del carrito
    productos_en_carrito = 0
    texto_carrito = ft.Text(f"🛒 Carrito: {productos_en_carrito}", size=20, weight=ft.FontWeight.BOLD)

    def agregar_al_carrito(e):
        nonlocal productos_en_carrito
        productos_en_carrito += 1
        texto_carrito.value = f"🛒 Carrito: {productos_en_carrito}"
        page.update()

    # Barra de búsqueda
    barra_busqueda = ft.TextField(
        hint_text="Buscar productos...",
        prefix_icon="search",
        border_radius=20,
        height=45,
        content_padding=10,
        expand=True,
        bgcolor="#ffffff", 
        border_color="transparent" 
    )

    # Función generadora de tarjetas
    def crear_tarjeta(nombre, precio, url_imagen):
        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Image(
                        src=url_imagen,
                        width=150,
                        height=150,
                        border_radius=10
                    ),
                    ft.Text(nombre, size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(f"${precio}", size=16, color="green"),
                    ft.Button(content=nombre, icon="add_shopping_cart", on_click=agregar_al_carrito)
                ], 
                alignment=ft.MainAxisAlignment.CENTER, 
                horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=20,
                width=220
            )
        )

    # ft.Row con wrap=True para distribuir las tarjetas dinámicamente
    catalogo = ft.Row(
        wrap=True,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=20,
        run_spacing=20
    )

    # Poblamos el catálogo
    catalogo.controls.append(crear_tarjeta("Mochila", "45.00", "https://picsum.photos/200/200?1"))
    catalogo.controls.append(crear_tarjeta("Cuaderno", "12.50", "https://picsum.photos/200/200?2"))
    catalogo.controls.append(crear_tarjeta("Bolígrafo", "3.00", "https://picsum.photos/200/200?3"))
    catalogo.controls.append(crear_tarjeta("Calculadora", "25.00", "https://picsum.photos/200/200?4"))
    catalogo.controls.append(crear_tarjeta("Remera", "25.00", "https://picsum.photos/200/200?5"))
    catalogo.controls.append(crear_tarjeta("Pantalon", "25.00", "https://picsum.photos/200/200?6"))

    # Navbar envuelto en un contenedor para aplicar color de fondo
    navbar = ft.Container(
        content=ft.Row([
            ft.Text("Catálogo", size=30, weight=ft.FontWeight.W_900), 
            barra_busqueda,
            texto_carrito
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=20),
        bgcolor="#e9ecef", 
        padding=15,
        border_radius=10
    )

    # Agregamos los elementos a la página
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