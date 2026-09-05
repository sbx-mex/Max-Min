# Parche controlado - Semana 35 y estabilidad

## Publicación

1. Extrae el ZIP y sube su contenido a la raíz de `sbx-mex/Max-Min`, conservando las carpetas.
2. Abre **Actions -> Actualizar semana Max Min -> Run workflow**.
3. Deja vacíos semana y ruta; el workflow detectará `updates/incoming/Max & Min_35.csv`, reemplazará la semana y retirará el CSV al terminar.

El caso de control `38996 · Valle de Aragón / Bagel Tradicional / Semana 35` debe quedar en `25.00` y será validado contra el CSV antes de publicar.

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

Desde la Semana 36 sólo carga un archivo como `updates/incoming/Max & Min_36.csv`. El workflow detecta la semana, reemplaza automáticamente una semana ya existente, recalcula, verifica contra el CSV y publica. No edites `data/manifest.js` ni los JSON manualmente.
