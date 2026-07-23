# Evaluación de mappings de entidad — Bloque3_Mappings_Entidades/

> Cubre los 2 workbooks de `inputs/_incoming_claude_web/Bloque3_Mappings_Entidades/`.
> Ver `evidence/entity_mapping_catalog.yaml` para el detalle estructurado
> fila a fila. No se asume que una coincidencia por descripción sea un
> mapping aprobado — donde el propio workbook marca "No migra"/"NO MIGRA",
> se trata como decisión funcional ya tomada; donde marca una instrucción
> en lenguaje natural pendiente de ejecutar, se trata como `pending_mapping`,
> nunca como `mapped`.

## 1. Los dos workbooks

- **`260311 Mapeo gct Enablon-Match UORG ENTIDAD (1).xlsx`** (0.2 MB, 5
  hojas: `Niveles`, `Exportación eje`, `Plantas`, `Fabricas`, `Unidades`) —
  resuelve el eje de entidad del sistema **GCT** (relevante para `moc`).
- **`Mapeo ITP primer eje enablon_revisado _final1 (version 4).xlsx`**
  (1.2 MB, 15 hojas, 1 hoja oculta) — resuelve el eje de entidad del
  sistema **ITP/Prevención** (relevante para `simulacros`, `safety_meetings`,
  `eventos`, `ops`, `inspecciones`).

Ambos se abrieron en modo `read_only`/`data_only` (fórmula + valor cacheado)
sin modificarlos.

## 2. Workbook GCT — estructura confirmada

- **`Niveles`** (392 filas): encadena `IdCentro → IdFabrica → IdPlanta →
  IdUnidad` con fórmulas `XLOOKUP` cruzadas entre las 4 hojas del mismo
  workbook, generando un código compuesto (`CONCAT(IdFabrica_code, ".",
  Planta_code)`). Varias filas de muestra devuelven `'NULL.NULL'` en el
  código final — no se ha confirmado si es un resultado esperado (unidad
  sin subdivisión) o una cadena de lookup rota (ver `entity_mapping_catalog.yaml`,
  `entity_mapping:gct_uorg.niveles_lookup_chain`, `OQ-ENT-01`).
- **`Exportación eje`** (1722 filas): esta es, con alta confianza, la misma
  fuente que `inputs/entity_catalog/First_Axis_export_bruto.csv` (1724
  filas incl. cabecera) — no una copia independiente. Fórmula de ruta:
  `=IF(Parent="<Top>",Code,CONCAT(Parent,">",Code))`, exactamente el
  mecanismo que CLAUDE.md describe para reconstruir `Ruta1` a partir de
  `Parent`+`Code`.

## 3. Workbook ITP — estructura confirmada

- **10 hojas por site/entidad legal** (`Estructura`, `C&CE`, `Madrid
  Corporación`, `MCPF`, `MCSH`, `MCPM`, `M&NC`, `Site Canarias`, `PESR`,
  `PELR`): cada una lista `IDCentro`/`IDUnidadOrg` de ese site con una
  columna de decisión (`Propuesta de mapeo` o `Descripción Unidad`).
  **observed**: una proporción sustancial de filas en varias de estas
  hojas está marcada explícitamente `"No migra"` / `"NO MIGRA"` — esto es
  una decisión funcional YA tomada y documentada, no una carencia de
  evidencia. No se contó el total exacto (fuera de alcance de este
  incremento).
- **`Site Canarias`** y **`MCPM`**: a diferencia de las demás, varias filas
  contienen una INSTRUCCIÓN EN LENGUAJE NATURAL en la columna de mapeo
  (p. ej. "Crear L5 dentro de SITE CANARIAS > OPERACIONES TENERIFE que sea
  'RT HÍSTICO'..." para Ref. Tenerife; "hay que dividir dos centros L4"
  para MCPM) — **no** son mappings ya resueltos, son tareas pendientes de
  ejecución manual documentadas en el propio archivo. Se clasifican
  `pending_mapping`, nunca `mapped`, precisamente para no confundir una
  instrucción con una decisión aplicada (ver `OQ-ENT-03`).
- **`MCSH`** (CQ-Shanghai): única hoja con nombres bilingües
  español/mandarín observados directamente en las columnas de origen. La
  mayoría de sus unidades están marcadas `"No migra"`; una está marcada
  `"HISTORIC"` con código de destino ya asignado (`CEPSA.QM.09`).
- **Hoja oculta `Centros-empresas-departamentos-`** (6154 filas,
  `IDCentro`/`nombrecentro`/`IDEmpresa`/`nombreempresa`/`IDDepartamento`/
  `IDUnidadOrg`): tabla de referencia base contra la que resuelven (vía
  `XLOOKUP`) tanto `Mapeo Eje final-modificado` como, indirectamente, las
  hojas por site. No aparece en el listado visible de hojas del workbook —
  oculta, no "muy oculta" (no se pudo determinar el atributo `veryHidden`
  con certeza para ninguna hoja de los 12 workbooks, ver limitaciones).
- **`Mapeo Eje final-modificado`** (1696 filas) y **`Eje final 2`** (3038
  filas): las dos hojas más consolidadas — encadenan `XLOOKUP` contra la
  hoja oculta y contra `MAPEOFINAL` (no leída en detalle), produciendo el
  árbol final de entidad en formato `Nivel`/`Referencia`/`Nombre [EN]`/
  `Nombre [ES]`/`Estado`/`Entrada`. `Eje final 2` es la única con las 5
  columnas de idioma completas (EN/FR/ES/ZH/BR) — candidato más completo a
  formato de exportación final, sin confirmar si es el efectivamente usado.

## 4. Relaciones muchos-a-uno / uno-a-muchos observadas

- **Muchos-a-uno**: múltiples `IDUnidadOrg` de un mismo `IDCentro` colapsan
  a menudo al mismo código de destino o a la misma decisión `"No migra"`
  (observado en `C&CE`, `Madrid Corporación`).
- **Uno-a-muchos**: un mismo `IDCentro` (p. ej. `MCPF`, `MCPM`) se marca
  explícitamente para DIVIDIRSE en varios centros de destino de nivel 4 —
  lo opuesto a una consolidación, una decisión de expansión de jerarquía
  documentada en texto libre, pendiente de ejecutar.

## 5. Registros sin mapping y duplicados

- No se identificó, en la muestra leída, ningún registro con
  `mapping_status=unresolved` puro (sin ninguna decisión, ni "No migra" ni
  código asignado) — toda fila muestreada tenía al menos una decisión
  parcial o una instrucción. Esto **no** descarta que existan más adelante
  en las hojas (miles de filas no muestreadas).
- No se ejecutó una comprobación de duplicados de `IDUnidadOrg` entre
  hojas de site distintas — fuera de alcance de este incremento.

## 6. Comentarios y decisiones funcionales documentadas

Los comentarios en columnas de "Propuesta de mapeo" son la fuente más rica
de decisión funcional ya tomada encontrada en todo este incremento — a
diferencia de los ETL de módulo (que documentan CÓMO se transforma un
dato), estas hojas documentan explícitamente el JUICIO de reestructuración
organizativa (qué se fusiona, qué se divide, qué no migra y por qué). Se
recomienda que cualquier especificación futura del campo de entidad
(`Entity`/`FirstAxis`) para cualquier objeto cite directamente estas
columnas de comentario en vez de re-derivar la decisión desde el catálogo
resuelto genérico.

## 7. Versiones o fechas

- `260311 Mapeo gct...xlsx`: creado 2015-06-05, modificado 2026-05-04 —
  el más antiguo del proyecto por fecha de creación, con la actualización
  más reciente entre los 12 workbooks analizados en ambos incrementos.
- `Mapeo ITP primer eje...(version 4).xlsx`: creado 2025-10-02, modificado
  2026-07-02. El nombre de archivo ("version 4") confirma explícitamente
  la existencia de al menos 3 revisiones previas — ningún diff entre
  versiones está disponible en este repositorio.

## 8. Limitaciones

- No se leyeron en detalle las hojas `MAPEOFINAL` (referenciada por
  fórmulas de `Mapeo Eje final-modificado` pero no abierta) ni el resto de
  columnas más allá de las primeras 14 en ninguna hoja.
- No se determinó con certeza el atributo `veryHidden` (muy oculto) para
  ninguna hoja de ningún workbook — `openpyxl`/el XML de `workbook.xml`
  solo confirmó `state="hidden"` o ausencia de atributo (visible); si
  existiera alguna hoja `veryHidden` en estos 12 workbooks, este análisis
  no lo habría distinguido de una oculta normal.
- No se ha confirmado cuál de las dos hojas candidatas a "mapeo final" del
  workbook ITP (`Mapeo Eje final-modificado` vs. `Eje final 2`) es la que
  realmente se usó para producir `inputs/entity_catalog/catalogo_resuelto_code_ruta_site.csv`.
- 1 external link sin resolver en el workbook ITP — no se intentó abrir
  (podría requerir un archivo o conexión no presente en este repositorio).
