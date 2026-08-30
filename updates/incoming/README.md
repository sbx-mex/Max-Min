# Entrada semanal

Carga aquí un único archivo antes de ejecutar el workflow **Actualizar semana Max Min**.

Semana 35:

- Ruta preferida: `updates/incoming/Max & Min_35.csv`
- Si el CSV supera 24 MB: comprímelo como `updates/incoming/Max & Min_35.zip`.
- El ZIP debe contener exactamente `Max & Min_35.csv`.

Después del procesamiento exitoso, el workflow retira el archivo fuente para evitar acumulación. Los resultados quedan en `data/` y el control en `audit/week_35_update_report.json`.
