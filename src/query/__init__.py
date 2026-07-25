"""Query Engine v0.1 -- filtros reutilizables de solo lectura sobre catálogos
cerrados, con SQL siempre parametrizada.

Primer consumidor: `src.export.prototype.drills`. No cubre todavía ningún
otro `MigrationObject` -- ver `docs/specifications/v1.0/export/` para el
resto del inventario.

Uso típico (CLI -> pipeline):

    from src.query.catalog import DRILLS_FILTER_CATALOG
    from src.query.validator import compile_filter_tokens
    from src.query.sql_builder import compose_filtered_sql

    compiled = compile_filter_tokens(["center_id:eq:25"], DRILLS_FILTER_CATALOG)
    composed = compose_filtered_sql(original_sql_text, compiled)
    # composed.sql_text / composed.parameters -> src.db.query_runner.run_query
"""
from __future__ import annotations
