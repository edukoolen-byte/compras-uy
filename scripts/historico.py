"""Carga histórica.
- Años cerrados: usa los ZIP anuales OCDS del Catálogo Nacional de Datos Abiertos.
- Año en curso (o años sin ZIP publicado): usa el RSS mensual de ARCE y baja
  cada movimiento (tarda más: puede llevar 30-90 minutos por año).

Uso:  python scripts/historico.py 2018-2025
      python scripts/historico.py 2026
      python scripts/historico.py 2026-11      (solo un mes)
"""
import io
import json
import os
import re
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as cm  # noqa: E402

CKAN_API = "https://catalogodatos.gub.uy/api/3/action/package_show?id=arce-datos-historicos-de-compras"
CKAN_PAGINA = "https://catalogodatos.gub.uy/dataset/arce-datos-historicos-de-compras"


def urls_zip():
    """{año: url} de los ZIP anuales publicados."""
    res = {}
    try:
        datos = json.loads(cm.descargar(CKAN_API))
        for r in datos["result"]["resources"]:
            url = r.get("url") or ""
            m = re.search(r"(20\d\d)", (r.get("name") or "") + " " + url)
            if url.lower().endswith(".zip") and m:
                res[int(m.group(1))] = url
    except Exception as e:  # noqa: BLE001
        print(f"API del catálogo no disponible ({e}); pruebo con la página web")
    if not res:
        html = cm.descargar(CKAN_PAGINA) or ""
        for url in set(re.findall(r'href="([^"]+?\.zip)"', html)):
            m = re.search(r"(20\d\d)", url)
            if m:
                res[int(m.group(1))] = url if url.startswith("http") else "https://catalogodatos.gub.uy" + url
    return res


def procesar_releases(rels, base, clasif):
    n = 0
    for rel in rels:
        cid = cm.id_compra(rel)
        if not cid:
            continue
        c = base.get(cid) or cm.compra_vacia(cid)
        cm.aplicar_release(c, rel)
        clasif.compra(c)
        if c["categorias"]:
            if cid not in base:
                n += 1
            base[cid] = c
    return n


def desde_zip(anio, url, base, clasif):
    print(f"{anio}: bajando {url}")
    contenido = cm.descargar(url, timeout=600, binario=True)
    z = zipfile.ZipFile(io.BytesIO(contenido))

    def orden(nombre):
        m = re.search(r"([la])-(\d\d)-(\d{4})", nombre)
        return (m.group(3), m.group(2), 0 if m.group(1) == "l" else 1) if m else ("9999", nombre, 9)

    total = 0
    for nombre in sorted((n for n in z.namelist() if n.endswith(".json")), key=orden):
        with z.open(nombre) as f:
            paquete = json.load(f)
        rels = paquete.get("releases", []) if isinstance(paquete, dict) else paquete
        nuevas = procesar_releases(rels, base, clasif)
        total += nuevas
        print(f"  {nombre}: {len(rels)} movimientos, {nuevas} compras nuevas del rubro")
    return total


def desde_rss(anio, meses, base, clasif):
    total = 0
    for mes in meses:
        items = cm.leer_rss(f"{cm.URL_RSS}/{anio}/{mes:02d}")
        items.sort(key=lambda x: _fecha_rss(x["fecha"]))
        print(f"{anio}-{mes:02d}: {len(items)} movimientos en el RSS mensual")
        # 1) llamados y adjudicaciones: se bajan todos para clasificar
        principales = [x for x in items if x["release"].startswith(("llamado-", "adjudicacion-"))]
        rels = _bajar_muchos([x["release"] for x in principales])
        total += procesar_releases(rels, base, clasif)
        # 2) resto de movimientos solo de compras que ya están en la base
        resto = [x for x in items if not x["release"].startswith(("llamado-", "adjudicacion-")) and x["compra"] in base]
        procesar_releases(_bajar_muchos([x["release"] for x in resto]), base, clasif)
        cm.guardar_base(base, clasif)  # guardado parcial por si se corta
        print(f"  compras del rubro en base: {len(base)}")
    return total


def _fecha_rss(s):
    try:
        return datetime.strptime(s, "%a, %d %b %Y %H:%M:%S")
    except ValueError:
        return datetime.min


def _bajar_muchos(ids):
    def uno(rid):
        try:
            return cm.bajar_release(rid)
        except Exception as e:  # noqa: BLE001
            print(f"  error {rid}: {e}")
            return []
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(uno, ids))
    return [r for lista in res for r in lista]


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "2018-2025"
    hoy = datetime.now(timezone.utc)
    solo_mes = None
    m =re.fullmatch(r"(\d{4})(?:-(\d{4}|\d{2}))?", arg.strip())
    if not m:
        sys.exit("Formato: 2018-2025, 2026 o 2026-11")
    desde = int(m.group(1))
    if m.group(2) and len(m.group(2)) == 2:
        hasta, solo_mes = desde, int(m.group(2))
    else:
        hasta = int(m.group(2)) if m.group(2) else desde

    clasif = cm.Clasificador()
    base = cm.cargar_base()
    zips = urls_zip()
    print(f"ZIP anuales disponibles: {sorted(zips)}")

    for anio in range(desde, hasta + 1):
        if solo_mes:
            desde_rss(anio, [solo_mes], base, clasif)
        elif anio in zips and anio < hoy.year:
            desde_zip(anio, zips[anio], base, clasif)
        else:
            ultimo = hoy.month if anio == hoy.year else 12
            print(f"{anio}: sin ZIP anual, uso el RSS mensual (enero a {ultimo:02d})")
            desde_rss(anio, range(1, ultimo + 1), base, clasif)
        cm.guardar_base(base, clasif)

    print(f"Listo. Compras de higiene urbana en base: {len(base)}")


if __name__ == "__main__":
    main()
