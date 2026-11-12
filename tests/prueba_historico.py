"""Prueba de la carga histórica desde un ZIP anual simulado."""
import io, json, os, sys, tempfile, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(__file__))
import common as cm
import historico
from prueba_flujo import RELEASES  # reutiliza los releases de ejemplo

tmp = tempfile.mkdtemp()
for n in ("ARCHIVO_COMPRAS", "ARCHIVO_META", "ARCHIVO_CODIGOS", "ARCHIVO_ESTADO"):
    setattr(cm, n, os.path.join(tmp, os.path.basename(getattr(cm, n))))
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    ll = [r for k, v in RELEASES.items() if k.startswith(("llamado", "aclar")) for r in v]
    aa = [r for k, v in RELEASES.items() if k.startswith("adjud") for r in v]
    z.writestr("ocds-2020/l-01-2020.json", json.dumps({"releases": ll}))
    z.writestr("ocds-2020/a-01-2020.json", json.dumps({"releases": aa}))
historico.urls_zip = lambda: {2020: "http://x/ocds-2020.zip"}
cm.descargar = lambda url, **k: buf.getvalue()
sys.argv = ["historico.py", "2020"]
historico.main()
datos = json.load(open(cm.ARCHIVO_COMPRAS))
assert {c["id"] for c in datos} == {"900001", "900002"}, datos
import alertas
print(alertas._cuerpo("award", next(c for c in datos if c["id"] == "900002")))
print("OK")
