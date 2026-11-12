"""Funciones compartidas: descarga, lectura de releases OCDS de ARCE,
clasificación por rubro y base de datos (archivos JSON)."""
import json
import os
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVO_COMPRAS = os.path.join(RAIZ, "docs", "data", "compras.json")
ARCHIVO_META = os.path.join(RAIZ, "docs", "data", "meta.json")
ARCHIVO_CODIGOS = os.path.join(RAIZ, "docs", "data", "codigos.json")
ARCHIVO_ESTADO = os.path.join(RAIZ, "data", "estado.json")
ARCHIVO_RUBROS = os.path.join(RAIZ, "config", "rubros.json")

BASE = "http://www.comprasestatales.gub.uy"
URL_RSS = BASE + "/ocds/rss"
URL_RELEASE = BASE + "/ocds/release/{}"
URL_DETALLE = "https://www.comprasestatales.gub.uy/consultas/detalle/id/{}"

SESION = requests.Session()
SESION.headers["User-Agent"] = "monitor-compras-higiene-urbana/1.0 (uso personal)"


# ---------------------------------------------------------------- red
def descargar(url, intentos=4, timeout=60, binario=False):
    ultimo = None
    for i in range(intentos):
        try:
            r = SESION.get(url, timeout=timeout)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content if binario else r.text
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"No se pudo descargar {url}: {ultimo}")


def leer_rss(url=URL_RSS):
    """Devuelve lista de (release_id, id_compra, categoria, fecha) del feed."""
    texto = descargar(url, timeout=180)
    if not texto:
        return []
    raiz = ET.fromstring(texto.encode("utf-8") if isinstance(texto, str) else texto)
    salida = []
    for it in raiz.iter("item"):
        guid = (it.findtext("guid") or "").strip()
        titulo = it.findtext("title") or ""
        m = re.search(r"id_compra:(\d+)", titulo)
        salida.append({
            "release": guid,
            "compra": m.group(1) if m else None,
            "tipo": (it.findtext("category") or "").strip(),
            "fecha": (it.findtext("pubDate") or "").strip(),
        })
    return salida


def bajar_release(release_id):
    texto = descargar(URL_RELEASE.format(release_id))
    if not texto:
        return []
    paquete = json.loads(texto)
    return paquete.get("releases", [])


# ---------------------------------------------------------------- texto
def normalizar(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.lower()).strip()


class Clasificador:
    def __init__(self, ruta=ARCHIVO_RUBROS):
        with open(ruta, encoding="utf-8") as f:
            self.config = json.load(f)
        self.cats = []
        for c in self.config["categorias"]:
            self.cats.append({
                "id": c["id"],
                "inc": [re.compile(p) for p in c.get("incluir", [])],
                "exc": [re.compile(p) for p in c.get("excluir", [])],
                "codigos": {str(x) for x in c.get("codigos", [])},
                "residual": c.get("solo_si_no_hay_otra", False),
            })

    def texto(self, texto, codigo=None):
        """Categorías que aplican a un texto (y opcionalmente un código)."""
        n = normalizar(texto)
        encontradas = []
        for c in self.cats:
            if c["residual"]:
                continue
            if self._aplica(c, n, codigo):
                encontradas.append(c["id"])
        if not encontradas:
            for c in self.cats:
                if c["residual"] and self._aplica(c, n, codigo):
                    encontradas.append(c["id"])
        return encontradas

    @staticmethod
    def _aplica(c, n, codigo):
        if codigo is not None and str(codigo) in c["codigos"]:
            return True
        if any(p.search(n) for p in c["exc"]):
            return False
        return any(p.search(n) for p in c["inc"])

    def compra(self, c):
        """Clasifica una compra completa. Marca cada ítem y devuelve categorías."""
        cats = set()
        for it in c.get("items", []):
            it["cat"] = self.texto(it.get("desc", ""), it.get("cod"))
            cats.update(it["cat"])
        for a in c.get("adjudicaciones", []):
            for it in a.get("items", []):
                it["cat"] = self.texto(it.get("desc", ""), it.get("cod"))
                cats.update(it["cat"])
        cats.update(self.texto(c.get("descripcion", "")))
        # "otros" solo si no hay otra categoría más específica
        if len(cats) > 1:
            cats.discard("otros")
        orden = [x["id"] for x in self.cats]
        c["categorias"] = [x for x in orden if x in cats]
        return c["categorias"]


# ---------------------------------------------------------------- releases
TIPOS = {
    "tender": "Llamado",
    "tenderUpdate": "Aclaración",
    "tenderAmendment": "Ajuste del llamado",
    "tenderCancellation": "Cancelación",
    "award": "Adjudicación",
    "awardUpdate": "Ajuste de adjudicación",
}


def id_compra(rel):
    ocid = rel.get("ocid") or ""
    return ocid.rsplit("-", 1)[-1] if ocid else None


def _item(it):
    unidad = it.get("unit") or {}
    valor = unidad.get("value") or {}
    cls = it.get("classification") or {}
    d = {
        "desc": (it.get("description") or cls.get("description") or "").strip(),
        "cod": cls.get("id"),
        "cant": it.get("quantity"),
        "unidad": unidad.get("name"),
    }
    if valor.get("amount") is not None:
        d["precio"] = valor.get("amount")
        d["moneda"] = valor.get("currency")
        try:
            d["total"] = round(float(valor["amount"]) * float(it.get("quantity") or 1), 2)
        except (TypeError, ValueError):
            pass
    return d


def compra_vacia(cid):
    return {
        "id": cid, "titulo": "", "descripcion": "", "organismo": "", "organismo_id": "",
        "tipo": "", "estado": "", "publicado": None, "apertura": None,
        "items": [], "adjudicaciones": [], "documentos": [], "eventos": [],
        "categorias": [], "url": URL_DETALLE.format(cid),
    }


def aplicar_release(c, rel):
    """Incorpora un release OCDS a la compra c (dict). Devuelve True si cambió algo."""
    rid = rel.get("id")
    tag = (rel.get("tag") or [""])[0]
    fecha = rel.get("date")
    if any(e["release"] == rid for e in c["eventos"]):
        return False
    c["eventos"].append({"release": rid, "tipo": tag, "fecha": fecha})
    c["eventos"].sort(key=lambda e: e.get("fecha") or "")

    comprador = rel.get("buyer") or {}
    if comprador.get("name"):
        c["organismo"] = comprador["name"].strip()
        c["organismo_id"] = comprador.get("id", "")

    t = rel.get("tender")
    if t:
        c["titulo"] = t.get("title") or c["titulo"]
        c["descripcion"] = (t.get("description") or c["descripcion"] or "").strip()
        c["tipo"] = t.get("procurementMethodDetails") or c["tipo"]
        if t.get("status"):
            c["estado"] = t["status"]
        if t.get("items"):
            c["items"] = [_item(i) for i in t["items"]]
        periodo = t.get("tenderPeriod") or {}
        if periodo.get("endDate"):
            c["apertura"] = periodo["endDate"]
        if tag == "tender" and not c["publicado"]:
            c["publicado"] = periodo.get("startDate") or fecha
        docs = t.get("documents") or []
        for d in docs:
            url = d.get("url")
            if url and all(x["url"] != url for x in c["documentos"]):
                c["documentos"].append({"url": url, "titulo": d.get("title") or d.get("documentType") or "Documento"})
    if tag == "tenderCancellation":
        c["estado"] = "cancelled"

    for a in rel.get("awards") or []:
        sup = (a.get("suppliers") or [{}])[0]
        adj = {
            "id": a.get("id"),
            "fecha": a.get("date") or fecha,
            "estado": a.get("status"),
            "proveedor": (sup.get("name") or "").strip(),
            "proveedor_id": sup.get("id"),
            "items": [_item(i) for i in a.get("items") or []],
            "release": rid,
        }
        c["adjudicaciones"] = [x for x in c["adjudicaciones"] if x.get("id") != adj["id"]]
        c["adjudicaciones"].append(adj)
        if tag == "award" and c["estado"] in ("", "active"):
            c["estado"] = "awarded"
    if not c["publicado"]:
        c["publicado"] = fecha
    return True


# ---------------------------------------------------------------- base
def cargar_json(ruta, defecto):
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return defecto


def guardar_json(ruta, datos, compacto=False):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if compacto:
            json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def cargar_base():
    lista = cargar_json(ARCHIVO_COMPRAS, [])
    return {c["id"]: c for c in lista}


def guardar_base(base, clasif, nota=""):
    lista = sorted(base.values(), key=lambda c: c.get("publicado") or "", reverse=True)
    guardar_json(ARCHIVO_COMPRAS, lista, compacto=True)
    # resumen de códigos de catálogo encontrados, para afinar reglas
    cods = {}
    for c in lista:
        for it in c["items"] + [i for a in c["adjudicaciones"] for i in a["items"]]:
            if not it.get("cod") or not it.get("cat"):
                continue
            k = str(it["cod"])
            x = cods.setdefault(k, {"cod": k, "desc": it["desc"], "veces": 0, "cat": set()})
            x["veces"] += 1
            x["cat"].update(it["cat"])
    codigos = sorted(({**v, "cat": sorted(v["cat"])} for v in cods.values()), key=lambda v: -v["veces"])
    guardar_json(ARCHIVO_CODIGOS, codigos)
    meta = cargar_json(ARCHIVO_META, {})
    meta.update({
        "actualizado": ahora_iso(),
        "compras": len(lista),
        "categorias": [{"id": c["id"], "nombre": c["nombre"]} for c in clasif.config["categorias"]],
    })
    if nota:
        meta["nota"] = nota
    guardar_json(ARCHIVO_META, meta)


def ahora_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
