"""Synthetic multi-tenant B2B CRM and billing database.

See data/saas/README.md for the dataset card and docs/adr/004-saas-database.md for the design.
The generator lives in `text2sql.data.saas.generate` and is not re-exported here, so that
`python -m text2sql.data.saas.generate` does not import its own module twice.
"""

from text2sql.data.saas.dictionary import (
    DEFAULT_DB_PATH,
    SAAS_DB_ID,
    TABLES,
    ColumnSpec,
    TableSpec,
    load_saas_schema,
)
from text2sql.data.saas.planted import (
    CANARY_COLUMNS,
    PlantedInjection,
    canary_values,
    planted_injections,
)
from text2sql.data.saas.policy import saas_scope_policy
from text2sql.data.saas.profile import AS_OF, SAAS_SEED

__all__ = [
    "AS_OF",
    "CANARY_COLUMNS",
    "DEFAULT_DB_PATH",
    "SAAS_DB_ID",
    "SAAS_SEED",
    "TABLES",
    "ColumnSpec",
    "PlantedInjection",
    "TableSpec",
    "canary_values",
    "load_saas_schema",
    "planted_injections",
    "saas_scope_policy",
]
