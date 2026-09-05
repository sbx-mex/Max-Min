# Max-Min - aplicar ahora

1. Sube el contenido de este paquete a la raíz del repositorio, conservando las rutas.
2. En GitHub abre **Actions -> Actualizar semana Max Min -> Run workflow**.
3. Deja vacíos los campos: el proceso detectará y recalculará la Semana 35 automáticamente.

El workflow queda corregido para cargas futuras: detecta el CSV, inserta o reemplaza la semana completa, verifica la publicación y retira la fuente procesada.

Para Semana 36 en adelante sólo carga `updates/incoming/Max & Min_36.csv` (y así sucesivamente). No necesitas indicar `replace`.
