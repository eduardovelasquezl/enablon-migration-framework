# Export Engine

> **IMPORTANTE — Status: Approved Design.**
> Este documento describe arquitectura **aprobada**, no implementación
> existente. **No existe ningún código de esta capa en `src/` a día de esta
> versión.** Ningún elemento de este documento debe interpretarse como
> disponible para usar.

## Por qué está aprobado pero no implementado

El Knowledge Engine (ver [`analysis_engine.md`](analysis_engine.md)) ya
determina qué está listo para carga (`ready_for_final_load`) y por qué. Falta
la capa que traduzca ese resultado en el CSV real de importación a Enablon —
deliberadamente pospuesta hasta contar con un template de importación validado
por el cliente para cada objeto Enablon. Generar CSV sin esa plantilla sería
inventar un formato, exactamente lo que este proyecto evita en todo lo demás.

## Componentes aprobados

### `ExportPlan`
Decide **qué** se exporta en una ejecución concreta: qué `MigrationObject`,
con qué alcance (¿solo `ready_for_final_load`? ¿incluir bloqueados con nota?),
y en qué orden — reutilizando el mismo principio de "Action Plans al final"
que ya aplica `project_analysis.py`.

### `ExportDefinition`
Por objeto Enablon, la definición de qué columnas del CSV final corresponden a
qué campos ya resueltos del modelo (`Mapping`/`EnablonField`), y qué
transformación de formato final aplica (fecha, separador decimal...) — sin
reinterpretar ninguna regla de negocio ya resuelta antes, solo dar forma de
salida.

### `CSV Generator`
Produce el contenido del CSV a partir de un `ExportDefinition` y del resultado
de análisis ya finalizado — nunca vuelve a decidir si un registro está listo,
eso ya lo decidió `finalize_action_plans()`/el resto del Knowledge Engine.

### `CSV Writer`
Escribe el fichero físico con el encoding/separador que exija cada plantilla
real de Enablon (algunas ya observadas son UTF-16 con tabulador; otras UTF-8/
Latin-1 con `;` — ver `knowledge_repository.md`). No decide contenido, solo
formato de fichero.

### `CSV Validator`
Valida el CSV generado contra la plantilla real de Enablon (columnas
obligatorias, tipos, longitudes) antes de considerarlo entregable — un control
de calidad final, distinto de las validaciones de cobertura que ya hace
`mapping_coverage.py` sobre los datos de origen.

### `ExportPackage`
Agrupa los CSV generados de una ejecución de exportación completa, con su
propio `manifest.yaml` (mismo espíritu que el ya implementado en
`project_analysis.py`, pero para la entrega final en vez de para el análisis).

### `Manifest` (de exportación)
Registro de qué se generó, con qué hashes, de qué versión del análisis
(`analysis_run_id` de origen) y con qué plantilla — para que una entrega sea
trazable hasta el análisis que la produjo.

## Lo que este diseño NO resuelve todavía

- Qué plantilla exacta usa cada objeto Enablon (pendiente de validar con el
  cliente, objeto por objeto).
- Si la entrega final es manual o vía API — fuera de alcance declarado del
  framework por ahora.
- Cualquier forma de reintentar o versionar una exportación ya entregada — eso
  pertenece a Fase 6 (Versioning) del roadmap, no a esta capa.

## Relación con el resto de la arquitectura

```
ProjectAnalysisResult (Implemented)
        │
        ▼
ExportPlan + ExportDefinition (Approved Design)
        │
        ▼
CSV Generator → CSV Writer → CSV Validator (Approved Design)
        │
        ▼
ExportPackage + Manifest (Approved Design)
```
