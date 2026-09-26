"""Costeo derivado de los componentes, igual que el consumo de una venta."""

import json
from decimal import Decimal


def incluir_costeo_combos(costeos, productos):
    por_nombre = {c["producto"].lower(): c for c in costeos}
    por_id = {str(p["id"]): p for p in productos}
    nombres_combos = {p["nombre"].lower() for p in productos if p["es_combo"]}
    resultados = [c for c in costeos if c["producto"].lower() not in nombres_combos]

    for producto in productos:
        if not producto["es_combo"]:
            continue
        ingredientes = {}
        faltantes = []
        componentes = producto.get("combo_items") or []
        if isinstance(componentes, str):
            componentes = json.loads(componentes)
        for componente in componentes:
            base = por_id.get(str(componente["id"]))
            receta = por_nombre.get(base["nombre"].lower()) if base else None
            if not receta or not receta["ingredientes"]:
                faltantes.append(base["nombre"] if base else "Producto eliminado")
                continue
            multiplicador = Decimal(str(componente.get("cantidad", 1)))
            for ingrediente in receta["ingredientes"]:
                insumo_id = ingrediente["insumo_id"]
                if insumo_id not in ingredientes:
                    ingredientes[insumo_id] = {
                        **ingrediente, "cantidad": Decimal(0), "subtotal": Decimal(0)
                    }
                cantidad = Decimal(str(ingrediente["cantidad"])) * multiplicador
                ingredientes[insumo_id]["cantidad"] += cantidad
                ingredientes[insumo_id]["subtotal"] += (
                    cantidad * Decimal(str(ingrediente["costo_unitario"] or 0))
                )
        detalle = sorted(ingredientes.values(), key=lambda i: i["nombre_insumo"].lower())
        resultados.append({
            "producto": producto["nombre"],
            "precio": producto["precio"],
            "precio_delivery": producto.get("precio_delivery"),
            "costo_total": sum((i["subtotal"] for i in detalle), Decimal(0)),
            "ingredientes": detalle,
            "costeo_incompleto": bool(faltantes) or not componentes,
            "productos_sin_receta": list(dict.fromkeys(faltantes)),
        })
    return sorted(resultados, key=lambda c: c["producto"].lower())
