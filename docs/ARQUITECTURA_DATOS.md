# Arquitectura de datos compacta

`data/manifest.js` contiene las dimensiones: tiendas, categorías, ingredientes, cruces SAP, presentaciones y rutas. Cada tienda carga un único JSON bajo demanda.

El archivo de tienda se agrupa por semana. Cada arreglo plano repite tríos:

```text
[categoriaId, ingredienteId, usoIdealCentavos, ...]
```

Este diseño evita repetir nombres en 4.76 millones de filas. La app divide `usoIdealCentavos / 100` y promedia contra la cantidad total de semanas elegidas, incluyendo como cero una semana sin registro para ese ingrediente.

Las 954 tiendas están distribuidas en 12 carpetas de hasta 80 archivos. El service worker guarda únicamente las tiendas consultadas, evitando una instalación inicial masiva.
