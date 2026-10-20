import flet as ft

def main(page: ft.Page):
    page.title = "E-commerce"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.theme_mode = ft.ThemeMode.LIGHT
    
    # Product-Card
    product_card = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Image(
                    src="https://picsum.photos/200/200",
                    width=150,
                    height=150,
                    border_radius=10
                ),
                ft.Text("Mochila", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("$45.00", size=16, color="green"),
                ft.Button(content="Agregar al carrito", icon="add_shopping_cart")
            ], 
            alignment=ft.MainAxisAlignment.CENTER, 
            horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
            width=250
        )
    )

    page.add(
        ft.Text("Catálogo de Productos", size=30, weight=ft.FontWeight.W_900),
        product_card
    )

if __name__ == "__main__":
    print("Iniciando servidor web...")
    print("http://localhost:8551")
    ft.run(main, view=ft.AppView.WEB_BROWSER, port=8551, host="0.0.0.0")


#python3 -m venv venv  !!No se olviden de activar el virtual enviroment
#source venv/bin/activate