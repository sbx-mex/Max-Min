# Parche UI limpia · exportación guiada

## Archivos para reemplazar

- `index.html`
- `css/styles.css`
- `js/app.js`
- `sw.js`
- `tools/audit_project.py`

## Archivos nuevos

- `assets/ui/Damos_Seguimiento.webp`
- `assets/ui/Un_placer_haber_Ayudado.webp`

## Cambios visibles

- Se oculta el bloque promocional superior.
- Se elimina la fórmula explicativa y las cuatro tarjetas métricas duplicadas.
- El encabezado conserva sólo el icono, las tres pestañas y las acciones.
- Antes de descargar se muestra `Damos_Seguimiento.webp` con tienda, semanas, etiquetas y hojas.
- Después de descargar se muestra `Un_placer_haber_Ayudado.webp`.
- Se agrega un pie discreto de Sistema de Evidencias OPS.
- Los dos recursos quedan disponibles sin conexión mediante el service worker.

## Publicación segura

1. Sube los archivos indicados respetando sus rutas.
2. Espera **Validar Max Min Remaster**.
3. Recarga la aplicación una vez para activar el caché `v6`.
4. Selecciona al menos una etiqueta y comprueba el flujo: confirmar → exportar → cerrar.

Este parche no modifica datos, fórmulas MIN/MAX, cruces SAP, formatos ni generación multipágina.
