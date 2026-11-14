import flet as ft


COLORES_BASE = [
    ("Rojo", "#F44336"),
    ("Coral", "#FF7043"),
    ("Naranja", "#FF9800"),
    ("Ámbar", "#FFC107"),
    ("Amarillo", "#FFEB3B"),
    ("Lima", "#CDDC39"),
    ("Verde", "#4CAF50"),
    ("Esmeralda", "#009688"),
    ("Turquesa", "#00BCD4"),
    ("Celeste", "#03A9F4"),
    ("Azul", "#2196F3"),
    ("Índigo", "#3F51B5"),
    ("Violeta", "#673AB7"),
    ("Morado", "#9C27B0"),
    ("Magenta", "#E91E63"),
    ("Rosa", "#F06292"),
    ("Marrón", "#795548"),
    ("Oliva", "#827717"),
    ("Gris azulado", "#607D8B"),
    ("Gris", "#757575"),
]

TONOS_COLOR = (
    ("Muy claro", 255, 0.72),
    ("Claro", 255, 0.42),
    ("", 0, 0),
    ("Oscuro", 0, 0.25),
    ("Muy oscuro", 0, 0.50),
)


def _mezclar_color(color, destino, proporcion):
    rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    mezclado = tuple(
        round(componente * (1 - proporcion) + destino * proporcion)
        for componente in rgb
    )
    return "#" + "".join(f"{componente:02X}" for componente in mezclado)


def opciones_color(color_actual):
    colores = []
    vistos = set()
    for nombre, base in COLORES_BASE:
        for tono, destino, proporcion in TONOS_COLOR:
            valor = _mezclar_color(base, destino, proporcion)
            if valor in vistos:
                continue
            vistos.add(valor)
            etiqueta = f"{nombre} {tono}".strip()
            colores.append((etiqueta, valor))
    for etiqueta, valor in (
        ("Blanco", "#FFFFFF"),
        ("Gris claro", "#BDBDBD"),
        ("Gris oscuro", "#424242"),
        ("Negro", "#000000"),
    ):
        if valor not in vistos:
            vistos.add(valor)
            colores.append((etiqueta, valor))
    if color_actual not in vistos:
        colores.append((f"Color actual ({color_actual})", color_actual))

    return [
        ft.DropdownOption(
            key=valor,
            text=f"{etiqueta} {valor}",
            content=ft.Row(
                [
                    ft.Container(
                        width=22,
                        height=22,
                        bgcolor=valor,
                        border_radius=4,
                    ),
                    ft.Text(f"{etiqueta}  {valor}"),
                ],
                spacing=8,
            ),
        )
        for etiqueta, valor in colores
    ]
