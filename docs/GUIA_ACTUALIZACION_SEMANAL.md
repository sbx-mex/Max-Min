# Carga semanal segura · Max-Min

1. Sube uno o varios CSV/ZIP a `updates/incoming/`.
2. Guarda los cambios en `main`. No necesitas indicar una semana manualmente.
3. Abre **Actions → Actualizar semana Max Min** para ver las semanas verificadas y las pendientes.

La semana se obtiene del contenido del CSV. Se permiten cargas desde la 35 en adelante, incluso cuando llegan fuera de orden. Una semana ausente no participa en los filtros ni en el promedio; al recibirla se incorpora con sus datos reales.

Si dos archivos son idénticos, se importan una sola vez. Si contienen versiones diferentes de la misma semana, conserva en incoming únicamente la que deseas publicar y vuelve a ejecutar.

La validación y los cambios se hacen primero en una copia. Si una fuente falla, el motor original y las cargas permanecen disponibles. Una semana ya existente se sustituye completa. Se cotejan todos sus registros, no una muestra.

Los CeCo fuera del Directorio.xlsx vigente se excluyen y se detallan en el reporte, sin asignarles nombres ni almacenes inventados. Indicadores debe permanecer vacío. Uso Ideal debe ser numérico, finito y no negativo.

Los límites se aplican por archivo, con protección adicional al descomprimir ZIP. Los límites de las carpetas de datos publicados siguen activos.

Si llega una carga mientras se valida otra, el publicador vuelve a descargar main y recalcula. No fuerza el push ni combina JSON generados sobre versiones distintas.

Reportes: `audit/week_queue_report.json`, `audit/week_NUM_source_report.json`, `audit/week_NUM_update_report.json` y `audit/week_NUM_publish_report.json`.

La misma ejecución despliega en Pages el sitio verificado, sin incluir las fuentes CSV/Excel ni los reportes internos. No depende de que un commit del bot dispare otro despliegue.
