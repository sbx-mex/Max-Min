# Max & Min 4.0 · Remaster

Aplicación estática/PWA para validar uso ideal, formato de surtido y etiquetas MIN/MAX por CeCo. La versión conserva las tres pestañas, elimina el menú lateral y reemplaza el motor pesado anterior por carga bajo demanda por tienda.

## Resultado operativo

- Directorio: cruce `CeCo → Tienda` desde `sources/Directorio.xlsx`.
- Datos: semanas 1-34, 954 tiendas con información, 701 ingredientes y 4,764,428 registros positivos.
- SAP: `Ingrediente → Catálogo Micros → Código DIA → Descripción SAP` desde `sources/Lista_Precios_Base.xlsx`.
- Indicadores: la fuente mantiene la columna vacía; no se inventa información.
- Uso ideal: promedio aritmético entre todas las semanas seleccionadas. El mínimo es `promedio / 7`.
- Máximo: 2 pedidos `×5`, 3 `×4`, 4 `×3`, 5 `×2`.
- Formato: Unidad o Pick Pack, con factor heredado del proyecto anterior y ajustes locales por ingrediente.
- PDF: Carta horizontal, 4 filas × 3 columnas, 12 etiquetas por hoja y páginas adicionales automáticas.

## Tres pestañas

1. **Etiquetas**: selección, vista previa y exportación.
2. **Consulta**: cruce SAP, Código DIA, promedio, MIN/MAX, formato y estatus.
3. **Acomodo**: foto del rack y marcadores de los ingredientes elegidos.

La cabecera se resume como `38107 · Pedregal · Uso Sem 18-25`. En cada hoja PDF se imprime una sola fila superior con Tienda, Semanas y Fecha de actualización.

## Ejecutar

La carga por tienda usa `fetch`, por lo que se debe servir por HTTP:

```bash
python -m http.server 8000
```

Después abre `http://localhost:8000`.

## Regenerar datos

El ZIP de origen no se duplica dentro del proyecto porque contiene casi 600 MB sin comprimir. Para reconstruir el motor con otro corte:

```bash
python tools/build_data.py \
  --zip "/ruta/Max & Min_1_34.zip" \
  --directory sources/Directorio.xlsx \
  --prices sources/Lista_Precios_Base.xlsx
```

El constructor acepta tanto los CSV UTF-16 estándar como el formato de comillas duplicadas detectado en la semana 34. Los datos se dividen en carpetas de máximo 80 archivos y menos de 25 MB.

## Validar antes de publicar

```bash
node --check js/app.js
node --check sw.js
python tools/cleanup_obsolete.py
python tools/audit_project.py
python tools/audit_pdf_export.py
```

Si el ZIP original está disponible, agrega una reconciliación exacta de Pedregal:

```bash
python tools/reconcile_source.py --zip "/ruta/Max & Min_1_34.zip" --ceco 38107 --weeks 18-25
```

El workflow `Validar Max Min Remaster` ejecuta estas verificaciones en cada push/PR. `Limpiar motores obsoletos` es manual y elimina sólo patrones conocidos del motor anterior.

## Exportación segura

El flujo de exportación sigue el patrón de validación local de [Lay-Out_2.0](https://github.com/sbx-mex/Lay-Out_2.0): generador PDF empacado en el repositorio, orientación verificada, conteo esperado de páginas, nombre de archivo limpio, progreso visible y cierre confirmado.

## Publicar en GitHub Pages

1. Sustituir la raíz del repositorio `Max-Min` con este contenido en una rama de trabajo.
2. Abrir un Pull Request y esperar el workflow verde.
3. Publicar la rama aprobada en GitHub Pages.

No se incluyeron `data_part_*.js`, `data_sem_*.js`, `data_index.js`, imágenes hero/splash antiguas ni otros motores duplicados.
