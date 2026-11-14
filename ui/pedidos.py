import flet as ft


ESTADOS_PEDIDO = {
    "pendiente": "Pendiente",
    "en_preparacion": "En preparación",
    "listo": "Listo para retirar / enviar",
    "entregado": "Entregado",
    "cancelado": "Cancelado",
}

METODOS_PAGO = {
    "efectivo_local": "Efectivo al retirar",
    "transferencia": "Transferencia",
    "tarjeta_credito": "Tarjeta de crédito",
    "tarjeta_debito": "Tarjeta de débito",
}

TRANSICIONES_ESTADO_PEDIDO = {
    "pendiente": ("en_preparacion", "cancelado"),
    "en_preparacion": ("listo", "cancelado"),
    "listo": ("entregado", "cancelado"),
    "entregado": (),
    "cancelado": (),
}


def crear_resumen_pedido(pedido, superficie, admin=False):
    fecha = pedido["creado_en"].strftime("%d/%m/%Y %H:%M")
    controles = [
        ft.Text(
            f"Compra #{pedido['id']} · {fecha}",
            weight=ft.FontWeight.BOLD,
        ),
    ]
    if admin:
        controles.append(ft.Text(f"Usuario: {pedido['nombre_usuario']}"))
    controles.extend([
        ft.Text(f"Estado: {ESTADOS_PEDIDO[pedido['estado']]}"),
        ft.Text(
            f"Sucursal: {pedido['sucursal_nombre']} · "
            f"{'Retiro' if pedido['tipo_entrega'] == 'retiro' else 'Envío'}"
        ),
        ft.Text(
            f"Pago: {METODOS_PAGO[pedido['metodo_pago']]} · "
            f"Total: ${pedido['total']:.2f}"
        ),
    ])
    if pedido["tipo_entrega"] == "envio":
        controles.append(
            ft.Text(
                f"Entrega a: {pedido['nombre_envio']} · {pedido['direccion_envio']}, "
                f"{pedido['localidad_envio']} · Tel. {pedido['telefono_envio']}"
            )
        )
    controles.extend(
        ft.Text(
            f"• {producto['nombre']} x {producto['cantidad']} · "
            f"${producto['precio_unitario'] * producto['cantidad']:.2f}"
        )
        for producto in pedido["productos"]
    )
    return ft.Container(
        content=ft.Column(controles, spacing=4),
        padding=12,
        bgcolor=superficie,
        border_radius=8,
    )


def crear_fila_pedido_admin(
    pedido,
    superficie,
    ancho,
    guardar_estado,
    solicitar_eliminacion,
):
    opciones_estado = [
        ft.DropdownOption(key=estado, text=ESTADOS_PEDIDO[estado])
        for estado in (
            pedido["estado"],
            *TRANSICIONES_ESTADO_PEDIDO[pedido["estado"]],
        )
    ]
    selector_estado = ft.Dropdown(
        label="Estado",
        value=pedido["estado"],
        options=opciones_estado,
        width=ancho(260),
        disabled=not TRANSICIONES_ESTADO_PEDIDO[pedido["estado"]],
    )
    return ft.Container(
        content=ft.Column(
            [
                crear_resumen_pedido(pedido, superficie, admin=True),
                ft.Row(
                    [
                        selector_estado,
                        ft.TextButton(
                            "Guardar estado",
                            on_click=lambda e, pid=pedido["id"], field=selector_estado:
                                guardar_estado(pid, field),
                        ),
                        ft.TextButton(
                            "Eliminar",
                            icon="delete",
                            style=ft.ButtonStyle(color="red"),
                            on_click=lambda e, pid=pedido["id"]:
                                solicitar_eliminacion(pid),
                        ),
                    ],
                    wrap=True,
                ),
            ],
            spacing=4,
        ),
        padding=8,
        bgcolor=superficie,
        border_radius=8,
    )
