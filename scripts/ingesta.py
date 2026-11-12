"""Ingesta periódica: lee el RSS de ARCE, baja los movimientos nuevos,
filtra los de higiene urbana, actualiza la base y crea alertas (issues)."""
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as cm  # noqa: E402
import alertas  # noqa: E402

PRINCIPALES = ("llamado-", "adjudicacion-")


def main():
    clasif = cm.Clasificador()
    base = cm.cargar_base()
    estado = cm.cargar_json(cm.ARCHIVO_ESTADO, {"vistos": []})
    vistos = set(estado["vistos"])

    feed = cm.leer_rss()
    nuevos = [x for x in feed if x["release"] and x["release"] not in vistos]
    print(f"Feed: {len(feed)} movimientos, {len(nuevos)} nuevos")
    if feed and not any(x["release"] in vistos for x in feed) and vistos:
        print("AVISO: ningún movimiento del feed estaba visto; puede haber un hueco. "
              "Corré 'Carga histórica' del mes en curso para completarlo.")

    # Los llamados y adjudicaciones se bajan siempre (para clasificarlos).
    # Aclaraciones/ajustes solo si la compra ya está en seguimiento.
    eventos_alerta = []
    fallidos = set()
    principales = [x for x in nuevos if x["release"].startswith(PRINCIPALES)]
    _procesar(principales, base, clasif, eventos_alerta, fallidos)
    secundarios = [x for x in nuevos if not x["release"].startswith(PRINCIPALES) and x["compra"] in base]
    _procesar(secundarios, base, clasif, eventos_alerta, fallidos)
    if fallidos:
        print(f"{len(fallidos)} movimientos no se pudieron bajar; se reintentan en la próxima corrida")

    # guardamos solo los últimos ~20000 ids vistos (sin los que fallaron)
    del_feed = [x["release"] for x in feed if x["release"] and x["release"] not in fallidos]
    s = set(del_feed)
    estado["vistos"] = (del_feed + [v for v in estado["vistos"] if v not in s])[:20000]
    cm.guardar_json(cm.ARCHIVO_ESTADO, estado)
    cm.guardar_base(base, clasif)
    print(f"Base: {len(base)} compras de higiene urbana. Eventos relevantes: {len(eventos_alerta)}")

    alertas.enviar(eventos_alerta, clasif.config.get("alertas", {}))


def _procesar(lista, base, clasif, eventos_alerta, fallidos):
    with ThreadPoolExecutor(max_workers=6) as ex:
        resultados = list(ex.map(lambda x: (x, _seguro(x["release"])), lista))
    fallidos.update(x["release"] for x, rels in resultados if rels is None)
    for x, rels in sorted(resultados, key=lambda r: r[0]["fecha"]):
        for rel in rels or []:
            cid = cm.id_compra(rel)
            if not cid:
                continue
            existente = cid in base
            c = base.get(cid) or cm.compra_vacia(cid)
            cats_antes = set(c.get("categorias", []))
            if not cm.aplicar_release(c, rel):
                continue  # ya lo teníamos (por ejemplo, de la carga histórica)
            clasif.compra(c)
            if not c["categorias"]:
                continue
            base[cid] = c
            tag = (rel.get("tag") or [""])[0]
            if tag in ("tender", "award", "tenderCancellation") or (not existente) or (set(c["categorias"]) - cats_antes):
                eventos_alerta.append((tag, c))


def _seguro(rid):
    try:
        return cm.bajar_release(rid)
    except Exception as e:  # noqa: BLE001
        print(f"  error en {rid}: {e}")
        return None


if __name__ == "__main__":
    main()
