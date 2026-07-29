"""
api/schemas/vendors.py
api/schemas/controls.py
api/schemas/readiness.py
api/schemas/admin.py

All non-incident Pydantic schemas in one file for now.
Split into separate files if they grow large.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr

# =============================================================================
# INCIDENTS
# =============================================================================

class IncidentOut(BaseModel):
    id:                   int
    org_id:               int
    article_link:         str
    title:                str
    summary:              str
    source_feed:          str
    published_at:         str
    vendor:               str
    vendor_id:            Optional[int] = None
    severity:             str
    incident_type:        str
    ai_reason:            str
    soc_criteria:         list[str]
    soc_type:             str
    alert_status:         str
    event_classification: str
    notified_at:          Optional[str] = None
    acknowledged_by:      str
    acknowledged_at:      Optional[str] = None
    notes:                str
    detected_at:          str
    updated_at:           str

    model_config = {"from_attributes": True}


class IncidentListOut(BaseModel):
    items: list[IncidentOut]
    total: int


class IncidentStatsOut(BaseModel):
    total:        int
    new:          int
    notified:     int
    acknowledged: int
    resolved:     int
    critical:     int
    high:         int
    medium:       int
    low:          int
    unknown:      int
    vendors:      list[str]
    sources:      list[str]


class IncidentActionIn(BaseModel):
    action: str = Field(
        ...,
        description="acknowledge | resolve | false_positive | reopen | "
                    "system_event | system_incident | unclassified"
    )
    notes: Optional[str] = None


class IncidentNotesIn(BaseModel):
    notes: str


# =============================================================================
# VENDORS
# =============================================================================

class VendorOut(BaseModel):
    id:             int
    org_id:         int
    name:           str
    aliases:        list[str]
    category:       str
    active:         bool
    created_at:     str
    incident_count: Optional[int] = 0

    model_config = {"from_attributes": True}


class VendorIn(BaseModel):
    name:     str = Field(..., min_length=1, max_length=200)
    aliases:  list[str] = []
    category: str = ""


class VendorUpdateIn(BaseModel):
    name:     Optional[str] = None
    aliases:  Optional[list[str]] = None
    category: Optional[str] = None
    active:   Optional[bool] = None


# =============================================================================
# CONTROLS
# =============================================================================

class ControlOut(BaseModel):
    # Core control fields
    id:                    int
    org_id:                int
    control_id:            str
    title:                 str
    description:           str
    control_type:          str
    status:                str
    owner:                 str
    tsc_criteria:          list[str]
    ai_suggested_criteria: list[str]
    source:                str
    notes:                 str
    created_at:            str
    updated_at:            str

    # Classification fields
    frequency:              Optional[str] = None
    requires_population:    bool          = False
    requires_sample:        bool          = False
    suggested_sample_size:  Optional[int] = None
    narrative:              Optional[str] = None
    narrative_approved_at:  Optional[str] = None
    narrative_flags:        list          = []

    # Computed on read — not stored in DB
    testing_approach:       Optional[str] = None

    # Evidence health — populated by list endpoint via evidence_files JOIN
    # Single controls (GET /controls/{id}) return defaults (0, None, [], None)
    evidence_count:    int            = 0
    worst_verdict:     Optional[str]  = None   # ready_to_submit | needs_work | do_not_submit
    phases_present:    list[str]      = []
    last_evidence_at:  Optional[str]  = None
    audit_bucket:      str            = 'no_evidence'  # audit_ready | at_risk | blocked | no_evidence
    next_action:       Optional[str]  = None

    model_config = {"from_attributes": True}


class ControlIn(BaseModel):
    title:        str  = Field(..., min_length=1, max_length=300)
    description:  str  = ""
    control_type: str  = Field("manual", pattern="^(automated|manual|itdm)$")
    status:       Optional[str] = 'not_tested'
    frequency:    Optional[str] = None
    owner:        str  = ""
    tsc_criteria: list[str] = []
    notes:        str  = ""


class ControlUpdateIn(BaseModel):
    control_id:   Optional[str]       = None
    title:        Optional[str]       = None
    description:  Optional[str]       = None
    control_type: Optional[str]       = None
    status:       Optional[str]       = None
    frequency:    Optional[str]       = None
    owner:        Optional[str]       = None
    tsc_criteria: Optional[list[str]] = None
    notes:        Optional[str]       = None


# =============================================================================
# ADMIN
# =============================================================================

class UserOut(BaseModel):
    id:           str       # UUID
    org_id:       int
    name:         str
    email:        str
    role:         str
    is_active:    bool
    created_at:   str
    last_login:   Optional[str]

    model_config = {"from_attributes": True}


class UserInviteIn(BaseModel):
    name:  str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    role:  str = Field("analyst", pattern="^(admin|analyst|auditor)$")


class UserRoleUpdateIn(BaseModel):
    role: str = Field(..., pattern="^(admin|analyst|auditor)$")


class TscScopeUpdateIn(BaseModel):
    categories: list[str] = Field(..., min_length=1)


class OrgOut(BaseModel):
    id: int
    name: str
    slug: str
    tsc_scope: list[str]
    examination_type: str = "type2"
    plan: str = "free"
    subscription_status: str = "trialing"
    trial_ends_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class ExamTypeUpdateIn(BaseModel):
    examination_type: str = Field(..., pattern="^(type1|type2)$")