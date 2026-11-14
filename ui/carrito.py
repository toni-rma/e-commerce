import flet as ft


class Carrito:
    def __init__(
        self,
        page,
        obtener_stock,
        notificar,
        ancho,
        cerrar_dialogo,
        continuar_compra,
        color_primario,
    ):
        self.page = page
        self.obtener_stock = obtener_stock
        self.notificar = notificar
        self.ancho = ancho
        self.cerrar_dialogo = cerrar_dialogo
        self.continuar_compra = continuar_compra
        self.color_primario = color_primario
        self.productos = []
        self.texto_cantidad = ft.Text(
            "🛒 Carrito: 0",
            size=20,
            weight=ft.FontWeight.BOLD,
        )
        self.lista = ft.Column(tight=True, spacing=8, scroll=ft.ScrollMode.AUTO)
        self.dialogo = ft.AlertDialog(
            title=ft.Text("Tu Carrito de Compras"),
            content=self.lista,
            actions=[
                ft.TextButton("Cerrar", on_click=self._cerrar),
                ft.Button(
                    content="Continuar compra",
                    bgcolor=color_primario,
                    color="white",
                    on_click=lambda e: self.continuar_compra(),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            scrollable=True,
        )
        self.boton = ft.Button(
            content=self.texto_cantidad,
            on_click=self.abrir,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
        )

    def agregar(self, producto):
        producto_id = producto["id"]
        ok, stock = self.obtener_stock(producto_id)
        if not ok:
            self.notificar(stock, "red")
            return

        cantidad_actual = sum(
            item["producto_id"] == producto_id for item in self.productos
        )
        if cantidad_actual >= stock:
            if stock == 0:
                self.notificar(
                    f"No hay stock disponible de '{producto['nombre']}'.",
                    "red",
                )
            else:
                self.notificar(
                    f"Solo hay {stock} unidades disponibles de '{producto['nombre']}'.",
                    "red",
                )
            return

        self.productos.append({
            "producto_id": producto_id,
            "nombre": producto["nombre"],
            "precio": float(producto["precio"]),
        })
        self._actualizar_contador()
        self.page.update()

    def items_pedido(self):
        cantidades = {}
        for item in self.productos:
            cantidades[item["producto_id"]] = (
                cantidades.get(item["producto_id"], 0) + 1
            )
        return [
            {"producto_id": producto_id, "cantidad": cantidad}
            for producto_id, cantidad in cantidades.items()
        ]

    def limpiar(self):
        self.productos.clear()
        self._actualizar_contador()

    def abrir(self, e=None):
        self._reconstruir()
        self.page.show_dialog(self.dialogo)

    def _cerrar(self, e):
        self.cerrar_dialogo()

    def _actualizar_contador(self):
        self.texto_cantidad.value = f"🛒 Carrito: {len(self.productos)}"

    def _validar_cantidad(self, producto_id, cantidad, mensaje):
        try:
            cantidad = int(str(cantidad).strip())
        except (TypeError, ValueError):
            mensaje.value = "Ingresa una cantidad entera."
            self.page.update()
            return None
        if cantidad < 1:
            mensaje.value = "La cantidad mínima es 1."
            self.page.update()
            return None

        ok, stock = self.obtener_stock(producto_id)
        if not ok:
            mensaje.value = stock
            self.page.update()
            return None
        if cantidad > stock:
            mensaje.value = f"Stock disponible: {stock} unidades."
            self.page.update()
            return None

        mensaje.value = ""
        self.page.update()
        return cantidad

    def _guardar_cantidad(self, producto_id, cantidad, mensaje):
        cantidad = self._validar_cantidad(producto_id, cantidad, mensaje)
        if cantidad is None:
            return False

        producto = next(
            (
                item for item in self.productos
                if item["producto_id"] == producto_id
            ),
            None,
        )
        if producto is None:
            return False

        datos_producto = {
            "producto_id": producto_id,
            "nombre": producto["nombre"],
            "precio": producto["precio"],
        }
        self.productos[:] = [
            item for item in self.productos
            if item["producto_id"] != producto_id
        ] + [dict(datos_producto) for _ in range(cantidad)]
        self._actualizar_contador()
        self._reconstruir()
        self.page.update()
        return True

    def _quitar_producto(self, producto_id):
        self.productos[:] = [
            item for item in self.productos
            if item["producto_id"] != producto_id
        ]
        self._actualizar_contador()
        self._reconstruir()
        self.page.update()

    def _ajustar_cantidad(self, e, producto_id, campo, delta, mensaje):
        try:
            actual = int(campo.value.strip())
        except (AttributeError, TypeError, ValueError):
            mensaje.value = "Ingresa una cantidad entera."
            self.page.update()
            return
        siguiente = actual + delta
        if siguiente < 1:
            self._quitar_producto(producto_id)
            return
        self._guardar_cantidad(producto_id, siguiente, mensaje)

    def _reconstruir(self):
        self.lista.controls.clear()
        if not self.productos:
            self.lista.controls.append(
                ft.Text("El carrito está vacío.", italic=True)
            )
        else:
            cantidades = {}
            for item in self.productos:
                producto = cantidades.setdefault(
                    item["producto_id"],
                    {
                        "nombre": item["nombre"],
                        "precio": item["precio"],
                        "cantidad": 0,
                    },
                )
                producto["cantidad"] += 1

            total = sum(
                item["precio"] * item["cantidad"]
                for item in cantidades.values()
            )
            for producto_id, item in cantidades.items():
                error = ft.Text("", color="red", size=12)
                campo = ft.TextField(
                    label="Cantidad",
                    value=str(item["cantidad"]),
                    width=self.ancho(100),
                    keyboard_type=ft.KeyboardType.NUMBER,
                    on_change=lambda e, pid=producto_id, msg=error:
                        self._validar_cantidad(pid, e.control.value, msg),
                    on_submit=lambda e, pid=producto_id, msg=error:
                        self._guardar_cantidad(pid, e.control.value, msg),
                )
                self.lista.controls.append(
                    ft.Column(
                        [
                            ft.Text(
                                f"{item['nombre']} · ${item['precio']:.2f} c/u",
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Row(
                                [
                                    ft.IconButton(
                                        icon=ft.Icons.REMOVE,
                                        tooltip="Quitar una unidad",
                                        on_click=lambda e, pid=producto_id, field=campo, msg=error:
                                            self._ajustar_cantidad(e, pid, field, -1, msg),
                                    ),
                                    campo,
                                    ft.IconButton(
                                        icon=ft.Icons.ADD,
                                        tooltip="Agregar una unidad",
                                        on_click=lambda e, pid=producto_id, field=campo, msg=error:
                                            self._ajustar_cantidad(e, pid, field, 1, msg),
                                    ),
                                    ft.TextButton(
                                        "Actualizar",
                                        on_click=lambda e, pid=producto_id, field=campo, msg=error:
                                            self._guardar_cantidad(pid, field.value, msg),
                                    ),
                                    ft.TextButton(
                                        "Quitar",
                                        icon="delete",
                                        on_click=lambda e, pid=producto_id:
                                            self._quitar_producto(pid),
                                    ),
                                ],
                                wrap=True,
                                spacing=4,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            error,
                            ft.Text(
                                f"Subtotal: ${item['precio'] * item['cantidad']:.2f}"
                            ),
                            ft.Divider(),
                        ],
                        spacing=4,
                    )
                )
            self.lista.controls.append(
                ft.Text(f"Total: ${total:.2f}", weight=ft.FontWeight.BOLD, size=18)
            )
        self.page.update()
