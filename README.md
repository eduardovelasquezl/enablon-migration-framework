# Migración Histórica a Enablon — Motor de Automatización

Sustituye el ETL en Excel original por un pipeline Python auditable. Antes de
tocar código, lee **`CLAUDE.md`** — es la memoria completa de todo lo
analizado hasta ahora (9 módulos + Acciones, catálogo de entidades, defectos
sistémicos, y el hallazgo abierto más importante del proyecto).

## Instalación

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y rellenar credenciales reales
```

## Qué hay ya poblado

- `sql/source_queries/<módulo>/` — las 34 queries de extracción reales que
  aportó el cliente, tal cual.
- `inputs/entity_catalog/` — el export real del árbol de entidades de
  Enablon (`First_Axis_export_bruto.csv`) y ya el catálogo resuelto
  Code/Ruta1 → Site (`catalogo_resuelto_code_ruta_site.csv`) — es la fuente
  de verdad, no usar los catálogos por módulo del Excel original.
- `inputs/csv_enablon/` — CSV reales ya exportados de Enablon por módulo,
  usados para contrastar la volumetría.
- `inputs/incidents/` — export de 834 tickets del Help Desk del cliente.
- `outputs/reports/` — los informes markdown/CSV ya generados durante el
  análisis manual previo a este repo (histórico, no se regeneran solos).

## Qué falta por implementar

- `config/modules.yaml` tiene el detalle de 8 módulos; falta afinar AP y el
  submódulo "visitas de seguridad y otros" (idorigenac 7/14, no analizado en
  detalle todavía).
- El motor de mapeo (`src/etl/mapping_engine.py`) está probado con datos
  sintéticos (`tests/`) pero no se ha ejecutado todavía contra un módulo real
  de principio a fin. **Simulacros es el candidato natural para el primer
  piloto** — es el módulo más simple y su migración ya está cerrada y
  validada, así que sirve como caso de prueba de equivalencia.
- No hay todavía conexión SQL en vivo probada (`src/db/`) — el acceso de
  solo lectura está concedido pero este entorno de desarrollo no tiene
  conectividad directa; el flujo real hoy es "alguien ejecuta la query y sube
  el resultado".

## Comandos típicos

```bash
# Revisar todas las queries de un módulo (JOINs, WHERE, columnas de entidad)
python -c "
from src.analysis.query_analyzer import review_directory
for name, r in review_directory('sql/source_queries/Eventos').items():
    print(name, '->', r.joins, r.risk_notes)
"

# Ejecutar los tests
pytest tests/ -v
```

## Antes de dar por buena cualquier cifra de volumetría

Lee la sección "Hallazgo #1" de `CLAUDE.md`. Un total agregado sano puede
esconder un site con un problema severo — ya pasó y el motor
(`src/analysis/volumetry.py`) avisa automáticamente por log si detecta el
mismo patrón, pero no lo silencies sin revisar antes.
