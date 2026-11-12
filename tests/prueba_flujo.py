"""Prueba local del flujo completo con releases de ejemplo (formato real ARCE)."""
import json, os, sys, shutil, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import common as cm

def rel(rid, cid, tag, fecha, tender=None, awards=None, buyer=("Intendencia de Canelones", "80-2")):
    r = {"ocid": f"ocds-yfs5dr-{cid}", "id": rid, "date": fecha, "tag": [tag],
         "buyer": {"name": buyer[0], "id": buyer[1]}}
    if tender: r["tender"] = tender
    if awards: r["awards"] = awards
    return r

def item(desc, cod, cant, precio=None, mon="UYU"):
    d = {"id": "1", "description": desc, "classification": {"id": cod, "description": desc},
         "quantity": cant, "unit": {"name": "UNIDAD", "id": "22"}}
    if precio is not None: d["unit"]["value"] = {"amount": precio, "currency": mon}
    return d

RELEASES = {
 "llamado-900001": [rel("llamado-900001", "900001", "tender", "2026-11-10T12:00:00Z", tender={
    "id": "900001", "title": "Licitación Abreviada 45/2026", "description": "Adquisición de contenedores de carga lateral",
    "status": "active", "procurementMethodDetails": "Licitación Abreviada",
    "items": [item("CONTENEDOR PARA RESIDUOS CARGA LATERAL 3200 LTS", "55123", 120)],
    "tenderPeriod": {"startDate": "2026-11-10T12:00:00Z", "endDate": "2026-12-05T13:00:00Z"},
    "documents": [{"url": "https://www.comprasestatales.gub.uy/Pliegos/pliego_900001.pdf", "title": "Pliego"}]})],
 "aclar_llamado-900001-0": [rel("aclar_llamado-900001-0", "900001", "tenderUpdate", "2026-11-11T10:00:00Z", tender={
    "id": "900001", "status": "active", "tenderPeriod": {"endDate": "2026-12-12T13:00:00Z"}})],
 "adjudicacion-900002": [rel("adjudicacion-900002", "900002", "award", "2026-11-09T10:00:00Z", buyer=("Intendencia de Maldonado", "80-10"), awards=[
    {"id": "R1", "status": "active", "date": "2026-11-08T00:00:00Z", "suppliers": [{"id": "R1", "name": "CAMIONES DEL SUR S A"}],
     "items": [item("CAMION RECOLECTOR COMPACTADOR CARGA TRASERA 19 M3", "60011", 2, 210000, "USD")]}])],
 "llamado-900003": [rel("llamado-900003", "900003", "tender", "2026-11-10T09:00:00Z", buyer=("Instituto de Higiene", "26-8"), tender={
    "id": "900003", "title": "Compra Directa 1/2026", "description": "Cabina PCR", "status": "active",
    "items": [item("CABINA DE PCR", "75959", 1)], "tenderPeriod": {"endDate": "2026-11-13T08:25:00Z"}})],
}
FEED = [{"release": k, "compra": v[0]["ocid"].split("-")[-1], "tipo": v[0]["tag"][0], "fecha": "Tue, 10 Nov 2026 10:00:00"} for k, v in RELEASES.items()]

tmp = tempfile.mkdtemp()
for n in ("ARCHIVO_COMPRAS", "ARCHIVO_META", "ARCHIVO_CODIGOS", "ARCHIVO_ESTADO"):
    setattr(cm, n, os.path.join(tmp, os.path.basename(getattr(cm, n))))
cm.leer_rss = lambda url=None: FEED
cm.bajar_release = lambda rid: RELEASES[rid]
import ingesta
ingesta.main()
datos = json.load(open(cm.ARCHIVO_COMPRAS))
for c in datos:
    print(c["id"], c["organismo"], c["categorias"], c["estado"], c["apertura"], len(c["eventos"]), "eventos",
          [(a["proveedor"], a["items"][0].get("total"), a["items"][0].get("moneda")) for a in c["adjudicaciones"]])
assert {c["id"] for c in datos} == {"900001", "900002"}, "debe ignorar la compra del Instituto de Higiene"
c1 = next(c for c in datos if c["id"] == "900001")
assert c1["apertura"] == "2026-12-12T13:00:00Z" and len(c1["eventos"]) == 2
# segunda corrida: no debe duplicar nada
ingesta.main()
assert len(json.load(open(cm.ARCHIVO_COMPRAS))) == 2
print(open(cm.ARCHIVO_CODIGOS).read())
shutil.copy(cm.ARCHIVO_COMPRAS, sys.argv[1]) if len(sys.argv) > 1 else None
print("OK")
