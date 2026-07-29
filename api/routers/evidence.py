"""
api/routers/evidence.py

Evidence API — control-scoped, phase-aware evidence upload and evaluation.

Evidence is no longer a one-shot stateless evaluation. Each file is:
    - Attached to a specific control
    - Tagged to an audit phase (walkthrough / testing_population / testing_ipe / testing_sample)
    - Evaluated in context of the control AND the criterion
    - Persisted (extracted_text + evaluation JSONB) in evidence_files table

Endpoints:
    GET    /api/v1/controls/{control_id}/evidence
           List all evidence files for a control, grouped by phase.

    POST   /api/v1/controls/{control_id}/evidence
           Upload a file, extract text, run evaluation, store result.
           Multipart form: file, phase, criteria_code, sample_reference (optional)

    DELETE /api/v1/controls/{control_id}/evidence/{evidence_id}
           Remove an evidence file.

    POST   /api/v1/controls/{control_id}/evidence/{evidence_id}/re-evaluate
           Re-run the AI evaluation on an existing file's stored extracted_text.

    POST   /api/v1/controls/{control_id}/evidence/package-eval
           Evaluate the complete evidence package for this control holistically.
           Looks across all phases and returns a package-level readiness verdict.

Legacy endpoint preserved for backwards compatibility (returns 410 with migration note):
    POST   /api/v1/evidence/evaluate  →  410 Gone
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from api.dependencies import AnalystUser, AuthUser
from app.utils.document_processor import extract_text, ALLOWED_MIME_TYPES
from app.utils.soc_mapper import SOC_LABELS
from app.utils.db_postgres import get_control_by_id, get_db
from app.ai.evidence_evaluator import (
    evaluate_evidence,
    VALID_PHASES,
    PHASE_LABELS,
    EvaluationResult,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_CRITERIA = set(SOC_LABELS.keys())


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class EvidenceFileOut(BaseModel):
    id: int
    control_id: int
    criteria_code: Optional[str]
    phase: str
    phase_label: str
    sample_reference: Optional[str]
    filename: str
    file_type: str
    evaluation: Optional[dict]      # Full EvaluationResult as dict, or None
    uploaded_by: Optional[str]
    uploaded_at: str
    evaluated_at: Optional[str]


class EvidenceListOut(BaseModel):
    control_id: int
    walkthrough:          list[EvidenceFileOut]
    testing_population:   list[EvidenceFileOut]
    testing_ipe:          list[EvidenceFileOut]
    testing_sample:       list[EvidenceFileOut]
    package_status:       str   # 'complete' | 'incomplete' | 'not_started'
    package_summary:      str   # One-line summary of overall readiness


class PackageEvalOut(BaseModel):
    verdict: str            # 'ready_to_submit' | 'needs_work' | 'do_not_submit'
    rejection_risk: str     # 'low' | 'medium' | 'high'
    summary: str
    phase_verdicts: dict    # phase → verdict for each phase present
    blocking_gaps: list[str]
    what_to_fix: list[str]


class PopulationIpeOut(BaseModel):
    population: EvidenceFileOut
    ipe: EvidenceFileOut


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_evidence_out(row: dict) -> EvidenceFileOut:
    evaluation = row.get('evaluation')
    if isinstance(evaluation, str):
        try:
            evaluation = json.loads(evaluation)
        except Exception:
            evaluation = None

    return EvidenceFileOut(
        id=row['id'],
        control_id=row['control_id'],
        criteria_code=row.get('criteria_code'),
        phase=row['phase'],
        phase_label=PHASE_LABELS.get(row['phase'], row['phase']),
        sample_reference=row.get('sample_reference'),
        filename=row['filename'],
        file_type=row['file_type'],
        evaluation=evaluation,
        uploaded_by=row.get('uploaded_by'),
        uploaded_at=str(row.get('uploaded_at', '')),
        evaluated_at=str(row['evaluated_at']) if row.get('evaluated_at') else None,
    )


def _get_evidence_rows(control_id: int, org_id: int) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, control_id, criteria_code, phase, sample_reference,
                       filename, file_type, evaluation, uploaded_by,
                       uploaded_at, evaluated_at
                FROM evidence_files
                WHERE control_id = %s AND org_id = %s
                ORDER BY uploaded_at ASC
                """,
                (control_id, org_id),
            )
            # RealDictCursor returns RealDictRow objects — dict() converts cleanly
            return [dict(row) for row in cur.fetchall()]


def _derive_package_status(rows: list[dict]) -> tuple[str, str]:
    """
    Returns (package_status, package_summary) based on what phases have files.
    """
    phases_present = {r['phase'] for r in rows}
    all_phases = {'walkthrough', 'testing_population', 'testing_ipe', 'testing_sample'}

    if not phases_present:
        return 'not_started', 'No evidence uploaded yet.'

    verdicts = []
    for r in rows:
        ev = r.get('evaluation')
        if isinstance(ev, str):
            try:
                ev = json.loads(ev)
            except Exception:
                ev = None
        if ev:
            verdicts.append(ev.get('verdict', 'do_not_submit'))

    if not verdicts:
        return 'incomplete', 'Files uploaded but not yet evaluated.'

    if all_phases.issubset(phases_present) and all(v == 'ready_to_submit' for v in verdicts):
        return 'complete', 'All phases present and ready to submit.'

    blocking = [v for v in verdicts if v == 'do_not_submit']
    if blocking:
        return 'incomplete', f'{len(blocking)} file(s) flagged as Do Not Submit.'

    missing = all_phases - phases_present
    if missing:
        missing_labels = [PHASE_LABELS.get(p, p) for p in missing]
        return 'incomplete', f'Missing: {", ".join(missing_labels)}.'

    return 'incomplete', 'Some files need work before submission.'


# ---------------------------------------------------------------------------
# GET /api/v1/controls/{control_id}/evidence
# ---------------------------------------------------------------------------

@router.get(
    '/controls/{control_id}/evidence',
    response_model=EvidenceListOut,
)
def list_evidence(control_id: int, current_user: AuthUser):
    """Returns all evidence files for a control, grouped by phase."""
    # Verify control belongs to org
    control = get_control_by_id(control_id, current_user.org_id)
    if not control:
        raise HTTPException(status_code=404, detail='Control not found.')

    rows = _get_evidence_rows(control_id, current_user.org_id)
    files = [_to_evidence_out(r) for r in rows]

    package_status, package_summary = _derive_package_status(rows)

    return EvidenceListOut(
        control_id=control_id,
        walkthrough=        [f for f in files if f.phase == 'walkthrough'],
        testing_population= [f for f in files if f.phase == 'testing_population'],
        testing_ipe=        [f for f in files if f.phase == 'testing_ipe'],
        testing_sample=     [f for f in files if f.phase == 'testing_sample'],
        package_status=package_status,
        package_summary=package_summary,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/controls/{control_id}/evidence
# ---------------------------------------------------------------------------

@router.post(
    '/controls/{control_id}/evidence',
    response_model=EvidenceFileOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidence(
    control_id: int,
    current_user: AnalystUser,
    file: UploadFile = File(...),
    phase: str = Form(...),
    criteria_code: str = Form(...),
    sample_reference: Optional[str] = Form(default=None),
):
    """
    Upload an evidence file, extract text, evaluate in context of the control
    and phase, and persist the result.

    Multipart form fields:
        file             : The evidence document
        phase            : walkthrough | testing_population | testing_ipe | testing_sample
        criteria_code    : TSC criterion e.g. 'CC6.1'
        sample_reference : (testing_sample only) e.g. "User: john@acme.com"
    """
    # ── Validate inputs ──────────────────────────────────────────────────────
    phase = phase.strip().lower()
    if phase not in VALID_PHASES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid phase '{phase}'. Must be one of: {sorted(VALID_PHASES)}",
        )

    criteria_code = criteria_code.strip().upper()
    if criteria_code not in _VALID_CRITERIA:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid criteria code '{criteria_code}'.",
        )

    mime_type = file.content_type or 'application/octet-stream'
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type: {mime_type}. "
                f"Accepted: PDF, PNG, JPEG, WEBP, Excel, Word, CSV, plain text."
            ),
        )

    # ── Verify control belongs to org ────────────────────────────────────────
    control = get_control_by_id(control_id, current_user.org_id)
    if not control:
        raise HTTPException(status_code=404, detail='Control not found.')

    # ── Extract text from file ───────────────────────────────────────────────
    contents = await file.read()

    MAX_SIZE = 20 * 1024 * 1024     # 20 MB
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail='File too large. Maximum size is 20 MB.',
        )

    extraction = extract_text(contents, file.filename or 'upload', mime_type)
    del contents  # release bytes immediately after extraction

    if extraction.error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=extraction.error,
        )

    extracted_text  = extraction.text
    file_type_label = extraction.file_type
    was_truncated   = extraction.was_truncated

    # ── Run evaluation ───────────────────────────────────────────────────────
    import json as _json
    tsc_criteria = control.get('tsc_criteria', '[]')
    if isinstance(tsc_criteria, str):
        try:
            tsc_criteria = _json.loads(tsc_criteria)
        except Exception:
            tsc_criteria = []

    # For IPE phase: fetch extracted_text from any population files already
    # uploaded to this control so the AI can cross-check record counts,
    # date ranges, and source system names directly.
    population_context: Optional[str] = None
    if phase == 'testing_ipe':
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT extracted_text
                    FROM evidence_files
                    WHERE control_id = %s
                      AND org_id = %s
                      AND phase = 'testing_population'
                      AND extracted_text IS NOT NULL
                    ORDER BY uploaded_at ASC
                    """,
                    (control_id, current_user.org_id),
                )
                pop_rows = cur.fetchall()
        if pop_rows:
            # Concatenate all population texts with a separator
            # Cap total at 6000 chars to avoid bloating the prompt context
            parts = []
            total = 0
            for row in pop_rows:
                text = row[0] if isinstance(row, tuple) else row.get('extracted_text', '')
                if text and total < 6000:
                    chunk = text[:max(0, 6000 - total)]
                    parts.append(chunk)
                    total += len(chunk)
            population_context = '\n\n---\n\n'.join(parts) if parts else None

    result: EvaluationResult = evaluate_evidence(
        raw_text=extracted_text,
        criteria_code=criteria_code,
        phase=phase,
        control_title=control.get('title', ''),
        control_description=control.get('description', ''),
        control_type=control.get('control_type', 'manual'),
        file_type=file_type_label,
        was_truncated=was_truncated,
        sample_reference=sample_reference if phase == 'testing_sample' else None,
        population_context=population_context,
    )

    # ── Persist to evidence_files ────────────────────────────────────────────
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO evidence_files (
                    org_id, control_id, criteria_code, phase,
                    sample_reference, filename, file_type,
                    extracted_text, evaluation,
                    uploaded_by, evaluated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id, uploaded_at
                """,
                (
                    current_user.org_id,
                    control_id,
                    criteria_code,
                    phase,
                    sample_reference if phase == 'testing_sample' else None,
                    file.filename,
                    mime_type,
                    extracted_text,             # stored for future re-evaluation
                    _json.dumps(result.to_dict()),
                    current_user.email,
                ),
            )
            inserted = cur.fetchone()
            new_id = inserted[0] if isinstance(inserted, tuple) else inserted['id']
            uploaded_at = inserted[1] if isinstance(inserted, tuple) else inserted['uploaded_at']

    # ── Auto-re-evaluate existing IPE files when population is uploaded ────────
    # If the user uploaded population evidence and there are already IPE files
    # for this control (uploaded before the population), silently re-evaluate
    # them now so they benefit from the cross-reference.
    if phase == 'testing_population' and extracted_text:
        _re_evaluate_ipe_files(
            control=control,
            control_id=control_id,
            org_id=current_user.org_id,
            new_population_text=extracted_text,
        )

    return EvidenceFileOut(
        id=new_id,
        control_id=control_id,
        criteria_code=criteria_code,
        phase=phase,
        phase_label=PHASE_LABELS.get(phase, phase),
        sample_reference=sample_reference if phase == 'testing_sample' else None,
        filename=file.filename or 'unknown',
        file_type=mime_type,
        evaluation=result.to_dict(),
        uploaded_by=current_user.email,
        uploaded_at=str(uploaded_at),
        evaluated_at=str(uploaded_at),
    )


# ---------------------------------------------------------------------------
# Internal helper: re-evaluate all IPE files for a control when new population
# evidence arrives. Called automatically from upload_evidence.
# ---------------------------------------------------------------------------

def _re_evaluate_ipe_files(
    control: dict,
    control_id: int,
    org_id: int,
    new_population_text: str,
) -> None:
    """
    Silently re-evaluates all testing_ipe rows for this control using the
    newly uploaded population text as cross-reference context.
    Errors are logged but never surfaced to the caller.
    """
    import json as _json

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, criteria_code, filename, file_type,
                           extracted_text, sample_reference
                    FROM evidence_files
                    WHERE control_id = %s AND org_id = %s
                      AND phase = 'testing_ipe'
                      AND extracted_text IS NOT NULL
                    """,
                    (control_id, org_id),
                )
                ipe_rows = [dict(r) for r in cur.fetchall()]

        if not ipe_rows:
            return

        for row in ipe_rows:
            try:
                updated = evaluate_evidence(
                    raw_text=row['extracted_text'],
                    criteria_code=row['criteria_code'] or control.get('tsc_criteria', [''])[0],
                    phase='testing_ipe',
                    control_title=control.get('title', ''),
                    control_description=control.get('description', ''),
                    control_type=control.get('control_type', 'manual'),
                    file_type=row['file_type'],
                    was_truncated=False,
                    population_context=new_population_text[:6000],
                )
                with get_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE evidence_files
                            SET evaluation = %s, evaluated_at = NOW(), updated_at = NOW()
                            WHERE id = %s AND org_id = %s
                            """,
                            (_json.dumps(updated.to_dict()), row['id'], org_id),
                        )
                logger.info(
                    'Auto-re-evaluated IPE file %s after new population upload '
                    '(control_id=%s)', row['id'], control_id
                )
            except Exception as exc:
                logger.warning(
                    'Failed to auto-re-evaluate IPE file %s: %s', row['id'], exc
                )
    except Exception as exc:
        logger.warning('IPE auto-re-evaluation failed for control %s: %s', control_id, exc)


# ---------------------------------------------------------------------------
# POST /api/v1/controls/{control_id}/evidence/population-ipe
# Combined upload: population export + IPE validation in one request.
# The population is evaluated first, then IPE is evaluated with population
# context — guaranteeing cross-referencing regardless of upload order.
# ---------------------------------------------------------------------------

class PopulationIpeOut(BaseModel):
    population: EvidenceFileOut
    ipe: EvidenceFileOut


@router.post(
    '/controls/{control_id}/evidence/population-ipe',
    response_model=PopulationIpeOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_population_with_ipe(
    control_id: int,
    current_user: AnalystUser,
    population_file: UploadFile = File(...),
    ipe_file: UploadFile = File(...),
    criteria_code: str = Form(...),
):
    """
    Combined upload: population export + IPE validation evidence in one request.

    Evaluates the population first, then evaluates the IPE file with the
    population's extracted text as cross-reference context — so the AI can
    directly compare record counts, date ranges, and source system names.

    Multipart form fields:
        population_file : The population export (system report, CSV, etc.)
        ipe_file        : The IPE validation evidence (report params screenshot,
                          reconciliation, etc.)
        criteria_code   : TSC criterion e.g. 'CC9.2'
    """
    import json as _json

    criteria_code = criteria_code.strip().upper()
    if criteria_code not in _VALID_CRITERIA:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid criteria code '{criteria_code}'.",
        )

    control = get_control_by_id(control_id, current_user.org_id)
    if not control:
        raise HTTPException(status_code=404, detail='Control not found.')

    MAX_SIZE = 20 * 1024 * 1024

    # ── Process population file ───────────────────────────────────────────────
    pop_mime = population_file.content_type or 'application/octet-stream'
    if pop_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Population file: unsupported type {pop_mime}.",
        )
    pop_contents = await population_file.read()
    if len(pop_contents) > MAX_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail='Population file too large (max 20 MB).')

    pop_extraction = extract_text(pop_contents, population_file.filename or 'population', pop_mime)
    del pop_contents
    if pop_extraction.error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Population file: {pop_extraction.error}",
        )
    pop_text      = pop_extraction.text
    pop_type_label = pop_extraction.file_type
    pop_truncated  = pop_extraction.was_truncated

    pop_result = evaluate_evidence(
        raw_text=pop_text,
        criteria_code=criteria_code,
        phase='testing_population',
        control_title=control.get('title', ''),
        control_description=control.get('description', ''),
        control_type=control.get('control_type', 'manual'),
        file_type=pop_type_label,
        was_truncated=pop_truncated,
    )

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO evidence_files (
                    org_id, control_id, criteria_code, phase,
                    filename, file_type, extracted_text, evaluation,
                    uploaded_by, evaluated_at
                ) VALUES (%s, %s, %s, 'testing_population', %s, %s, %s, %s, %s, NOW())
                RETURNING id, uploaded_at
                """,
                (
                    current_user.org_id, control_id, criteria_code,
                    population_file.filename, pop_mime,
                    pop_text, _json.dumps(pop_result.to_dict()),
                    current_user.email,
                ),
            )
            row = cur.fetchone()
            pop_id = row[0] if isinstance(row, tuple) else row['id']
            pop_uploaded_at = row[1] if isinstance(row, tuple) else row['uploaded_at']

    # ── Process IPE file — with population context ───────────────────────────
    ipe_mime = ipe_file.content_type or 'application/octet-stream'
    if ipe_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"IPE file: unsupported type {ipe_mime}.",
        )
    ipe_contents = await ipe_file.read()
    if len(ipe_contents) > MAX_SIZE:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail='IPE file too large (max 20 MB).')

    ipe_extraction = extract_text(ipe_contents, ipe_file.filename or 'ipe', ipe_mime)
    del ipe_contents
    if ipe_extraction.error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"IPE file: {ipe_extraction.error}",
        )
    ipe_text      = ipe_extraction.text
    ipe_type_label = ipe_extraction.file_type
    ipe_truncated  = ipe_extraction.was_truncated

    # Population text is passed directly — no DB round-trip needed
    ipe_result = evaluate_evidence(
        raw_text=ipe_text,
        criteria_code=criteria_code,
        phase='testing_ipe',
        control_title=control.get('title', ''),
        control_description=control.get('description', ''),
        control_type=control.get('control_type', 'manual'),
        file_type=ipe_type_label,
        was_truncated=ipe_truncated,
        population_context=pop_text[:6000],     # cross-reference right here
    )

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO evidence_files (
                    org_id, control_id, criteria_code, phase,
                    filename, file_type, extracted_text, evaluation,
                    uploaded_by, evaluated_at
                ) VALUES (%s, %s, %s, 'testing_ipe', %s, %s, %s, %s, %s, NOW())
                RETURNING id, uploaded_at
                """,
                (
                    current_user.org_id, control_id, criteria_code,
                    ipe_file.filename, ipe_mime,
                    ipe_text, _json.dumps(ipe_result.to_dict()),
                    current_user.email,
                ),
            )
            row = cur.fetchone()
            ipe_id = row[0] if isinstance(row, tuple) else row['id']
            ipe_uploaded_at = row[1] if isinstance(row, tuple) else row['uploaded_at']

    return PopulationIpeOut(
        population=EvidenceFileOut(
            id=pop_id,
            control_id=control_id,
            criteria_code=criteria_code,
            phase='testing_population',
            phase_label=PHASE_LABELS['testing_population'],
            sample_reference=None,
            filename=population_file.filename or 'unknown',
            file_type=pop_mime,
            evaluation=pop_result.to_dict(),
            uploaded_by=current_user.email,
            uploaded_at=str(pop_uploaded_at),
            evaluated_at=str(pop_uploaded_at),
        ),
        ipe=EvidenceFileOut(
            id=ipe_id,
            control_id=control_id,
            criteria_code=criteria_code,
            phase='testing_ipe',
            phase_label=PHASE_LABELS['testing_ipe'],
            sample_reference=None,
            filename=ipe_file.filename or 'unknown',
            file_type=ipe_mime,
            evaluation=ipe_result.to_dict(),
            uploaded_by=current_user.email,
            uploaded_at=str(ipe_uploaded_at),
            evaluated_at=str(ipe_uploaded_at),
        ),
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/controls/{control_id}/evidence/{evidence_id}
# ---------------------------------------------------------------------------

@router.delete(
    '/controls/{control_id}/evidence/{evidence_id}',
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_evidence(
    control_id: int,
    evidence_id: int,
    current_user: AnalystUser,
):
    control = get_control_by_id(control_id, current_user.org_id)
    if not control:
        raise HTTPException(status_code=404, detail='Control not found.')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM evidence_files
                WHERE id = %s AND control_id = %s AND org_id = %s
                """,
                (evidence_id, control_id, current_user.org_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail='Evidence file not found.')


# ---------------------------------------------------------------------------
# POST /api/v1/controls/{control_id}/evidence/{evidence_id}/re-evaluate
# ---------------------------------------------------------------------------

@router.post(
    '/controls/{control_id}/evidence/{evidence_id}/re-evaluate',
    response_model=EvidenceFileOut,
)
def re_evaluate(
    control_id: int,
    evidence_id: int,
    current_user: AnalystUser,
):
    """
    Re-run the AI evaluation on the stored extracted_text.
    Useful when the control description has changed, or to get a fresh
    assessment after a prompt update.
    """
    control = get_control_by_id(control_id, current_user.org_id)
    if not control:
        raise HTTPException(status_code=404, detail='Control not found.')

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, criteria_code, phase, sample_reference,
                       filename, file_type, extracted_text, uploaded_by, uploaded_at
                FROM evidence_files
                WHERE id = %s AND control_id = %s AND org_id = %s
                """,
                (evidence_id, control_id, current_user.org_id),
            )
            raw = cur.fetchone()

    if not raw:
        raise HTTPException(status_code=404, detail='Evidence file not found.')

    row = dict(raw)  # RealDictRow → plain dict

    if not row.get('extracted_text'):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='No extracted text available for re-evaluation. Delete and re-upload the file.',
        )

    # For IPE re-evaluation: fetch current population context
    population_context: Optional[str] = None
    if row['phase'] == 'testing_ipe':
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT extracted_text
                    FROM evidence_files
                    WHERE control_id = %s
                      AND org_id = %s
                      AND phase = 'testing_population'
                      AND extracted_text IS NOT NULL
                    ORDER BY uploaded_at ASC
                    """,
                    (control_id, current_user.org_id),
                )
                pop_rows = cur.fetchall()
        if pop_rows:
            parts = []
            total = 0
            for pr in pop_rows:
                text = pr[0] if isinstance(pr, tuple) else pr.get('extracted_text', '')
                if text and total < 6000:
                    chunk = text[:max(0, 6000 - total)]
                    parts.append(chunk)
                    total += len(chunk)
            population_context = '\n\n---\n\n'.join(parts) if parts else None

    result: EvaluationResult = evaluate_evidence(
        raw_text=row['extracted_text'],
        criteria_code=row['criteria_code'],
        phase=row['phase'],
        control_title=control.get('title', ''),
        control_description=control.get('description', ''),
        control_type=control.get('control_type', 'manual'),
        file_type=row['file_type'],
        was_truncated=False,
        sample_reference=row.get('sample_reference'),
        population_context=population_context,
    )

    import json as _json
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE evidence_files
                SET evaluation = %s, evaluated_at = NOW(), updated_at = NOW()
                WHERE id = %s AND org_id = %s
                RETURNING evaluated_at
                """,
                (_json.dumps(result.to_dict()), evidence_id, current_user.org_id),
            )
            updated = cur.fetchone()
            evaluated_at = updated[0] if isinstance(updated, tuple) else updated['evaluated_at']

    return EvidenceFileOut(
        id=evidence_id,
        control_id=control_id,
        criteria_code=row['criteria_code'],
        phase=row['phase'],
        phase_label=PHASE_LABELS.get(row['phase'], row['phase']),
        sample_reference=row.get('sample_reference'),
        filename=row['filename'],
        file_type=row['file_type'],
        evaluation=result.to_dict(),
        uploaded_by=row.get('uploaded_by'),
        uploaded_at=str(row['uploaded_at']),
        evaluated_at=str(evaluated_at),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/controls/{control_id}/evidence/package-eval
# ---------------------------------------------------------------------------

@router.post(
    '/controls/{control_id}/evidence/package-eval',
    response_model=PackageEvalOut,
)
def package_eval(control_id: int, current_user: AuthUser):
    """
    Holistic evaluation of all evidence phases for a control.

    Does NOT call the AI — derives a package verdict from the stored
    individual evaluations. This keeps it fast and avoids extra API cost.

    Logic:
      - Any 'do_not_submit' verdict → package is 'do_not_submit'
      - All phases present + all 'ready_to_submit' → 'ready_to_submit'
      - Otherwise → 'needs_work'
    """
    control = get_control_by_id(control_id, current_user.org_id)
    if not control:
        raise HTTPException(status_code=404, detail='Control not found.')

    rows = _get_evidence_rows(control_id, current_user.org_id)

    # Read control classification flags to gate which phases are required
    requires_population = bool(control.get('requires_population', True))
    requires_sample     = bool(control.get('requires_sample', True))

    if not rows:
        return PackageEvalOut(
            verdict='do_not_submit',
            rejection_risk='high',
            summary='No evidence has been uploaded for this control.',
            phase_verdicts={},
            blocking_gaps=['No evidence files found. Upload walkthrough evidence to begin.'],
            what_to_fix=['Upload at least one walkthrough evidence file for this control.'],
        )

    import json as _json

    phase_verdicts: dict[str, str] = {}
    blocking_gaps: list[str] = []
    all_what_to_fix: list[str] = []
    phases_present: set[str] = set()

    for row in rows:
        ev = row.get('evaluation')
        if isinstance(ev, str):
            try:
                ev = _json.loads(ev)
            except Exception:
                ev = None
        if not ev:
            continue

        phase = row['phase']
        phases_present.add(phase)
        verdict = ev.get('verdict', 'do_not_submit')

        # Track worst verdict per phase
        existing = phase_verdicts.get(phase)
        if existing != 'do_not_submit':
            phase_verdicts[phase] = verdict

        if verdict == 'do_not_submit':
            for gap in ev.get('gap_attributes', []):
                blocking_gaps.append(f"[{PHASE_LABELS.get(phase, phase)}] {gap}")

        if verdict in ('do_not_submit', 'needs_work'):
            for fix in ev.get('what_to_fix', []):
                all_what_to_fix.append(f"[{PHASE_LABELS.get(phase, phase)}] {fix}")

    # Build required phases based on control classification
    required_phases: set[str] = {'walkthrough'}
    if requires_population:
        required_phases |= {'testing_population', 'testing_ipe'}
    if requires_sample:
        required_phases.add('testing_sample')

    missing = required_phases - phases_present
    for p in sorted(missing):
        blocking_gaps.append(
            f"No evidence uploaded for {PHASE_LABELS.get(p, p)}."
        )

    # Derive overall verdict
    if any(v == 'do_not_submit' for v in phase_verdicts.values()) or missing:
        overall_verdict = 'do_not_submit'
        rejection_risk = 'high'
    elif any(v == 'needs_work' for v in phase_verdicts.values()):
        overall_verdict = 'needs_work'
        rejection_risk = 'medium'
    else:
        overall_verdict = 'ready_to_submit'
        rejection_risk = 'low'

    # Summary
    if overall_verdict == 'ready_to_submit':
        summary = 'All phases complete and ready for external auditor review.'
    elif missing:
        missing_labels = [PHASE_LABELS.get(p, p) for p in sorted(missing)]
        summary = f'Missing evidence for: {", ".join(missing_labels)}.'
    else:
        needs_work_count = sum(1 for v in phase_verdicts.values() if v != 'ready_to_submit')
        summary = f'{needs_work_count} phase(s) need attention before submission.'

    return PackageEvalOut(
        verdict=overall_verdict,
        rejection_risk=rejection_risk,
        summary=summary,
        phase_verdicts=phase_verdicts,
        blocking_gaps=blocking_gaps[:10],       # cap at 10 for readability
        what_to_fix=all_what_to_fix[:5],        # cap at 5 top actions
    )


# ---------------------------------------------------------------------------
# Legacy endpoint — 410 Gone
# ---------------------------------------------------------------------------

@router.post(
    '/evidence/evaluate',
    status_code=status.HTTP_410_GONE,
)
async def legacy_evaluate():
    """
    This endpoint has been superseded.
    Use POST /api/v1/controls/{control_id}/evidence instead.
    Evidence evaluation is now control-scoped and phase-aware.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            'This endpoint has been superseded. '
            'Use POST /api/v1/controls/{control_id}/evidence with a phase parameter. '
            'Evidence evaluation is now attached to a specific control and audit phase.'
        ),
    )