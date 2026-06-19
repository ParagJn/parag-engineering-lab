from datetime import datetime


def format_date(iso_string: str) -> str:
    """Convert ISO datetime string to a human-readable format."""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%b %d, %Y %H:%M")
    except (ValueError, TypeError):
        return iso_string


def score_label(score: float) -> str:
    """Convert a numeric score to a descriptive label."""
    if score >= 8:
        return "Excellent"
    if score >= 6:
        return "Good"
    if score >= 4:
        return "Fair"
    return "Needs Improvement"


def calculate_overall_score(questions: list) -> float | None:
    """Calculate average score from evaluated questions."""
    evaluated = [q for q in questions if q.get("status") == "evaluated" and q.get("avg_score") is not None]
    if not evaluated:
        return None
    return round(sum(q["avg_score"] for q in evaluated) / len(evaluated), 1)
