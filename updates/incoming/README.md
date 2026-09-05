# Entrada semanal automática (semana 35 en adelante)

Carga aquí un único CSV o ZIP. GitHub ejecutará **Actualizar semana Max Min** automáticamente.
También puedes iniciarlo manualmente: si dejas vacíos los campos, detectará el archivo y la semana por el nombre.

Semana 35:

- Ruta preferida: `updates/incoming/Max & Min_35.csv`
- Si el CSV supera 24 MB: comprímelo como `updates/incoming/Max & Min_35.zip`.
- El ZIP debe contener exactamente `Max & Min_35.csv`.

Para semanas futuras conserva el mismo formato: `Max & Min_36.csv`, `Max & Min_37.csv`, etc.

Si la semana ya existe, se reemplaza completa y se recalcula; no se anexan filas sobre datos anteriores. El proceso rechaza claves CeCo/categoría/ingrediente duplicadas y, antes de publicar, compara el 100 % del CSV con los JSON generados.

Después del procesamiento exitoso, el workflow retira el archivo fuente para evitar acumulación. Los resultados quedan en `data/` y los controles en `audit/week_N_update_report.json` y `audit/week_N_publish_report.json`. El directorio vigente es autoritativo: las tiendas abiertas se muestran primero, los cierres temporales permanecen disponibles y los CeCo ajenos se reportan sin bloquear la carga.
