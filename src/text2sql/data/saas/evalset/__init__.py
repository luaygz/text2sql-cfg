"""The SaaS evaluation set (data/saas/eval.jsonl) and few-shot pool (data/saas/fewshot_pool.jsonl).

Consumers import the item types and loaders from here. The drafting pipeline that produced the
files lives in the submodules (`python -m text2sql.data.saas.evalset build`); the dataset card
in data/saas/README.md and docs/adr/017-saas-eval-set.md describe how.
"""

from text2sql.data.saas.evalset.models import (
    EVAL_PATH,
    FEWSHOT_PATH,
    Attack,
    AttackCategory,
    Bucket,
    Difficulty,
    Expected,
    FewShotItem,
    Provenance,
    SaasEvalItem,
    load_fewshot_pool,
    load_saas_eval,
)

__all__ = [
    "EVAL_PATH",
    "FEWSHOT_PATH",
    "Attack",
    "AttackCategory",
    "Bucket",
    "Difficulty",
    "Expected",
    "FewShotItem",
    "Provenance",
    "SaasEvalItem",
    "load_fewshot_pool",
    "load_saas_eval",
]
