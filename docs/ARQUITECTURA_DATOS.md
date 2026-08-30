# Arquitectura de datos compacta

`data/manifest.js` contiene las dimensiones: tiendas, categorías, ingredientes, cruces SAP, presentaciones y rutas. Cada tienda carga un único JSON bajo demanda.

El archivo de tienda se agrupa por semana. Cada arreglo plano repite tríos:

```text
[categoriaId, ingredienteId, usoIdealCentavos, ...]
```

Este diseño evita repetir nombres en 4.76 millones de filas. La app divide `usoIdealCentavos / 100` y promedia contra la cantidad total de semanas elegidas, incluyendo como cero una semana sin registro para ese ingrediente.

Las 954 tiendas están distribuidas en 12 carpetas de hasta 80 archivos. El service worker guarda únicamente las tiendas consultadas, evitando una instalación inicial masiva.

## Actualización semanal incremental

`tools/update_week.py` incorpora una semana nueva directamente sobre los JSON de tienda existentes. Antes de escribir valida:

- encabezados y codificación del CSV;
- número de semana en todas las filas;
- CeCo contra `Directorio.xlsx`;
- columna `Indicadores` vacía;
- `Uso Ideal* (#)` numérico;
- continuidad con la última semana publicada;
- máximo de 100 archivos y 25 MB por carpeta.

La operación actualiza el manifiesto, los JSON afectados y los reportes de auditoría. Con `--replace` sustituye exclusivamente una semana existente. El workflow `.github/workflows/update-week.yml` limita la entrada a `updates/incoming/` y retira el archivo fuente después de publicar los datos.

## Estrategia de caché

El shell de la aplicación utiliza caché local, mientras `data/manifest.js` y los archivos de tienda usan network-first con reintento. De esta forma, una semana nueva aparece sin obligar al usuario a borrar manualmente el caché y todavía existe una copia de respaldo si la red falla.
