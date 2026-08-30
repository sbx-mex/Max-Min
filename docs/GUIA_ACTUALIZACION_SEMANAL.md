# Guía operativa · actualización semanal

## Semana 35

1. Carga `Max & Min_35.csv` en `updates/incoming/` sin cambiar sus encabezados.
2. Abre **Actions → Actualizar semana Max Min → Run workflow**.
3. Usa `week = 35`, la ruta mostrada y `replace = false`.
4. Cuando termine en verde, abre la aplicación: debe mostrar datos hasta la Semana 35.

Python valida primero y publica después. Los CeCo que no estén en el directorio vigente se excluyen y quedan registrados en `audit/week_35_update_report.json`; no detienen la actualización de las tiendas autorizadas.

## Semana 36 en adelante

Repite el mismo flujo cambiando únicamente el número del archivo, la ruta y el campo `week`. No subas CSV directamente a `data/` y no edites `manifest.js` manualmente.

## Corrección de una semana

Para sustituir una semana ya cargada, utiliza el mismo nombre y activa `replace = true`. El motor elimina exclusivamente esa semana de cada tienda y la vuelve a incorporar.

## Recuperación

Si el workflow falla, no publica datos parciales. Corrige el archivo fuente y vuelve a ejecutarlo. Los errores indican la fila y el motivo: Semana incorrecta, Indicadores con contenido o Uso Ideal no numérico.
