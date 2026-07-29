"""
Shared SOC 2 mapping logic.

Based on AICPA 2017 Trust Services Criteria (2022 revised points of focus).

Two layers:
  1. Trust Service Category affected (Security, Availability, etc.)
  2. Specific criteria within those categories

System event  = an occurrence (unauthorized access attempt, malware, etc.)
                Does NOT automatically require disclosure.
System incident = a system event requiring management action to prevent
                  or reduce impact on service commitments.
                  Significant ones MUST be disclosed in the SOC report.
"""

import json

# ---------------------------------------------------------------------------
# SOC 2 criteria labels — AICPA 2017 TSC (2022 revised points of focus)
# ---------------------------------------------------------------------------

SOC_LABELS = {
    # Control Environment
    "CC1.1": "COSO Principle 1: The entity demonstrates a commitment to integrity and ethical values.",
    "CC1.2": "COSO Principle 2: The board of directors demonstrates independence from management and exercises oversight of the development and performance of internal control.",
    "CC1.3": "COSO Principle 3: Management establishes, with board oversight, structures, reporting lines, and appropriate authorities and responsibilities in the pursuit of objectives.",
    "CC1.4": "COSO Principle 4: The entity demonstrates a commitment to attract, develop, and retain competent individuals in alignment with objectives.",
    "CC1.5": "COSO Principle 5: The entity holds individuals accountable for their internal control responsibilities in the pursuit of objectives.",

    # Communication and Information
    "CC2.1": "COSO Principle 13: The entity obtains or generates and uses relevant, quality information to support the functioning of internal control.",
    "CC2.2": "COSO Principle 14: The entity internally communicates information, including objectives and responsibilities for internal control, necessary to support the functioning of internal control.",
    "CC2.3": "COSO Principle 15: The entity communicates with external parties regarding matters affecting the functioning of internal control.",

    # Risk Assessment
    "CC3.1": "COSO Principle 6: The entity specifies objectives with sufficient clarity to enable the identification and assessment of risks relating to objectives.",
    "CC3.2": "COSO Principle 7: The entity identifies risks to the achievement of its objectives across the entity and analyzes risks as a basis for determining how the risks should be managed.",
    "CC3.3": "COSO Principle 8: The entity considers the potential for fraud in assessing risks to the achievement of objectives.",
    "CC3.4": "COSO Principle 9: The entity identifies and assesses changes that could significantly impact the system of internal control.",

    # Monitoring Activities
    "CC4.1": "COSO Principle 16: The entity selects, develops, and performs ongoing and/or separate evaluations to ascertain whether the components of internal control are present and functioning.",
    "CC4.2": "COSO Principle 17: The entity evaluates and communicates internal control deficiencies in a timely manner to those parties responsible for taking corrective action, including senior management and the board of directors, as appropriate.",

    # Control Activities
    "CC5.1": "COSO Principle 10: The entity selects and develops control activities that contribute to the mitigation of risks to the achievement of objectives to acceptable levels.",
    "CC5.2": "COSO Principle 11: The entity also selects and develops general control activities over technology to support the achievement of objectives.",
    "CC5.3": "COSO Principle 12: The entity deploys control activities through policies that establish what is expected and in procedures that put policies into action.",

    # Logical and Physical Access Controls
    "CC6.1": "The entity implements logical access security software, infrastructure, and architectures over protected information assets to protect them from security events to meet the entity's objectives.",
    "CC6.2": "Prior to issuing system credentials and granting system access, the entity registers and authorizes new internal and external users whose access is administered by the entity. For those users whose access is administered by the entity, user system credentials are removed when user access is no longer authorized.",
    "CC6.3": "The entity authorizes, modifies, or removes access to data, software, functions, and other protected information assets based on roles, responsibilities, or the system design and changes, giving consideration to the concepts of least privilege and segregation of duties, to meet the entity's objectives.",
    "CC6.4": "The entity restricts physical access to facilities and protected information assets (for example, data center facilities, backup media storage, and other sensitive locations) to authorized personnel to meet the entity's objectives.",
    "CC6.5": "The entity discontinues logical and physical protections over physical assets only after the ability to read or recover data and software from those assets has been diminished and is no longer required to meet the entity's objectives.",
    "CC6.6": "The entity implements logical access security measures to protect against threats from sources outside its system boundaries.",
    "CC6.7": "The entity restricts the transmission, movement, and removal of information to authorized internal and external users and processes, and protects it during transmission, movement, or removal to meet the entity's objectives.",
    "CC6.8": "The entity implements controls to prevent or detect and act upon the introduction of unauthorized or malicious software to meet the entity's objectives.",

    # System Operations
    "CC7.1": "To meet its objectives, the entity uses detection and monitoring procedures to identify (1) changes to configurations that result in the introduction of new vulnerabilities, and (2) susceptibilities to newly discovered vulnerabilities.",
    "CC7.2": "The entity monitors system components and the operation of those components for anomalies that are indicative of malicious acts, natural disasters, and errors affecting the entity's ability to meet its objectives; anomalies are analyzed to determine whether they represent security events.",
    "CC7.3": "The entity evaluates security events to determine whether they could or have resulted in a failure of the entity to meet its objectives (security incidents) and, if so, takes actions to prevent or address such failures.",
    "CC7.4": "The entity responds to identified security incidents by executing a defined incident-response program to understand, contain, remediate, and communicate security incidents, as appropriate.",
    "CC7.5": "The entity identifies, develops, and implements activities to recover from identified security incidents.",

    # Change Management
    "CC8.1": "The entity authorizes, designs, develops or acquires, configures, documents, tests, approves, and implements changes to infrastructure, data, software, and procedures to meet its objectives.",

    # Risk Mitigation
    "CC9.1": "The entity identifies, selects, and develops risk mitigation activities for risks arising from potential business disruptions.",
    "CC9.2": "The entity assesses and manages risks associated with vendors and business partners.",

    # Availability
    "A1.1": "The entity maintains, monitors, and evaluates current processing capacity and use of system components (infrastructure, data, and software) to manage capacity demand and to enable the implementation of additional capacity to help meet its objectives.",
    "A1.2": "The entity authorizes, designs, develops or acquires, implements, operates, approves, maintains, and monitors environmental protections, software, data backup processes, and recovery infrastructure to meet its objectives.",
    "A1.3": "The entity tests recovery plan procedures supporting system recovery to meet its objectives.",

    # Confidentiality
    "C1.1": "The entity identifies and maintains confidential information to meet the entity's objectives related to confidentiality.",
    "C1.2": "The entity disposes of confidential information to meet the entity's objectives related to confidentiality.",

    # Processing Integrity
    "PI1.1": "The entity obtains or generates, uses, and communicates relevant, quality information regarding the objectives related to processing, including definitions of data processed and product and service specifications, to support the use of products and services.",
    "PI1.2": "The entity implements policies and procedures over system inputs, including controls over completeness and accuracy, to result in products, services, and reporting to meet the entity's objectives.",
    "PI1.3": "The entity implements policies and procedures over system processing to result in products, services, and reporting to meet the entity's objectives.",
    "PI1.4": "The entity implements policies and procedures to make available or deliver output completely, accurately, and timely in accordance with specifications to meet the entity's objectives.",
    "PI1.5": "The entity implements policies and procedures to store inputs, items in processing, and outputs completely, accurately, and timely in accordance with system specifications to meet the entity's objectives.",

    # Privacy
    "P1.1": "The entity provides notice to data subjects about its privacy practices to meet the entity's objectives related to privacy. The notice is updated and communicated to data subjects in a timely manner for changes to the entity's privacy practices, including changes in the use of personal information, to meet the entity's objectives related to privacy.",
    "P2.1": "The entity communicates choices available regarding the collection, use, retention, disclosure, and disposal of personal information to the data subjects and the consequences, if any, of each choice. Explicit consent for the collection, use, retention, disclosure, and disposal of personal information is obtained from data subjects or other authorized persons, if required.",
    "P3.1": "Personal information is collected consistent with the entity's objectives related to privacy.",
    "P3.2": "For information requiring explicit consent, the entity communicates the need for such consent as well as the consequences of a failure to provide consent for the request for personal information and obtains the consent prior to the collection of the information to meet the entity's objectives related to privacy.",
    "P4.1": "The entity limits the use of personal information to the purposes identified in the entity's objectives related to privacy.",
    "P4.2": "The entity retains personal information consistent with the entity's objectives related to privacy.",
    "P4.3": "The entity securely disposes of personal information to meet the entity's objectives related to privacy.",
    "P5.1": "The entity grants identified and authenticated data subjects the ability to access their stored personal information for review and, upon request, provides physical or electronic copies of that information to data subjects to meet the entity's objectives related to privacy.",
    "P5.2": "The entity corrects, amends, or appends personal information based on information provided by data subjects and communicates such information to third parties, as committed or required, to meet the entity's objectives related to privacy.",
    "P6.1": "The entity discloses personal information to third parties with the explicit consent of data subjects and such consent is obtained prior to disclosure to meet the entity's objectives related to privacy.",
    "P6.2": "The entity creates and retains a complete, accurate, and timely record of authorized disclosures of personal information to meet the entity's objectives related to privacy.",
    "P6.3": "The entity creates and retains a complete, accurate, and timely record of detected or reported unauthorized disclosures (including breaches) of personal information to meet the entity's objectives related to privacy.",
    "P6.4": "The entity obtains privacy commitments from vendors and other third parties who have access to personal information to meet the entity's objectives related to privacy. The entity assesses those parties' compliance on a periodic and as-needed basis and takes corrective action, if necessary.",
    "P6.5": "The entity obtains commitments from vendors and other third parties with access to personal information to notify the entity in the event of actual or suspected unauthorized disclosures of personal information. Such notifications are reported to appropriate personnel and acted on in accordance with established incident-response procedures to meet the entity's objectives related to privacy.",
    "P6.6": "The entity provides notification of breaches and incidents to affected data subjects, regulators, and others to meet the entity's objectives related to privacy.",
    "P6.7": "The entity provides data subjects with an accounting of the personal information held and disclosure of the data subjects' personal information, upon the data subjects' request, to meet the entity's objectives related to privacy.",
    "P7.1": "The entity collects and maintains accurate, up-to-date, complete, and relevant personal information to meet the entity's objectives related to privacy.",
    "P8.1": "The entity implements a process for receiving, addressing, resolving, and communicating the resolution of inquiries, complaints, and disputes from data subjects and others and periodically monitors compliance to meet the entity's objectives related to privacy. Corrections and other necessary actions related to identified deficiencies are made or taken in a timely manner.",
}

# ---------------------------------------------------------------------------
# Trust Service Categories — groups criteria codes by AICPA category
# ---------------------------------------------------------------------------

TSC_CATEGORIES = {
    "Control Environment":                  ["CC1.1", "CC1.2", "CC1.3", "CC1.4", "CC1.5"],
    "Communication and Information":        ["CC2.1", "CC2.2", "CC2.3"],
    "Risk Assessment":                      ["CC3.1", "CC3.2", "CC3.3", "CC3.4"],
    "Monitoring Activities":                ["CC4.1", "CC4.2"],
    "Control Activities":                   ["CC5.1", "CC5.2", "CC5.3"],
    "Logical and Physical Access Controls": ["CC6.1", "CC6.2", "CC6.3", "CC6.4", "CC6.5", "CC6.6", "CC6.7", "CC6.8"],
    "System Operations":                    ["CC7.1", "CC7.2", "CC7.3", "CC7.4", "CC7.5"],
    "Change Management":                    ["CC8.1"],
    "Risk Mitigation":                      ["CC9.1", "CC9.2"],
    "Availability":                         ["A1.1", "A1.2", "A1.3"],
    "Confidentiality":                      ["C1.1", "C1.2"],
    "Processing Integrity":                 ["PI1.1", "PI1.2", "PI1.3", "PI1.4", "PI1.5"],
    "Privacy":                              ["P1.1", "P2.1", "P3.1", "P3.2", "P4.1", "P4.2", "P4.3", "P5.1", "P5.2", "P6.1", "P6.2", "P6.3", "P6.4", "P6.5", "P6.6", "P6.7", "P7.1", "P8.1"],
}

# ---------------------------------------------------------------------------
# Full SOC 2 criteria reference (injected into GPT prompts)
# SOC2_CRITERIA_FULL is placed first in system prompts to enable prefix caching.
# ---------------------------------------------------------------------------

SOC2_CRITERIA_FULL = """
SOC 2 TRUST SERVICES CRITERIA — AICPA 2017 (2022 revised points of focus)
Complete reference of all 59 criteria codes and their descriptions.

CONTROL ENVIRONMENT (CC1)
CC1.1 — COSO Principle 1: The entity demonstrates a commitment to integrity and ethical values.
CC1.2 — COSO Principle 2: The board of directors demonstrates independence from management and exercises oversight of the development and performance of internal control.
CC1.3 — COSO Principle 3: Management establishes, with board oversight, structures, reporting lines, and appropriate authorities and responsibilities in the pursuit of objectives.
CC1.4 — COSO Principle 4: The entity demonstrates a commitment to attract, develop, and retain competent individuals in alignment with objectives.
CC1.5 — COSO Principle 5: The entity holds individuals accountable for their internal control responsibilities in the pursuit of objectives.

COMMUNICATION AND INFORMATION (CC2)
CC2.1 — COSO Principle 13: The entity obtains or generates and uses relevant, quality information to support the functioning of internal control.
CC2.2 — COSO Principle 14: The entity internally communicates information, including objectives and responsibilities for internal control, necessary to support the functioning of internal control.
CC2.3 — COSO Principle 15: The entity communicates with external parties regarding matters affecting the functioning of internal control.

RISK ASSESSMENT (CC3)
CC3.1 — COSO Principle 6: The entity specifies objectives with sufficient clarity to enable the identification and assessment of risks relating to objectives.
CC3.2 — COSO Principle 7: The entity identifies risks to the achievement of its objectives across the entity and analyzes risks as a basis for determining how the risks should be managed.
CC3.3 — COSO Principle 8: The entity considers the potential for fraud in assessing risks to the achievement of objectives.
CC3.4 — COSO Principle 9: The entity identifies and assesses changes that could significantly impact the system of internal control.

MONITORING ACTIVITIES (CC4)
CC4.1 — COSO Principle 16: The entity selects, develops, and performs ongoing and/or separate evaluations to ascertain whether the components of internal control are present and functioning.
CC4.2 — COSO Principle 17: The entity evaluates and communicates internal control deficiencies in a timely manner to those parties responsible for taking corrective action, including senior management and the board of directors, as appropriate.

CONTROL ACTIVITIES (CC5)
CC5.1 — COSO Principle 10: The entity selects and develops control activities that contribute to the mitigation of risks to the achievement of objectives to acceptable levels.
CC5.2 — COSO Principle 11: The entity also selects and develops general control activities over technology to support the achievement of objectives.
CC5.3 — COSO Principle 12: The entity deploys control activities through policies that establish what is expected and in procedures that put policies into action.

LOGICAL AND PHYSICAL ACCESS CONTROLS (CC6)
CC6.1 — The entity implements logical access security software, infrastructure, and architectures over protected information assets to protect them from security events to meet the entity's objectives.
CC6.2 — Prior to issuing system credentials and granting system access, the entity registers and authorizes new internal and external users whose access is administered by the entity. For those users whose access is administered by the entity, user system credentials are removed when user access is no longer authorized.
CC6.3 — The entity authorizes, modifies, or removes access to data, software, functions, and other protected information assets based on roles, responsibilities, or the system design and changes, giving consideration to the concepts of least privilege and segregation of duties, to meet the entity's objectives.
CC6.4 — The entity restricts physical access to facilities and protected information assets (for example, data center facilities, backup media storage, and other sensitive locations) to authorized personnel to meet the entity's objectives.
CC6.5 — The entity discontinues logical and physical protections over physical assets only after the ability to read or recover data and software from those assets has been diminished and is no longer required to meet the entity's objectives.
CC6.6 — The entity implements logical access security measures to protect against threats from sources outside its system boundaries.
CC6.7 — The entity restricts the transmission, movement, and removal of information to authorized internal and external users and processes, and protects it during transmission, movement, or removal to meet the entity's objectives.
CC6.8 — The entity implements controls to prevent or detect and act upon the introduction of unauthorized or malicious software to meet the entity's objectives.

SYSTEM OPERATIONS (CC7)
CC7.1 — To meet its objectives, the entity uses detection and monitoring procedures to identify (1) changes to configurations that result in the introduction of new vulnerabilities, and (2) susceptibilities to newly discovered vulnerabilities.
CC7.2 — The entity monitors system components and the operation of those components for anomalies that are indicative of malicious acts, natural disasters, and errors affecting the entity's ability to meet its objectives; anomalies are analyzed to determine whether they represent security events.
CC7.3 — The entity evaluates security events to determine whether they could or have resulted in a failure of the entity to meet its objectives (security incidents) and, if so, takes actions to prevent or address such failures.
CC7.4 — The entity responds to identified security incidents by executing a defined incident-response program to understand, contain, remediate, and communicate security incidents, as appropriate.
CC7.5 — The entity identifies, develops, and implements activities to recover from identified security incidents.

CHANGE MANAGEMENT (CC8)
CC8.1 — The entity authorizes, designs, develops or acquires, configures, documents, tests, approves, and implements changes to infrastructure, data, software, and procedures to meet its objectives.

RISK MITIGATION (CC9)
CC9.1 — The entity identifies, selects, and develops risk mitigation activities for risks arising from potential business disruptions.
CC9.2 — The entity assesses and manages risks associated with vendors and business partners.

AVAILABILITY (A1)
A1.1 — The entity maintains, monitors, and evaluates current processing capacity and use of system components (infrastructure, data, and software) to manage capacity demand and to enable the implementation of additional capacity to help meet its objectives.
A1.2 — The entity authorizes, designs, develops or acquires, implements, operates, approves, maintains, and monitors environmental protections, software, data backup processes, and recovery infrastructure to meet its objectives.
A1.3 — The entity tests recovery plan procedures supporting system recovery to meet its objectives.

CONFIDENTIALITY (C1)
C1.1 — The entity identifies and maintains confidential information to meet the entity's objectives related to confidentiality.
C1.2 — The entity disposes of confidential information to meet the entity's objectives related to confidentiality.

PROCESSING INTEGRITY (PI1)
PI1.1 — The entity obtains or generates, uses, and communicates relevant, quality information regarding the objectives related to processing, including definitions of data processed and product and service specifications, to support the use of products and services.
PI1.2 — The entity implements policies and procedures over system inputs, including controls over completeness and accuracy, to result in products, services, and reporting to meet the entity's objectives.
PI1.3 — The entity implements policies and procedures over system processing to result in products, services, and reporting to meet the entity's objectives.
PI1.4 — The entity implements policies and procedures to make available or deliver output completely, accurately, and timely in accordance with specifications to meet the entity's objectives.
PI1.5 — The entity implements policies and procedures to store inputs, items in processing, and outputs completely, accurately, and timely in accordance with system specifications to meet the entity's objectives.

PRIVACY (P)
P1.1 — The entity provides notice to data subjects about its privacy practices to meet the entity's objectives related to privacy. The notice is updated and communicated to data subjects in a timely manner for changes to the entity's privacy practices, including changes in the use of personal information, to meet the entity's objectives related to privacy.
P2.1 — The entity communicates choices available regarding the collection, use, retention, disclosure, and disposal of personal information to the data subjects and the consequences, if any, of each choice. Explicit consent for the collection, use, retention, disclosure, and disposal of personal information is obtained from data subjects or other authorized persons, if required.
P3.1 — Personal information is collected consistent with the entity's objectives related to privacy.
P3.2 — For information requiring explicit consent, the entity communicates the need for such consent as well as the consequences of a failure to provide consent for the request for personal information and obtains the consent prior to the collection of the information to meet the entity's objectives related to privacy.
P4.1 — The entity limits the use of personal information to the purposes identified in the entity's objectives related to privacy.
P4.2 — The entity retains personal information consistent with the entity's objectives related to privacy.
P4.3 — The entity securely disposes of personal information to meet the entity's objectives related to privacy.
P5.1 — The entity grants identified and authenticated data subjects the ability to access their stored personal information for review and, upon request, provides physical or electronic copies of that information to data subjects to meet the entity's objectives related to privacy.
P5.2 — The entity corrects, amends, or appends personal information based on information provided by data subjects and communicates such information to third parties, as committed or required, to meet the entity's objectives related to privacy.
P6.1 — The entity discloses personal information to third parties with the explicit consent of data subjects and such consent is obtained prior to disclosure to meet the entity's objectives related to privacy.
P6.2 — The entity creates and retains a complete, accurate, and timely record of authorized disclosures of personal information to meet the entity's objectives related to privacy.
P6.3 — The entity creates and retains a complete, accurate, and timely record of detected or reported unauthorized disclosures (including breaches) of personal information to meet the entity's objectives related to privacy.
P6.4 — The entity obtains privacy commitments from vendors and other third parties who have access to personal information to meet the entity's objectives related to privacy. The entity assesses those parties' compliance on a periodic and as-needed basis and takes corrective action, if necessary.
P6.5 — The entity obtains commitments from vendors and other third parties with access to personal information to notify the entity in the event of actual or suspected unauthorized disclosures of personal information. Such notifications are reported to appropriate personnel and acted on in accordance with established incident-response procedures to meet the entity's objectives related to privacy.
P6.6 — The entity provides notification of breaches and incidents to affected data subjects, regulators, and others to meet the entity's objectives related to privacy.
P6.7 — The entity provides data subjects with an accounting of the personal information held and disclosure of the data subjects' personal information, upon the data subjects' request, to meet the entity's objectives related to privacy.
P7.1 — The entity collects and maintains accurate, up-to-date, complete, and relevant personal information to meet the entity's objectives related to privacy.
P8.1 — The entity implements a process for receiving, addressing, resolving, and communicating the resolution of inquiries, complaints, and disputes from data subjects and others and periodically monitors compliance to meet the entity's objectives related to privacy. Corrections and other necessary actions related to identified deficiencies are made or taken in a timely manner.
"""

# ---------------------------------------------------------------------------
# Incident type → SOC criteria mapping
#
# Grounded in AICPA guidance:
# - Unauthorized access / breaches → Security (CC6, CC7, CC9), Confidentiality,
#   Privacy (if PII involved)
# - Availability attacks → Availability (A1) + Security (CC7)
# - Data corruption → Processing Integrity + Availability + Security
# - Malware/Ransomware → Security + Availability + Confidentiality +
#   Processing Integrity + Privacy (if PII)
# - Supply chain → Vendor risk (CC9) + Change management (CC8) + Security
# - Risk assessment (CC3) included for high-impact incident types where
#   the event requires management to reassess risk posture
# ---------------------------------------------------------------------------

INCIDENT_SOC_MAP = {
    "data breach": {
        "trust_categories": ["Security", "Confidentiality", "Privacy"],
        "criteria": [
            "CC3.2",   # risk identification — breach may reveal unidentified risks
            "CC6.1",   # access controls failed or bypassed
            "CC6.6",   # external threat materialised
            "CC7.2",   # anomaly monitoring — was breach detected?
            "CC7.3",   # incident response triggered
            "CC7.4",   # incident classification and remediation
            "CC7.5",   # recovery from security incident
            "CC9.2",   # vendor risk — is this a third-party breach?
            "C1.1",    # confidentiality policies
            "P4.1",    # use of personal data
            "P4.2",    # retention and disposal of personal data
            "P4.3",    # secure disposal of personal data
            "P6.3",    # record of unauthorized disclosures / breaches
            "P6.6",    # breach notification to regulators and data subjects
        ],
        "notes": "Breaches involving personal data implicate Privacy criteria. "
                 "Significant breaches are system incidents requiring SOC report disclosure."
    },

    "unauthorized access": {
        "trust_categories": ["Security", "Confidentiality"],
        "criteria": [
            "CC3.2",
            "CC6.1",   # access controls
            "CC6.6",   # external threats
            "CC7.2",   # monitoring — was access detected?
            "CC7.3",   # incident response
            "CC7.4",   # remediation
            "CC7.5",   # recovery from security incident
            "CC9.2",   # third-party risk if vendor system accessed
            "C1.1",    # confidentiality policies
        ],
        "notes": "Confirmed unauthorized access is typically a system incident "
                 "requiring management action and potential SOC report disclosure."
    },

    "credential compromise": {
        "trust_categories": ["Security"],
        "criteria": [
            "CC6.1",   # access controls
            "CC6.2",   # user registration and authorization
            "CC6.3",   # access removal — compromised credentials need revoking
            "CC7.2",   # anomaly monitoring
            "CC7.4",   # remediation
            "CC7.5",   # recovery from security incident
        ],
        "notes": "Credential compromise with evidence of misuse escalates to "
                 "a system incident. Requires immediate access revocation (CC6.3)."
    },

    "data leak": {
        "trust_categories": ["Privacy", "Confidentiality", "Security"],
        "criteria": [
            "CC3.2",
            "CC6.7",   # transmission controls failed
            "CC7.2",   # anomaly detection
            "CC7.5",   # recovery from security incident
            "C1.1",    # confidentiality policies
            "C1.2",    # disposal of confidential information
            "P4.1",    # data use limits
            "P4.2",    # retention and disposal
            "P4.3",    # secure disposal of personal data
            "P6.1",    # third-party disclosure
            "P6.3",    # record of unauthorized disclosures
            "P6.6",    # breach notification
        ],
        "notes": "Accidental or intentional data leaks involving personal data "
                 "trigger Privacy criteria and may require breach notification."
    },

    "ransomware attack": {
        "trust_categories": ["Security", "Availability", "Confidentiality",
                              "Processing Integrity", "Privacy"],
        "criteria": [
            "CC3.2",   # risk assessment — ransomware forces risk reassessment
            "CC3.3",   # risk analysis
            "CC6.6",   # external threat
            "CC6.8",   # prevention / detection of malicious software
            "CC7.2",   # monitoring
            "CC7.3",   # incident response
            "CC7.4",   # remediation
            "CC7.5",   # recovery from security incident
            "CC9.1",   # risk mitigation for business disruption
            "A1.1",    # availability — systems may be unavailable
            "A1.3",    # recovery and business continuity
            "C1.1",    # confidentiality — data may be exfiltrated before encryption
            "PI1.1",   # processing integrity — data may be corrupted
            "PI1.3",   # processing integrity — system processing policies
        ],
        "notes": "Ransomware is almost always a system incident. Impacts multiple "
                 "trust categories simultaneously. High likelihood of SOC disclosure."
    },

    "malware infection": {
        "trust_categories": ["Security", "Availability", "Confidentiality",
                              "Processing Integrity"],
        "criteria": [
            "CC6.6",   # external threat
            "CC6.8",   # prevention / detection of malicious software
            "CC7.2",   # anomaly monitoring
            "CC7.3",   # incident response
            "CC7.4",   # remediation
            "CC7.5",   # recovery from security incident
            "A1.1",    # availability impact
            "A1.3",    # recovery
            "C1.1",    # confidentiality risk
            "PI1.1",   # processing integrity risk
        ],
        "notes": "Malware scope determines severity. Add Privacy criteria "
                 "if personal data systems are affected."
    },

    "exploited vulnerability": {
        "trust_categories": ["Security"],
        "criteria": [
            "CC3.3",   # risk analysis — known CVE means risk was identifiable
            "CC6.6",   # external threats
            "CC7.1",   # vulnerability detection — was this in monitoring scope?
            "CC7.4",   # remediation
            "CC7.5",   # recovery from security incident
            "CC8.1",   # change management — patching is a change
        ],
        "notes": "CISA KEV entries are actively exploited — treat as system incidents. "
                 "CC7.1 is key: was this vulnerability in the monitoring programme?"
    },

    "supply chain attack": {
        "trust_categories": ["Security", "Availability"],
        "criteria": [
            "CC3.2",   # risk identification — supply chain risk
            "CC3.3",   # risk analysis
            "CC8.1",   # change management — malicious update is a change
            "CC8.2",   # change testing and approval (legacy reference retained)
            "CC8.3",   # unauthorized change detection (legacy reference retained)
            "CC9.1",   # risk mitigation for business disruption
            "CC9.2",   # vendor and third-party risk — core criteria
            "CC7.4",   # remediation
            "CC7.5",   # recovery from security incident
            "CC6.6",   # external threat
            "CC6.8",   # prevention / detection of malicious software
            "A1.3",    # recovery if service disrupted
        ],
        "notes": "Supply chain attacks directly implicate CC9.2 (vendor risk). "
                 "Almost always a system incident requiring SOC disclosure."
    },

    "denial of service": {
        "trust_categories": ["Availability", "Security"],
        "criteria": [
            "A1.1",    # availability monitoring
            "A1.2",    # environmental protections
            "A1.3",    # recovery and business continuity
            "CC7.3",   # incident response
            "CC7.4",   # remediation
            "CC7.5",   # recovery from security incident
            "CC9.1",   # risk mitigation for business disruption
            "CC6.6",   # external threat
        ],
        "notes": "DoS/DDoS primarily impacts Availability criteria. "
                 "Significant service disruption is a system incident."
    },

    "phishing campaign": {
        "trust_categories": ["Security"],
        "criteria": [
            "CC6.1",   # access controls — phishing targets credentials
            "CC6.2",   # user authorization
            "CC6.8",   # malicious software / links
            "CC7.2",   # anomaly monitoring
            "CC7.3",   # incident response
            "CC7.5",   # recovery from security incident
        ],
        "notes": "Phishing detected early may be a system event only. "
                 "Successful phishing leading to access breach escalates to incident."
    },

    "insider threat": {
        "trust_categories": ["Security", "Confidentiality"],
        "criteria": [
            "CC3.2",
            "CC6.1",   # access controls
            "CC6.2",   # authorization — was access appropriate?
            "CC6.3",   # deprovisioning
            "CC7.2",   # anomaly monitoring — insider activity detection
            "CC7.5",   # recovery from security incident
            "CC9.2",   # if third-party personnel involved
            "C1.1",    # confidentiality policies
        ],
        "notes": "Insider threats directly test the effectiveness of CC6 access "
                 "controls and CC7.2 anomaly monitoring."
    },

    "api exposure": {
        "trust_categories": ["Security", "Confidentiality"],
        "criteria": [
            "CC6.1",   # access controls on API
            "CC6.6",   # external threat
            "CC6.7",   # transmission of information
            "CC7.1",   # vulnerability detection
            "CC7.5",   # recovery from security incident
            "C1.1",    # confidentiality
        ],
        "notes": "Exposed APIs may leak confidential or personal data. "
                 "Assess whether data was actually accessed before classifying "
                 "as system event vs incident."
    },

    "other": {
        "trust_categories": ["Security"],
        "criteria": [
            "CC7.2",
            "CC7.4",
        ],
        "notes": "Review incident details to determine full criteria impact."
    },
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_criteria_for_incident_type(incident_type: str) -> list[str]:
    """
    Returns the list of SOC 2 criteria codes for a given incident type.
    Falls back to 'other' if the type isn't in the map.
    """
    key = incident_type.lower().strip()
    mapping = INCIDENT_SOC_MAP.get(key, INCIDENT_SOC_MAP["other"])
    return mapping["criteria"]


def get_trust_categories(incident_type: str) -> list[str]:
    """Returns the trust service categories affected by this incident type."""
    key = incident_type.lower().strip()
    mapping = INCIDENT_SOC_MAP.get(key, INCIDENT_SOC_MAP["other"])
    return mapping["trust_categories"]


def get_notes(incident_type: str) -> str:
    """Returns auditor guidance notes for this incident type."""
    key = incident_type.lower().strip()
    mapping = INCIDENT_SOC_MAP.get(key, INCIDENT_SOC_MAP["other"])
    return mapping.get("notes", "")


def criteria_as_json(incident_type: str) -> str:
    """Returns criteria list as a JSON string for DB storage."""
    return json.dumps(get_criteria_for_incident_type(incident_type))


# Security maps to all CC series categories (CC1–CC9)
_SECURITY_TSC_CATEGORIES = [
    "Control Environment",
    "Communication and Information",
    "Risk Assessment",
    "Monitoring Activities",
    "Control Activities",
    "Logical and Physical Access Controls",
    "System Operations",
    "Change Management",
    "Risk Mitigation",
]

_SCOPE_TO_TSC_CATEGORIES = {
    "Security":             _SECURITY_TSC_CATEGORIES,
    "Availability":         ["Availability"],
    "Confidentiality":      ["Confidentiality"],
    "Processing Integrity": ["Processing Integrity"],
    "Privacy":              ["Privacy"],
}


def get_criteria_for_scope(selected_categories: list[str]) -> list[str]:
    """
    Returns a flat, deduplicated list of criteria codes for the given TSC scope
    categories. Security (CC series) is always included.
    """
    tsc_keys: list[str] = list(_SECURITY_TSC_CATEGORIES)  # always include Security
    for cat in selected_categories:
        for key in _SCOPE_TO_TSC_CATEGORIES.get(cat, []):
            if key not in tsc_keys:
                tsc_keys.append(key)

    seen: set[str] = set()
    codes: list[str] = []
    for key in tsc_keys:
        for code in TSC_CATEGORIES.get(key, []):
            if code not in seen:
                seen.add(code)
                codes.append(code)
    return codes
