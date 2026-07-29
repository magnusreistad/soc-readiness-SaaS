"""
app/utils/secure_ai_cache.py

Tenant-isolated AI response cache for the evidence evaluator.

Key design decisions vs the legacy ai_cache.py:
    - Cache key includes org_id — structurally impossible for org A's
      cached result to be returned to org B.
    - Evidence evaluation results are NEVER cached — each evaluation
      must be a fresh AI call because evidence documents contain
      sensitive client data that must not persist anywhere.
    - Only caches AICPA criteria lookups and static control descriptions
      which contain no client data.
    - All cache entries have a TTL enforced at read time.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta

from app.utils.db_postgres import get_db

logger = logging.getLogger(__name__)

# Cache TTL — criteria lookups are stable; 7 days is safe
_TTL_DAYS = 7

# Cache is ONLY permitted for these safe, non-sensitive operation types
_CACHEABLE_OPERATIONS = frozenset({
    'criteria_suggestion',   # suggest TSC criteria for a control description
    'control_interpretation', # interpret pasted control text
    'incident_classification', # classify threat feed articles
})


def _make_key(org_id: int, operation: str, content: str) -> str:
    """
    Produces a cache key that is:
        - Tenant-scoped: different orgs always get different keys
        - Operation-scoped: different operations never collide
        - Content-addressed: same content = same key (enables deduplication)
    """
    raw = f"{org_id}:{operation}:{content[:500]}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def get_cached(
    org_id: int,
    operation: str,
    content: str,
) -> dict | None:
    """
    Returns cached result for (org_id, operation, content) or None on miss.

    IMPORTANT: Evidence evaluation results must never be cached.
    Raises ValueError if called with operation='evidence_evaluation'.
    """
    if operation == 'evidence_evaluation':
        raise ValueError(
            'Evidence evaluation results must never be cached. '
            'Each evaluation must be a fresh AI call.'
        )

    if operation not in _CACHEABLE_OPERATIONS:
        logger.warning('Cache lookup for unknown operation: %s', operation)
        return None

    key = _make_key(org_id, operation, content)
    cutoff = datetime.now(timezone.utc) - timedelta(days=_TTL_DAYS)

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT result_json FROM ai_response_cache
                    WHERE content_hash = %s
                      AND org_id       = %s
                      AND created_at   > %s
                    LIMIT 1
                    """,
                    (key, org_id, cutoff),
                )
                row = cur.fetchone()
    except Exception as exc:
        logger.error('Cache read failed: %s', exc)
        return None

    if row is None:
        return None

    try:
        return json.loads(row['result_json'])
    except json.JSONDecodeError:
        return None


def store_cached(
    org_id: int,
    operation: str,
    content: str,
    result: dict,
) -> None:
    """
    Stores a result in the tenant-scoped cache.

    Evidence evaluation results are explicitly forbidden.
    """
    if operation == 'evidence_evaluation':
        raise ValueError(
            'Evidence evaluation results must never be cached.'
        )

    if operation not in _CACHEABLE_OPERATIONS:
        logger.warning('Refusing to cache unknown operation: %s', operation)
        return

    key = _make_key(org_id, operation, content)
    result_json = json.dumps(result)

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_response_cache
                        (content_hash, org_id, model, result_json)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (content_hash) DO UPDATE
                        SET result_json = EXCLUDED.result_json,
                            created_at  = NOW()
                    """,
                    (key, org_id, operation, result_json),
                )
    except Exception as exc:
        # Cache write failure is non-fatal — log and continue
        logger.error('Cache write failed: %s', exc)