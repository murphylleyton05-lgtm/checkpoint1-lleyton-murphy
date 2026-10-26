#!/usr/bin/env python3
"""Genera los gráficos SVG del ebook a partir de los datos de los casos.

Paleta validada (dataviz validate_palette, modo claro):
  serie 1 (barras)  #1a7fb5   serie 2 (línea)  #c8650f
Las líneas de referencia neutras usan tinta secundaria #3d4d55.
Uso: python3 herramientas/graficos.py
"""
from pathlib import Path

DESTINO = Path(__file__).resolve().parent.parent / "fuente" / "graficos"
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
AZUL, AMBAR, TINTA2, TENUE, GRILLA = "#1a7fb5", "#c8650f", "#3d4d55", "#5f6f77", "#e3e9ec"
FUENTE = "Inter, Arial, sans-serif"


def miles(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def barra(x, y_tope, ancho, base):
    """Columna con extremo de datos redondeado (4px) y base recta."""
    r = min(4, (base - y_tope))
    return (f'<path d="M{x:.1f} {base:.1f} V{y_tope + r:.1f} Q{x:.1f} {y_tope:.1f} {x + r:.1f} {y_tope:.1f} '
            f'H{x + ancho - r:.1f} Q{x + ancho:.1f} {y_tope:.1f} {x + ancho:.1f} {y_tope + r:.1f} V{base:.1f} Z"/>')


def grafico_columnas(nombre, valores, etiquetas, vmax, paso, lineas=(), escalones=None,
                     destacar=(), ancho_total=720, alto_total=270, titulo_eje="USD"):
    """valores: columnas. lineas: [(valor, color, rótulo)]. escalones: serie (lista) dibujada como línea."""
    izq, der, sup, inf = 52, 600, 16, 222
    w, h = der - izq, inf - sup
    banda = w / len(valores)
    ancho = min(24, banda * 0.55)
    esc = h / vmax
    p = [f'<svg viewBox="0 0 {ancho_total} {alto_total}" xmlns="http://www.w3.org/2000/svg" role="img" font-family="{FUENTE}">']
    # grilla y eje
    v = 0
    while v <= vmax + 1e-9:
        y = inf - v * esc
        p.append(f'<line x1="{izq}" y1="{y:.1f}" x2="{der}" y2="{y:.1f}" stroke="{GRILLA if v else "#9fb0b7"}" stroke-width="1"/>')
        p.append(f'<text x="{izq - 8}" y="{y + 3.5:.1f}" font-size="10.5" fill="{TENUE}" text-anchor="end">{miles(v)}</text>')
        v += paso
    p.append(f'<text x="{izq - 8}" y="{sup - 4}" font-size="10" fill="{TENUE}" text-anchor="end">{titulo_eje}</text>')
    # columnas (2px de aire entre bandas garantizado por el ancho máximo)
    p.append(f'<g fill="{AZUL}">')
    for i, val in enumerate(valores):
        x = izq + i * banda + (banda - ancho) / 2
        p.append(barra(x, inf - val * esc, ancho, inf))
    p.append('</g>')
    for i, et in enumerate(etiquetas):
        x = izq + i * banda + banda / 2
        p.append(f'<text x="{x:.1f}" y="{inf + 16}" font-size="10.5" fill="{TENUE}" text-anchor="middle">{et}</text>')
    # rótulos selectivos sobre columnas
    for i in destacar:
        x = izq + i * banda + banda / 2
        y = inf - valores[i] * esc - 6
        p.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="10.5" font-weight="600" fill="{TINTA2}" text-anchor="middle">{miles(valores[i])}</text>')
    # serie escalonada (p. ej., sueldo pagado)
    if escalones:
        pts = []
        for i, val in enumerate(escalones):
            x0 = izq + i * banda
            x1 = x0 + banda
            y = inf - val * esc
            pts.append(f"{x0:.1f},{y:.1f} {x1:.1f},{y:.1f}")
        p.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{AMBAR}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>')
        y_fin = inf - escalones[-1] * esc
        p.append(f'<circle cx="{der:.1f}" cy="{y_fin:.1f}" r="4.5" fill="{AMBAR}" stroke="#ffffff" stroke-width="2"/>')
    # líneas de referencia con rótulo directo a la derecha
    for val, color, rotulo in lineas:
        y = inf - val * esc
        p.append(f'<line x1="{izq}" y1="{y:.1f}" x2="{der}" y2="{y:.1f}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>')
        p.append(f'<text x="{der + 8}" y="{y + 3.5:.1f}" font-size="10.5" font-weight="600" fill="{TINTA2}">{rotulo}</text>')
    p.append('</svg>')
    return "\n".join(p)


def grafico_linea(nombre, valores, etiquetas, vmax, paso, meta=None, ancho_total=720, alto_total=250):
    izq, der, sup, inf = 52, 600, 16, 202
    w, h = der - izq, inf - sup
    esc = h / vmax
    n = len(valores)
    xs = [izq + i * w / (n - 1) for i in range(n)]
    p = [f'<svg viewBox="0 0 {ancho_total} {alto_total}" xmlns="http://www.w3.org/2000/svg" role="img" font-family="{FUENTE}">']
    v = 0
    while v <= vmax + 1e-9:
        y = inf - v * esc
        p.append(f'<line x1="{izq}" y1="{y:.1f}" x2="{der}" y2="{y:.1f}" stroke="{GRILLA if v else "#9fb0b7"}" stroke-width="1"/>')
        p.append(f'<text x="{izq - 8}" y="{y + 3.5:.1f}" font-size="10.5" fill="{TENUE}" text-anchor="end">{miles(v)}</text>')
        v += paso
    p.append(f'<text x="{izq - 8}" y="{sup - 4}" font-size="10" fill="{TENUE}" text-anchor="end">USD</text>')
    for x, et in zip(xs, etiquetas):
        p.append(f'<text x="{x:.1f}" y="{inf + 16}" font-size="10.5" fill="{TENUE}" text-anchor="middle">{et}</text>')
    area = f"{xs[0]:.1f},{inf} " + " ".join(f"{x:.1f},{inf - v * esc:.1f}" for x, v in zip(xs, valores)) + f" {xs[-1]:.1f},{inf}"
    p.append(f'<polygon points="{area}" fill="{AZUL}" fill-opacity="0.10"/>')
    linea = " ".join(f"{x:.1f},{inf - v * esc:.1f}" for x, v in zip(xs, valores))
    p.append(f'<polyline points="{linea}" fill="none" stroke="{AZUL}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>')
    p.append(f'<circle cx="{xs[-1]:.1f}" cy="{inf - valores[-1] * esc:.1f}" r="4.5" fill="{AZUL}" stroke="#ffffff" stroke-width="2"/>')
    p.append(f'<text x="{xs[-1] + 8:.1f}" y="{inf - valores[-1] * esc + 4:.1f}" font-size="10.5" font-weight="600" fill="{TINTA2}">{miles(valores[-1])}</text>')
    if meta:
        val, rotulo = meta
        y = inf - val * esc
        p.append(f'<line x1="{izq}" y1="{y:.1f}" x2="{der}" y2="{y:.1f}" stroke="{TINTA2}" stroke-width="1.6"/>')
        p.append(f'<text x="{der + 8}" y="{y + 3.5:.1f}" font-size="10.5" font-weight="600" fill="{TINTA2}">{rotulo}</text>')
    p.append('</svg>')
    return "\n".join(p)


def main():
    DESTINO.mkdir(exist_ok=True)
    # --- Valeria: ingreso disponible (bruto x 0,80 - 200) ---
    bruto = [2900, 1800, 4200, 2400, 3600, 1500, 2700, 3900, 2100, 5200, 2600, 1900]
    disp = [b * 0.8 - 200 for b in bruto]
    prom = sum(disp) / 12
    piso = sum(sorted(disp)[:3]) / 3
    svg = grafico_columnas("valeria-disponible", disp, MESES, 4000, 1000,
                           lineas=[(prom, AMBAR, f"Promedio {miles(prom)}"), (piso, TINTA2, f"Piso {miles(piso)}")],
                           destacar=[5, 9])
    (DESTINO / "valeria-disponible.svg").write_text(svg, encoding="utf-8")

    # --- Valeria: simulación del primer año (sueldo de arranque 1.200, sueldo meta 1.600) ---
    meses_pago = ["Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic", "Ene"]
    embalse, sueldos, saldos = 0.0, [], []
    for i in range(12):
        embalse += disp[i]                      # cobros del mes i
        sueldo = 1600 if embalse >= 3200 else 1200
        embalse -= sueldo                        # se paga el día 1 del mes siguiente
        sueldos.append(sueldo)
        saldos.append(embalse)
    # columnas: ingreso disponible del mes anterior; línea: sueldo pagado
    svg2 = grafico_columnas("valeria-sueldo", disp, meses_pago, 4000, 1000, escalones=sueldos, destacar=[5, 9])
    (DESTINO / "valeria-sueldo.svg").write_text(svg2, encoding="utf-8")
    svg3 = grafico_linea("valeria-embalse", saldos, meses_pago, 10000, 2000, meta=(9600, "Meta 9.600"))
    (DESTINO / "valeria-embalse.svg").write_text(svg3, encoding="utf-8")

    # --- Martín: estacionalidad (bruto x 0,98 - 280), sueldo meta 1.000 ---
    bruto_m = [1400, 1100, 2600, 2300, 900, 400, 350, 600, 1500, 2800, 3200, 3000]
    disp_m = [b * 0.98 - 280 for b in bruto_m]
    svg4 = grafico_columnas("martin-estacional", disp_m, MESES, 3000, 1000,
                            lineas=[(1000, AMBAR, "Sueldo meta 1.000")], destacar=[6, 10])
    (DESTINO / "martin-estacional.svg").write_text(svg4, encoding="utf-8")

    print("Saldos Valeria:", [round(s) for s in saldos])
    print("Sueldos Valeria:", sueldos)
    print("Disponible Martín:", [round(d) for d in disp_m], "promedio", round(sum(disp_m) / 12, 1))


if __name__ == "__main__":
    main()
