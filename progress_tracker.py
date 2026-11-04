"""Pure view-model helpers for the progress tracker."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


DISPLAY_ZONE = ZoneInfo("Asia/Manila")
SHORT_GAP_THRESHOLD = timedelta(days=7)
MAX_GRID_CHECKS = 6

DOMAINS = (
    ("cardiovascular", "Heart"),
    ("general_burden", "Kidneys"),
    ("neuropathy_mobility", "Nerves & Feet"),
    ("retinopathy", "Eyes"),
)

STATUS_ORDER = {"Good": 0, "Check": 1, "See a doctor": 2}
STATUS_DETAILS = {
    "Good": {"icon": "✓", "key": "good"},
    "Check": {"icon": "!", "key": "check"},
    "See a doctor": {"icon": "!", "key": "doctor"},
    "Not available": {"icon": "–", "key": "neutral"},
}
RULE_STATUS_LABELS = {"Low": "Good", "Moderate": "Check", "High": "See a doctor"}


def to_display_datetime(value, display_zone=DISPLAY_ZONE):
    """Return a timestamp in the configured display timezone."""
    if isinstance(value, datetime):
        timestamp = value
    else:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(display_zone)


def format_time_label(value, now=None, include_year=False):
    """Format a short PHT label, adding the year when it is needed."""
    timestamp = to_display_datetime(value)
    reference = to_display_datetime(now or datetime.now(timezone.utc))
    format_string = (
        "%b %-d, %Y, %H:%M"
        if include_year or timestamp.year != reference.year
        else "%b %-d, %H:%M"
    )
    try:
        return timestamp.strftime(format_string)
    except ValueError:
        format_string = (
            "%b %#d, %Y, %H:%M"
            if include_year or timestamp.year != reference.year
            else "%b %#d, %H:%M"
        )
        return timestamp.strftime(format_string)


def _status(rule_result):
    label = RULE_STATUS_LABELS.get((rule_result or {}).get("label"), "Not available")
    details = STATUS_DETAILS[label]
    return {"label": label, **details}


def _record_view(record, now):
    timestamp = to_display_datetime(record["created_at"])
    return {
        "id": record.get("id"),
        "timestamp": timestamp,
        "timestamp_iso": timestamp.isoformat(),
        "time_label": format_time_label(timestamp, now),
        "full_time_label": timestamp.strftime("%Y-%m-%d %H:%M"),
        "archived": bool(record.get("archived", False)),
        "rule_results": record.get("rule_results") or {},
    }


def _gap_label(delta):
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes == 0:
        return "at the same time"
    if minutes < 5:
        return "a few minutes later"
    if minutes < 24 * 60:
        return "later that day"
    days = minutes // (24 * 60)
    if days < 14:
        return f"{days} day{'s' if days != 1 else ''} later"
    if days < 60:
        weeks = max(1, round(days / 7))
        return f"{weeks} week{'s' if weeks != 1 else ''} later"
    months = max(1, round(days / 30))
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} later"
    years = max(1, round(days / 365))
    return f"{years} year{'s' if years != 1 else ''} later"


def _sequence_description(title, entries):
    parts = []
    for entry in entries:
        archived = ", archived check" if entry["archived"] else ""
        parts.append(f"{entry['status']['label']} on {entry['full_time_label']} PHT{archived}")
    return f"{title} screening sequence: " + "; ".join(parts) + "."


def _summary_row(title, previous, current):
    previous_label = previous["status"]["label"]
    current_label = current["status"]["label"]
    if previous_label == "Not available" and current_label == "Not available":
        message = f"{title}: no result in either check, so there is nothing to compare."
    elif previous_label == "Not available":
        message = (
            f"{title}: {current_label} now. There was no result in your previous "
            "check, so there's nothing to compare."
        )
    elif current_label == "Not available":
        message = f"{title}: no result this time (it was {previous_label} before)."
    elif previous_label == current_label:
        message = f"{title}: No change, {current_label}."
    else:
        message = f"{title}: Moved from {previous_label} to {current_label}."
    return {
        "title": title,
        "message": message,
        "previous": previous["status"],
        "current": current["status"],
        "previous_date": previous["time_label"],
        "previous_full_date": previous["full_time_label"],
    }


def build_progress_view(records, include_archived=False, now=None):
    """Build all tracker display data without accessing Flask or the database."""
    reference_now = to_display_datetime(now or datetime.now(timezone.utc))
    ordered = sorted(
        (_record_view(record, reference_now) for record in records),
        key=lambda record: record["timestamp"],
    )
    include_year = len({record["timestamp"].year for record in ordered}) > 1
    if include_year:
        for record in ordered:
            record["time_label"] = format_time_label(
                record["timestamp"], reference_now, include_year=True
            )
    count = len(ordered)
    included_phrase = "including archived checks" if include_archived else "active checks only"

    timelines = []
    for category, title in DOMAINS:
        entries = []
        for index, record in enumerate(ordered):
            status = _status(record["rule_results"].get(category))
            gap = None
            short_gap = False
            if index:
                delta = record["timestamp"] - ordered[index - 1]["timestamp"]
                gap = _gap_label(delta)
                short_gap = delta < SHORT_GAP_THRESHOLD
            entries.append({
                "status": status,
                "timestamp": record["timestamp"],
                "timestamp_iso": record["timestamp_iso"],
                "time_label": record["time_label"],
                "full_time_label": record["full_time_label"],
                "archived": record["archived"],
                "gap_label": gap,
                "short_gap": short_gap,
            })
        timelines.append({
            "category": category,
            "title": title,
            "entries": entries,
            "sequence_description": _sequence_description(title, entries) if entries else "",
        })

    summary_rows = []
    short_gap_notice = False
    if count >= 2:
        previous, current = ordered[-2:]
        short_gap_notice = current["timestamp"] - previous["timestamp"] < SHORT_GAP_THRESHOLD
        for category, title in DOMAINS:
            summary_rows.append(_summary_row(
                title,
                {
                    "status": _status(previous["rule_results"].get(category)),
                    "time_label": previous["time_label"],
                    "full_time_label": previous["full_time_label"],
                },
                {"status": _status(current["rule_results"].get(category))},
            ))

    grid_records = list(reversed(ordered[-MAX_GRID_CHECKS:]))
    grid = []
    for record in grid_records:
        cells = []
        for category, _title in DOMAINS:
            cells.append(_status(record["rule_results"].get(category)))
        grid.append({
            "timestamp": record["timestamp"],
            "timestamp_iso": record["timestamp_iso"],
            "time_label": record["time_label"],
            "full_time_label": record["full_time_label"],
            "archived": record["archived"],
            "statuses": cells,
        })

    baseline = None
    if count == 1:
        baseline = {
            "date": ordered[0]["time_label"],
            "full_date": ordered[0]["full_time_label"],
            "timestamp_iso": ordered[0]["timestamp_iso"],
            "archived": ordered[0]["archived"],
            "statuses": [
                {
                    "title": title,
                    "status": _status(ordered[0]["rule_results"].get(category)),
                }
                for category, title in DOMAINS
            ],
        }

    return {
        "check_count": count,
        "domains": [{"category": category, "title": title} for category, title in DOMAINS],
        "included_phrase": included_phrase,
        "include_archived": include_archived,
        "summary_rows": summary_rows,
        "short_gap_notice": short_gap_notice,
        "grid": grid,
        "grid_start": min(MAX_GRID_CHECKS, count),
        "timelines": timelines,
        "baseline": baseline,
        "empty": count == 0,
    }
