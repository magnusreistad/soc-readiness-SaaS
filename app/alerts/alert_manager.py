import os
import json
import smtplib


def _parse_json(val, default=None):
    if default is None:
        default = []
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return default
    return default
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

from app.utils.soc_mapper import SOC_LABELS

load_dotenv()

# ---------------------------------------------------------------------------
# Config from .env
# ---------------------------------------------------------------------------

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", 587))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM    = os.getenv("ALERT_EMAIL_FROM", SMTP_USER)
EMAIL_TO_RAW  = os.getenv("ALERT_EMAIL_TO", "")
EMAIL_TO      = [e.strip() for e in EMAIL_TO_RAW.split(",") if e.strip()]
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")

# ALERT_MODE controls email behaviour:
#   'digest'      → one summary email per run (recommended)
#   'individual'  → one email per incident (original behaviour)
ALERT_MODE = os.getenv("ALERT_MODE", "digest")

SEVERITY_COLORS = {
    "critical": "#A32D2D",
    "high":     "#854F0B",
    "medium":   "#185FA5",
    "low":      "#3B6D11",
    "unknown":  "#5F5E5A",
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def create_alert(vendor: str, article: dict, incident_id: int = None) -> bool:
    """
    Used in 'individual' mode — sends one alert per incident.
    In 'digest' mode this only prints to terminal; run_collector
    calls send_digest() once at the end of a run instead.
    """
    article = _normalise(article)
    print(_terminal_summary(vendor, article))

    if ALERT_MODE == "digest":
        print("  [alert] Digest mode — will send summary at end of run.")
        return True   # return True so incident is stored; digest handles sending

    email_ok = _send_individual_email(vendor, article, incident_id) if EMAIL_TO else False
    slack_ok = _send_slack(vendor, article, incident_id) if SLACK_WEBHOOK else False

    if not EMAIL_TO:
        print("  [alert] No ALERT_EMAIL_TO set — skipping email.")
    if not SLACK_WEBHOOK:
        print("  [alert] No SLACK_WEBHOOK_URL set — skipping Slack.")

    return email_ok or slack_ok


def send_digest(incidents: list[dict]) -> bool:
    """
    Sends one digest email (and Slack summary) covering all incidents
    from a single run. Call this from run_collector after the main loop.

    Each item in `incidents` should be:
        {
            vendor      : str,
            article     : dict (normalised article fields),
            incident_id : int or None,
        }
    """
    if not incidents:
        print("  [digest] No incidents to report.")
        return False

    # Sort by severity so critical/high appear first
    incidents_sorted = sorted(
        incidents,
        key=lambda x: SEVERITY_ORDER.get(x["article"].get("severity", "unknown"), 4)
    )

    email_ok = _send_digest_email(incidents_sorted) if EMAIL_TO else False
    slack_ok = _send_digest_slack(incidents_sorted) if SLACK_WEBHOOK else False

    if not EMAIL_TO:
        print("  [digest] No ALERT_EMAIL_TO set — skipping email.")
    if not SLACK_WEBHOOK:
        print("  [digest] No SLACK_WEBHOOK_URL set — skipping Slack.")

    return email_ok or slack_ok


# ---------------------------------------------------------------------------
# Digest email
# ---------------------------------------------------------------------------

def _send_digest_email(incidents: list[dict]) -> bool:
    count     = len(incidents)
    top_sev   = incidents[0]["article"].get("severity", "unknown")
    has_crit  = any(i["article"].get("severity") == "critical" for i in incidents)

    subject = (
        f"[{'CRITICAL' if has_crit else top_sev.upper()}] "
        f"Vendor Threat Digest — {count} incident{'s' if count > 1 else ''} detected"
    )

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_FROM
        msg["To"]      = ", ".join(EMAIL_TO)

        msg.attach(MIMEText(_digest_plain(incidents), "plain"))
        msg.attach(MIMEText(_digest_html(incidents),  "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        print(f"  [digest] Email sent to: {', '.join(EMAIL_TO)} ({count} incidents)")
        return True

    except Exception as e:
        print(f"  [digest] Email failed: {e}")
        return False


def _digest_plain(incidents: list[dict]) -> str:
    lines = [
        "VENDOR THREAT DIGEST",
        "=" * 60,
        f"Run time : {_now()}",
        f"Incidents: {len(incidents)}",
        "=" * 60,
    ]
    for i, item in enumerate(incidents, 1):
        a   = item["article"]
        soc = _format_soc_plain(a.get("soc_criteria", "[]"))
        lines += [
            "",
            f"{i}. {item['vendor']} — {a.get('severity','').upper()}",
            f"   Type    : {a.get('incident_type','N/A')}",
            f"   Title   : {a.get('title','')}",
            f"   Source  : {a.get('source','')}",
            f"   Link    : {a.get('link','')}",
            f"   AI note : {a.get('ai_reason','N/A')}",
            f"   SOC     : {soc or 'None identified'}",
        ]
        if item.get("incident_id"):
            lines.append(f"   ID      : {item['incident_id']}")
        lines.append("   " + "-" * 56)

    lines += ["", "Generated by Vendor Threat Monitor.", _now()]
    return "\n".join(lines)


def _digest_html(incidents: list[dict]) -> str:
    count    = len(incidents)
    has_crit = any(i["article"].get("severity") == "critical" for i in incidents)
    header_color = "#A32D2D" if has_crit else SEVERITY_COLORS.get(
        incidents[0]["article"].get("severity", "unknown"), "#5F5E5A"
    )

    cards_html = ""
    for item in incidents:
        a         = item["article"]
        color     = SEVERITY_COLORS.get(a.get("severity", "unknown"), "#5F5E5A")
        sev_text  = a.get("severity", "unknown").upper()
        soc_html  = _format_soc_html(a.get("soc_criteria", "[]"))
        inc_row   = (
            f"<tr><td style='color:#888;padding:3px 0;width:100px'>ID</td>"
            f"<td style='padding:3px 0'><code>{item['incident_id']}</code></td></tr>"
            if item.get("incident_id") else ""
        )

        cards_html += f"""
<div style="border:1px solid #e0e0dc;border-radius:8px;overflow:hidden;margin-bottom:16px;">
  <div style="background:{color};padding:14px 20px;display:flex;align-items:center;gap:12px;">
    <span style="color:#fff;font-size:16px;font-weight:500;">{item['vendor']}</span>
    <span style="background:rgba(255,255,255,0.2);color:#fff;font-size:11px;font-weight:500;
                 padding:2px 10px;border-radius:20px;letter-spacing:0.06em;">{sev_text}</span>
  </div>
  <div style="padding:14px 20px 0;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr><td style="color:#888;padding:3px 0;width:100px">Incident type</td>
          <td style="padding:3px 0">{a.get('incident_type') or '—'}</td></tr>
      <tr><td style="color:#888;padding:3px 0">Source</td>
          <td style="padding:3px 0">{a.get('source','')}</td></tr>
      {inc_row}
    </table>
  </div>
  <div style="padding:10px 20px 0;">
    <a href="{a.get('link','')}" style="font-size:14px;color:#185FA5;text-decoration:none;
       font-weight:500;line-height:1.4;">{a.get('title','')}</a>
  </div>
  <div style="padding:8px 20px 0;">
    <span style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:0.06em;">
      AI assessment</span>
    <p style="margin:4px 0 0;font-size:13px;color:#333;line-height:1.5;">
      {a.get('ai_reason') or '—'}</p>
  </div>
  <div style="padding:8px 20px 14px;">
    <span style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:0.06em;">
      SOC criteria</span>
    <div style="margin-top:6px;">{soc_html}</div>
  </div>
</div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:system-ui,-apple-system,sans-serif;background:#f5f5f3;
             margin:0;padding:24px;">
<div style="max-width:640px;margin:0 auto;">

  <!-- Header -->
  <div style="background:{header_color};border-radius:10px 10px 0 0;padding:20px 28px;">
    <p style="margin:0 0 4px;color:rgba(255,255,255,0.8);font-size:12px;
              text-transform:uppercase;letter-spacing:0.08em;">Vendor Threat Digest</p>
    <h1 style="margin:0;color:#fff;font-size:20px;font-weight:500;">
      {count} Incident{'s' if count > 1 else ''} Detected</h1>
    <p style="margin:6px 0 0;color:rgba(255,255,255,0.75);font-size:13px;">{_now()}</p>
  </div>

  <!-- Cards -->
  <div style="background:#fff;border:1px solid #e0e0dc;border-top:none;
              border-radius:0 0 10px 10px;padding:20px;">
    {cards_html}
  </div>

  <!-- Footer -->
  <p style="margin:12px 0 0;font-size:12px;color:#999;text-align:center;">
    Generated by Vendor Threat Monitor · {_now()}</p>

</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Digest Slack
# ---------------------------------------------------------------------------

def _send_digest_slack(incidents: list[dict]) -> bool:
    try:
        count = len(incidents)
        attachments = []
        for item in incidents:
            a     = item["article"]
            color = SEVERITY_COLORS.get(a.get("severity", "unknown"), "#5F5E5A")
            soc   = _format_soc_plain(a.get("soc_criteria", "[]"))
            attachments.append({
                "color": color,
                "fields": [
                    {"title": "Vendor",       "value": item["vendor"],                            "short": True},
                    {"title": "Severity",      "value": a.get("severity","").upper(),               "short": True},
                    {"title": "Type",          "value": a.get("incident_type","N/A"),               "short": True},
                    {"title": "Source",        "value": a.get("source",""),                        "short": True},
                    {"title": "Article",       "value": f"<{a.get('link','')}|{a.get('title','')}>", "short": False},
                    {"title": "SOC criteria",  "value": soc or "None identified",                  "short": False},
                ],
            })

        payload = {
            "text": f":rotating_light: *Vendor Threat Digest — {count} incident{'s' if count > 1 else ''} detected* · {_now()}",
            "attachments": attachments,
        }

        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            SLACK_WEBHOOK, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status == 200
        if ok:
            print(f"  [digest] Slack sent ({count} incidents).")
        return ok

    except Exception as e:
        print(f"  [digest] Slack failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Individual email (used when ALERT_MODE=individual)
# ---------------------------------------------------------------------------

def _send_individual_email(vendor: str, article: dict, incident_id: int = None) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{article['severity'].upper()}] Vendor Security Alert — {vendor}"
        msg["From"]    = EMAIL_FROM
        msg["To"]      = ", ".join(EMAIL_TO)
        msg.attach(MIMEText(_email_plain(vendor, article, incident_id), "plain"))
        msg.attach(MIMEText(_email_html(vendor, article, incident_id),  "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        print(f"  [alert] Email sent to: {', '.join(EMAIL_TO)}")
        return True
    except Exception as e:
        print(f"  [alert] Email failed: {e}")
        return False


def _email_plain(vendor: str, article: dict, incident_id: int = None) -> str:
    soc   = _format_soc_plain(article["soc_criteria"])
    lines = [
        "VENDOR SECURITY ALERT", "=" * 50,
        f"Vendor:         {vendor}",
        f"Severity:       {article['severity'].upper()}",
        f"Incident type:  {article['incident_type'] or 'N/A'}",
        f"Detected:       {_now()}", "",
        f"Title:    {article['title']}",
        f"Source:   {article['source']}",
        f"Link:     {article['link']}", "",
        "Summary:", article["summary"] or "(no summary available)", "",
        "AI assessment:", article["ai_reason"] or "(not assessed)", "",
        "SOC criteria affected:", soc or "  None identified", "", "-" * 50,
    ]
    if incident_id:
        lines.append(f"Incident ID: {incident_id}")
    lines.append("Generated by Vendor Threat Monitor.")
    return "\n".join(lines)


def _email_html(vendor: str, article: dict, incident_id: int = None) -> str:
    color    = SEVERITY_COLORS.get(article["severity"], "#5F5E5A")
    sev_text = article["severity"].upper()
    soc_html = _format_soc_html(article["soc_criteria"])
    summary  = article["summary"] or "<em>No summary available.</em>"
    reason   = article["ai_reason"] or "<em>Not assessed.</em>"
    inc_row  = (
        f"<tr><td style='color:#888;padding:4px 0'>Incident ID</td>"
        f"<td style='padding:4px 0'><code>{incident_id}</code></td></tr>"
        if incident_id else ""
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:system-ui,-apple-system,sans-serif;background:#f5f5f3;margin:0;padding:24px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;
            overflow:hidden;border:1px solid #e0e0dc;">
  <div style="background:{color};padding:20px 28px;">
    <p style="margin:0 0 4px;color:rgba(255,255,255,0.8);font-size:12px;
              text-transform:uppercase;letter-spacing:0.08em;">Vendor Security Alert</p>
    <h1 style="margin:0;color:#fff;font-size:20px;font-weight:500;">{vendor}</h1>
    <span style="display:inline-block;margin-top:8px;background:rgba(255,255,255,0.2);
                 color:#fff;font-size:11px;font-weight:500;padding:3px 10px;
                 border-radius:20px;letter-spacing:0.06em;">{sev_text}</span>
  </div>
  <div style="padding:20px 28px 0;">
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr><td style="color:#888;padding:4px 0;width:130px">Incident type</td>
          <td style="padding:4px 0">{article['incident_type'] or '—'}</td></tr>
      <tr><td style="color:#888;padding:4px 0">Source</td>
          <td style="padding:4px 0">{article['source']}</td></tr>
      <tr><td style="color:#888;padding:4px 0">Detected</td>
          <td style="padding:4px 0">{_now()}</td></tr>
      {inc_row}
    </table>
  </div>
  <div style="padding:16px 28px 0;">
    <p style="margin:0 0 6px;font-size:13px;color:#888;text-transform:uppercase;
              letter-spacing:0.06em;">Article</p>
    <a href="{article['link']}" style="font-size:15px;color:#185FA5;text-decoration:none;
       font-weight:500;">{article['title']}</a>
  </div>
  <div style="padding:16px 28px 0;">
    <p style="margin:0 0 6px;font-size:13px;color:#888;text-transform:uppercase;
              letter-spacing:0.06em;">Summary</p>
    <p style="margin:0;font-size:14px;color:#333;line-height:1.6;">{summary}</p>
  </div>
  <div style="padding:16px 28px 0;">
    <p style="margin:0 0 6px;font-size:13px;color:#888;text-transform:uppercase;
              letter-spacing:0.06em;">AI assessment</p>
    <p style="margin:0;font-size:14px;color:#333;line-height:1.6;">{reason}</p>
  </div>
  <div style="padding:16px 28px 20px;">
    <p style="margin:0 0 8px;font-size:13px;color:#888;text-transform:uppercase;
              letter-spacing:0.06em;">SOC criteria affected</p>
    {soc_html}
  </div>
  <div style="background:#f5f5f3;padding:14px 28px;border-top:1px solid #e0e0dc;">
    <p style="margin:0;font-size:12px;color:#999;">
      Generated by Vendor Threat Monitor · {_now()}</p>
  </div>
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# Slack individual
# ---------------------------------------------------------------------------

def _send_slack(vendor: str, article: dict, incident_id: int = None) -> bool:
    try:
        color   = SEVERITY_COLORS.get(article["severity"], "#5F5E5A")
        sev     = article["severity"].upper()
        soc_txt = _format_soc_plain(article["soc_criteria"])

        payload = {
            "text": f":rotating_light: *Vendor Security Alert — {vendor}* [{sev}]",
            "attachments": [{
                "color": color,
                "fields": [
                    {"title": "Vendor",        "value": vendor,                              "short": True},
                    {"title": "Severity",       "value": sev,                                 "short": True},
                    {"title": "Incident type",  "value": article["incident_type"] or "N/A",  "short": True},
                    {"title": "Source",         "value": article["source"],                   "short": True},
                    {"title": "Article",        "value": f"<{article['link']}|{article['title']}>", "short": False},
                    {"title": "AI assessment",  "value": article["ai_reason"] or "N/A",      "short": False},
                    {"title": "SOC criteria",   "value": soc_txt or "None identified",        "short": False},
                ],
                "footer": f"Vendor Threat Monitor{' · ID: ' + str(incident_id) if incident_id else ''}",
                "ts": int(datetime.now(timezone.utc).timestamp()),
            }],
        }

        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(
            SLACK_WEBHOOK, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status == 200
        if ok:
            print("  [alert] Slack notification sent.")
        return ok

    except Exception as e:
        print(f"  [alert] Slack failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Shared formatting helpers
# ---------------------------------------------------------------------------

def _normalise(article: dict) -> dict:
    defaults = {
        "title": "(no title)", "link": "", "source": "Unknown",
        "summary": "", "severity": "unknown", "incident_type": "",
        "ai_reason": "", "soc_criteria": "[]",
    }
    return {**defaults, **article}


def _format_soc_plain(soc_json) -> str:
    try:
        criteria = _parse_json(soc_json)
        if not criteria:
            return ""
        return "  " + ", ".join(
            f"{c}" + (f" ({SOC_LABELS[c]})" if c in SOC_LABELS else "")
            for c in criteria
        )
    except Exception:
        return ""


def _format_soc_html(soc_json) -> str:
    try:
        criteria = _parse_json(soc_json)
        if not criteria:
            return "<p style='margin:0;font-size:14px;color:#888;'>None identified</p>"
        items = []
        for c in criteria:
            label = SOC_LABELS.get(c, "")
            desc  = f" <span style='color:#888;'>— {label}</span>" if label else ""
            items.append(
                f"<span style='display:inline-block;background:#E6F1FB;color:#0C447C;"
                f"font-size:12px;font-weight:500;padding:3px 10px;border-radius:20px;"
                f"margin:2px 4px 2px 0;'>{c}</span>{desc}"
            )
        return "<div style='line-height:2;'>" + "".join(items) + "</div>"
    except Exception:
        return "<p style='margin:0;font-size:14px;color:#888;'>None identified</p>"


def _terminal_summary(vendor: str, article: dict) -> str:
    sev = article["severity"].upper()
    return (
        f"\n{'='*60}\n"
        f"  VENDOR SECURITY ALERT\n"
        f"{'='*60}\n"
        f"  Vendor:   {vendor}\n"
        f"  Severity: {sev}\n"
        f"  Title:    {article['title']}\n"
        f"  Source:   {article['source']}\n"
        f"  Link:     {article['link']}\n"
        f"{'='*60}"
    )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")