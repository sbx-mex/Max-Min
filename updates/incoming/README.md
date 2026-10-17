# Entrada semanal automática · semana 35 en adelante

Carga aquí uno o varios **CSV o ZIP**. Al guardar en `main`, Actions ejecuta **Actualizar semana Max Min** y procesa todas las fuentes pendientes en orden.

- Nombre recomendado: `Max & Min_35.csv`, `Max & Min_36.csv`, etc.
- Python determina la semana usando **todas las filas de la columna Semana**. Si el nombre difiere, avisa y respeta el contenido.
- Cada CSV debe contener una sola semana y conservar los encabezados originales.
- Límite: 25 MiB por archivo. Si un CSV es más grande, usa un ZIP con un solo CSV, de hasta 128 MiB descomprimido.
- Puedes cargar varias semanas juntas. Su tamaño combinado no bloquea la cola; los límites del sitio y de cada archivo se mantienen.
- Los duplicados idénticos se importan una sola vez. Dos contenidos distintos para la misma semana detienen el lote para evitar elegir una versión por accidente.
- Si falta una semana, se registra como pendiente. No se rellena con ceros ni se copia otra semana. Puedes cargarla después.
- Una semana ya publicada se reemplaza completa; nunca se acumulan sus filas dos veces.

Antes de publicar, se audita cada fuente, se verifica cada registro contra los JSON y se revisan los dos motores. Sólo entonces se retiran los CSV/ZIP procesados. Quedan reportes en `audit/week_*` y un resumen en Actions.

Para ejecutar manualmente, deja ambos campos vacíos y se procesará toda la cola. Usa `source_path` para elegir un archivo; `week` es opcional y debe coincidir con su contenido.
