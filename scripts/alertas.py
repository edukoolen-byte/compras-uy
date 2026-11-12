"""Alertas: crea un 'issue' en GitHub por cada novedad relevante.
GitHub le manda automáticamente un mail al dueño del repositorio."""
import os

import requests

ETIQUETA = {
    "tender": "Nuevo llamado",
    "award": "Adjudicación",
    "tenderCancellation": "Llamado cancelado",
}


def _fmt_fecha(iso):
    if not iso:
        return "-"
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]} {iso[11:16]}".strip()


def _cuerpo(tag, c):
    lineas = [
        f"**Organismo:** {c['organismo']}",
        f"**Procedimiento:** {c['titulo']} ({c['tipo'] or '-'})",
        f"**Objeto:** {c['descripcion'] or '-'}",
        f"**Rubros:** {', '.join(c['categorias'])}",
        f"**Apertura:** {_fmt_fecha(c.get('apertura'))} (UTC)",
        "",
        "**Ítems:**",
    ]
    for it in c["items"][:15]:
        lineas.append(f"- {it['desc']} — {it.get('cant') or ''} {it.get('unidad') or ''}")
    if tag == "award":
        lineas.append("")
        lineas.append("**Adjudicado a:**")
        for a in c["adjudicaciones"]:
            totales = {}
            for it in a["items"]:
                if it.get("total") is not None:
                    totales[it.get("moneda") or "?"] = totales.get(it.get("moneda") or "?", 0) + it["total"]
            tot = ", ".join(f"{m} {v:,.0f}" for m, v in totales.items()) or "monto no informado"
            lineas.append(f"- {a['proveedor']}: {tot}")
    lineas += ["", f"[Ver en ARCE]({c['url']})"]
    for d in c.get("documentos", [])[:3]:
        lineas.append(f"[{d['titulo']}]({d['url']})")
    return "\n".join(lineas)


def enviar(eventos, cfg):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not cfg.get("activas", True) or not token or not repo:
        print("Alertas desactivadas o sin credenciales (normal si se corre en forma local).")
        return
    permitidas = set(cfg.get("categorias", []))
    maximo = int(cfg.get("maximo_por_corrida", 15))

    unicos = {}
    for tag, c in eventos:
        if not set(c["categorias"]) & permitidas:
            continue
        clave = (c["id"], tag if tag in ETIQUETA else "otro")
        if clave[1] == "otro":
            continue
        unicos[clave] = (tag, c)

    pendientes = list(unicos.values())
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    url = f"https://api.github.com/repos/{repo}/issues"
    for tag, c in pendientes[:maximo]:
        titulo = f"{ETIQUETA[tag]}: {c['organismo']} — {(c['descripcion'] or c['titulo'])[:90]}"
        r = s.post(url, json={"title": titulo, "body": _cuerpo(tag, c), "labels": [ETIQUETA[tag]]})
        print(f"Alerta '{titulo}': {r.status_code}")
    if len(pendientes) > maximo:
        resto = "\n".join(f"- {ETIQUETA[t]}: {c['organismo']} — {c['descripcion'][:80]} ({c['url']})"
                          for t, c in pendientes[maximo:])
        s.post(url, json={"title": f"{len(pendientes) - maximo} novedades más de higiene urbana",
                          "body": resto})
