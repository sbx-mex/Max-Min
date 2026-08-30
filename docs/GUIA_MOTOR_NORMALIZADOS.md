# Guía del motor Normalizados

## Objetivo

Integrar vasos, tapas y otros insumos descontados por receta sin confundirlos con el histórico principal de ingredientes. El navegador carga únicamente los datos de la tienda elegida.

## Actualización en tres pasos

1. Sustituye `sources/Normalizados.zip` con el archivo acumulado vigente.
2. Abre **Actions → Reconstruir motor Normalizados → Run workflow**. Al cargar el ZIP en `main`, también se inicia automáticamente.
3. Confirma que `audit/normalized_build_report.json` indique `status: ok` y que `sapMatched` y `formatMatched` sean iguales a `ingredients`.

## Regla de vigencia

- `reportWeeks`: semanas en las que el insumo sí fue descontado por receta.
- `lastWeek`: última semana con reporte real para ese ingrediente.
- `stoppedWeek`: primera semana posterior en la que dejó de reportarse.
- El promedio usa sólo las semanas seleccionadas que aparecen en `reportWeeks`; semanas posteriores al término no reducen artificialmente el MIN/MAX.

El aviso es individual. Ejemplo: `Descuento por receta hasta Sem 29 · dejó de reportarse en Sem 30`. Los insumos que llegan al corte actual muestran `Descuento por receta vigente`.

## Corte integrado

- 1,058,496 filas leídas; 1,053,226 registros positivos integrados.
- 949 tiendas vigentes con datos.
- 60 ingredientes: 60 cruces SAP y 60 presentaciones validadas.
- 18 ingredientes vigentes hasta la semana 35 y 42 con término histórico.
- Últimas semanas detectadas: 16, 28, 29, 30 y 35. No existe un corte global en semana 25.

Los CeCo ausentes del Directorio se excluyen y quedan documentados en el reporte; las tiendas abiertas conservan prioridad sobre los cierres temporales.

## Reconstrucción local

```bash
python tools/build_normalized.py
python tools/audit_project.py
```

El constructor lee el CSV UTF-16 en flujo, evita mantener 157 MB en memoria, cruza `Directorio.xlsx`, `Lista_Precios_Base.xlsx` y `presentation_reference.json`, y genera carpetas con máximo 80 archivos.
