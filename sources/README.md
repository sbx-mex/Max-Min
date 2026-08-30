# Fuentes del corte

- `Directorio.xlsx`: cruce oficial CeCo → nombre de tienda.
- `Lista_Precios_Base.xlsx`: hojas `Catalogo Micros` y `SAP` para obtener Código DIA, ID WOE y Descripción SAP.
- `Etiquetas_MIN_MAX_Carta_Horizontal.pdf`: referencia visual de 4 filas × 3 columnas.
- `Normalizados.zip`: histórico acumulado de insumos descontados por receta. Se transforma con `tools/build_normalized.py` y nunca se descarga completo en el navegador.
- `Max & Min_1_34.zip`: fuente semanal externa usada para generar `data/`; no se duplica aquí por tamaño.

Los registros de `data/` fueron generados el 30/08/2026. Consulta `audit/data_build_report.json` para la reconciliación completa y `audit/ingredients_review.csv` para los cruces que aún requieren decisión humana.

Los registros separados de `data/normalized/` se regeneran al sustituir `Normalizados.zip`. Consulta `audit/normalized_build_report.json` para su reconciliación y `audit/normalized_ingredients_review.csv` para la vigencia individual.
