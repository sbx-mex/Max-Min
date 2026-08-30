# Parche PDF 38107 · archivos a actualizar

Este parche no incluye `data/`: la carga de 954 tiendas ya está completa.

## Reemplazar o agregar

- `js/app.js`
- `css/styles.css`
- `tools/audit_pdf_export.py`
- `tools/audit_project.py`
- `tools/prepare_pdf_release.py` — nuevo
- `.github/workflows/validate.yml`
- `README.md`
- `docs/Etiquetas_MIN_MAX_Muestra_38107_Sem18-25.pdf`
- `audit/project_report.json`
- `audit/pdf_release_report.json`
- `audit/AUDITORIA_REMASTER_PDF_38107.md`

## Eliminar

Consulta `BORRAR_EN_GITHUB.txt`. El workflow manual `.github/workflows/cleanup-obsolete.yml`, que ya está en el repositorio, realiza el mismo borrado de patrones conocidos.

## Orden seguro

1. Carga los archivos de este parche respetando sus rutas.
2. Ejecuta **Limpiar motores obsoletos** desde GitHub Actions.
3. Ejecuta **Validar Max Min Remaster**.
4. Publica únicamente si ambas acciones terminan en verde.
