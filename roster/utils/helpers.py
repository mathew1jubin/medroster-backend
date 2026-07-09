# Helper functions for the roster app
from datetime import datetime, date

def parse_date(date_str: str) -> date:
    """Parses standard YYYY-MM-DD date strings."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None
