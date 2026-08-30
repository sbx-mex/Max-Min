# Guía operativa · actualización semanal

## Semana 35

1. Confirma que el archivo se llame `Max & Min_35.csv` y conserve estos encabezados: `Semana`, `Tiendas`, `Categoría Inventario`, `Ingrediente`, `Indicadores`, `Uso Ideal* (#)`.
2. Cárgalo en `updates/incoming/Max & Min_35.csv`. Si pesa más de 24 MB, carga `updates/incoming/Max & Min_35.zip` con el CSV dentro.
3. Abre **Actions → Actualizar semana Max Min → Run workflow**.
4. Captura `week = 35` y la ruta exacta del archivo. Mantén `replace = false` para una semana nueva.
5. Espera el resultado verde. El proceso valida CeCo, semana, encabezados, Indicadores vacíos, límites de archivos y continuidad histórica.
6. Revisa `audit/week_35_update_report.json` y abre la aplicación. El estado debe mostrar `Datos hasta Sem 35`.

## Semana 36 en adelante

Repite el mismo flujo cambiando únicamente el número del archivo, la ruta y el campo `week`. No subas CSV directamente a `data/` y no edites `manifest.js` manualmente.

## Corrección de una semana

Para sustituir una semana ya cargada, utiliza el mismo nombre y activa `replace = true`. El motor elimina exclusivamente esa semana de cada tienda y la vuelve a incorporar.

## Recuperación

Si el workflow falla, no publica datos parciales. Corrige el archivo fuente y vuelve a ejecutarlo. Los errores indican la fila y el motivo: CeCo inexistente, Semana incorrecta, Indicadores con contenido o Uso Ideal no numérico.
