# Actualización controlada · estabilidad y Semana 35

Este paquete contiene sólo los archivos que deben reemplazarse o agregarse. No vuelve a cargar las 954 tiendas ni modifica las semanas 1-34.

## 1. Reemplazar o agregar respetando las rutas

- `.github/workflows/validate.yml`
- `.github/workflows/cleanup-obsolete.yml`
- `.github/workflows/update-week.yml`
- `index.html`
- `css/styles.css`
- `js/app.js`
- `sw.js`
- `tools/build_data.py`
- `tools/update_week.py`
- `tools/cleanup_obsolete.py`
- `tools/audit_project.py`
- `tools/audit_pdf_export.py`
- `tools/prepare_pdf_release.py`
- `tools/generate_pdf_sample.cjs`
- `README.md`
- `docs/PLAN_10_MEJORAS.md`
- `docs/GUIA_ACTUALIZACION_SEMANAL.md`
- `docs/ARQUITECTURA_DATOS.md`
- `updates/incoming/README.md`

Los archivos de `audit/` y `output/pdf/` son evidencias de control y una muestra operativa; no son necesarios para que la app cargue.

## 2. Resolver la Action roja actual

1. Sube este parche manteniendo su estructura de carpetas.
2. Abre **Actions → Limpiar motores obsoletos → Run workflow**.
3. El workflow eliminará exclusivamente los 17 archivos enumerados en `BORRAR_EN_GITHUB.txt`.
4. Confirma que **Validar Max Min Remaster** termine en verde.

El error actual no proviene de los datos: `cleanup_obsolete.py` está funcionando como barrera y detectó restos del motor anterior.

## 3. Incorporar Semana 35

1. Sube `Max & Min_35.csv` a `updates/incoming/Max & Min_35.csv`.
2. Abre **Actions → Actualizar semana Max Min → Run workflow**.
3. Usa `week = 35`, `source_path = updates/incoming/Max & Min_35.csv` y `replace = false`.
4. Revisa `audit/week_35_update_report.json` y confirma que la app muestre `Datos hasta Sem 35`.

Si el CSV supera 24 MB, usa `updates/incoming/Max & Min_35.zip` y captura esa misma ruta en el workflow.

## 4. Regla para semanas posteriores

No edites `data/manifest.js` ni los JSON manualmente. Para Semana 36 y siguientes sólo cambia el número del archivo, la ruta y el campo `week` del workflow.

## Validación ejecutada

- Proyecto: correcto; semanas 1-34 continuas.
- Datos: 954 tiendas y 4,764,428 registros positivos.
- Límites: hasta 80 archivos por carpeta y menos de 25 MB.
- Prueba incremental: Semana 35 sintética incorporada sin alterar 1-34.
- Prueba de reemplazo: Semana 34 real reemplazada con total exacto.
- PDF: Carta horizontal, 4 × 3, 15 etiquetas en 2 hojas, encabezado repetido.
