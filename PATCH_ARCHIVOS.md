# Parche controlado - Semana 35 y estabilidad

## Publicación en tres pasos

1. Extrae el ZIP y sube su contenido a la raíz de `sbx-mex/Max-Min`, conservando las carpetas.
2. Abre **Actions -> Actualizar semana Max Min -> Run workflow**.
3. Mantén `week = 35`, `source_path = updates/incoming/Max & Min_35.csv` y `replace = false`.

Ese único workflow elimina los 17 restos del motor anterior, audita el CSV, sincroniza el directorio vigente, incorpora la Semana 35, verifica JavaScript/Python y publica los datos.

## Directorio vigente

- 952 tiendas autorizadas.
- 942 abiertas, ordenadas primero en el selector.
- 10 cierres temporales, disponibles con distintivo discreto.
- Los CeCo ajenos al directorio se excluyen y quedan documentados sin bloquear la carga.

## Resultado esperado

- `Validar Max Min Remaster` termina en verde.
- La aplicación muestra semanas 1-35.
- El selector de CeCo permite búsqueda ágil y una sola selección.
- La exportación conserva Carta horizontal, 4 filas x 3 columnas y páginas adicionales seguras.
- `audit/week_35_update_report.json` conserva la trazabilidad de tiendas y filas excluidas.

## Semanas siguientes

Desde la Semana 36 sólo carga `updates/incoming/Max & Min_36.csv` y ejecuta el mismo workflow cambiando `week` y `source_path`. No edites `data/manifest.js` ni los JSON manualmente.
