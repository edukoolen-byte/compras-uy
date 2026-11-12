# Monitor de compras estatales · Higiene urbana · Uruguay

Sigue automáticamente las compras del Estado uruguayo publicadas por ARCE y se queda solo con las de **higiene urbana**:

- contenedores
- camiones y equipos
- servicios de recolección y barrido
- transferencia de residuos
- tratamiento y disposición final
- residuos especiales/sanitarios

Qué hace:

- **Cada 2 horas** baja las novedades de ARCE (llamados, aclaraciones, prórrogas, adjudicaciones).
- Guarda el **histórico desde 2018**: quién compró, quién ganó, a qué precio.
- Publica una **página web** con llamados abiertos, adjudicaciones y precios, ranking de proveedores y organismos, y tu propio seguimiento.
- Te manda un **mail** cada vez que aparece un llamado o una adjudicación del rubro.

Todo corre gratis en GitHub. No hace falta tener la computadora prendida.

---

## Instalación (una sola vez, unos 20 minutos)

### 1. Crear la cuenta
Entrá a <https://github.com>, tocá **Sign up** y creá la cuenta con tu mail. Ese mail es donde te van a llegar las alertas.

### 2. Crear el repositorio
1. Arriba a la derecha: **+** → **New repository**.
2. **Repository name:** `compras-uy`.
3. Marcá **Public**. Es obligatorio para que la página web sea gratis; los datos son públicos de ARCE igual.
4. Tocá **Create repository**.

### 3. Subir los archivos
1. Descomprimí el ZIP en tu computadora.
2. En la página del repositorio recién creado, tocá el link **uploading an existing file**.
3. Abrí la carpeta `compras-uy` descomprimida, seleccioná **todo su contenido** y arrastralo a la página. Tienen que quedar las carpetas `.github`, `config`, `docs`, `scripts`, `tests` y los archivos sueltos.
4. Abajo, tocá **Commit changes**.

> **Si la carpeta `.github` no aparece**, es porque Windows o Mac la oculta por empezar con punto. En ese caso:
> 1. Tocá **Add file → Create new file**.
> 2. En el nombre escribí `.github/workflows/actualizar.yml`.
> 3. Pegá el contenido de ese archivo y guardá.
> 4. Repetí lo mismo con `.github/workflows/historico.yml`.

### 4. Dar permisos
1. Dentro del repositorio: **Settings → Actions → General**.
2. Abajo de todo, en **Workflow permissions**, marcá **Read and write permissions** y guardá.

### 5. Activar la página web
1. **Settings → Pages**.
2. En **Source** elegí **GitHub Actions**.

### 6. Cargar el histórico
1. Pestaña **Actions**. Si pregunta, tocá **I understand… enable them**.
2. A la izquierda, elegí **Carga historica** → **Run workflow**.
3. Dejá `2018-2025` y tocá **Run workflow**. Tarda entre 15 y 40 minutos.
4. Cuando termine (tilde verde), corré de nuevo **Carga historica** con `2026`. El año en curso no tiene archivo anual todavía, así que se baja mes a mes y puede tardar 1–2 horas.

### 7. Listo
- En **Actions**, al abrir la última corrida de **Actualizar compras**, aparece el link de tu página. También está en **Settings → Pages**. Tiene la forma `https://TU-USUARIO.github.io/compras-uy/`. Guardala en favoritos o en la pantalla de inicio del celular.
- A partir de ahora se actualiza sola cada 2 horas.

---

## Uso de la página

| Pestaña | Para qué |
|---|---|
| **Llamados abiertos** | Lo que está recibiendo ofertas, ordenado por fecha de apertura, con los días que faltan. |
| **Todas las compras** | El buscador completo, con filtros por rubro, organismo y año. |
| **Adjudicaciones y precios** | Cada ítem adjudicado con proveedor, cantidad, precio unitario y total. Sirve para armar precios de referencia. |
| **Proveedores** | Ranking de competidores: cuántas adjudicaciones, a qué organismos y por cuánto. Tocá uno para ver todas sus compras. |
| **Organismos** | Quién compra más del rubro (intendencias, entes, etc.). |
| **Mi seguimiento** | Las compras que marcaste: para analizar, cotizando, presentada, ganada, perdida. |

- Tocá cualquier fila para ver el detalle: ítems, adjudicaciones, historial completo, link a ARCE y al pliego.
- El botón **Descargar Excel (CSV)** baja exactamente lo que estás viendo.
- **Mi seguimiento** y las notas se guardan en el navegador donde las cargás. No se comparten entre la PC y el celular.

## Alertas por mail

Cada novedad del rubro crea un "issue" en el repositorio y GitHub te manda un mail automáticamente. Se ven todas en la pestaña **Issues**; cerralas cuando ya las viste.

- Si no te llegan, revisá en <https://github.com/settings/notifications> que **Email** esté activado para "Participating, @mentions and custom" y "Watching".
- Para apagarlas, en `config/rubros.json` cambiá `"activas": true` por `false`.

## Afinar qué se considera "higiene urbana"

Las reglas están en `config/rubros.json`. Para editarlo, abrí el archivo en GitHub y tocá el lápiz.

- **`incluir`:** palabras o frases que hacen que un ítem entre en el rubro. Se comparan en minúsculas y sin tildes.
- **`excluir`:** frases que lo sacan. Por ejemplo, "placa compactadora" es maquinaria vial, no de residuos.
- **`codigos`:** códigos del catálogo de ARCE que entran siempre. En `docs/data/codigos.json` ves qué códigos aparecieron y cuántas veces, para sumarlos.
- La categoría **"Otros con residuos (revisar)"** atrapa lo que menciona residuos pero no encaja en las demás. Sirve para descubrir cosas nuevas y no genera alertas.

Las reglas nuevas se aplican a lo que entra desde ese momento. Para reclasificar el pasado, corré otra vez **Carga historica**.

## Qué conviene saber

- **Fuente:** datos abiertos de ARCE en formato OCDS.
  - Feed RSS: `comprasestatales.gub.uy/ocds/rss`.
  - Histórico anual: Catálogo Nacional de Datos Abiertos.
- Los **montos** son los que publica ARCE (precio unitario × cantidad), separados por moneda. Algunas adjudicaciones no informan precio.
- El feed de ARCE muestra los últimos 500 movimientos, que son aproximadamente 1,5 días. Si el monitor estuvo parado más tiempo, corré **Carga historica** con el mes, por ejemplo `2026-11`, para completar el hueco.
- En repositorios públicos, GitHub pausa las tareas programadas después de 60 días sin actividad. Si pasa, te avisa por mail y se reactiva con un clic en **Actions**.

## Estructura

```
config/rubros.json      reglas de clasificación y alertas
scripts/ingesta.py      actualización periódica (RSS de ARCE)
scripts/historico.py    carga histórica (ZIP anuales + RSS mensual)
scripts/alertas.py      issues/mails
docs/index.html         la página web
docs/data/              datos publicados (compras.json, meta.json, codigos.json)
.github/workflows/      tareas programadas de GitHub
tests/                  pruebas locales con datos de ejemplo
```
