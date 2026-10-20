"""Display elapsed days without hiding a comparison window boundary."""

from datetime import timedelta
from math import ceil, floor


def display_delay_days(delay: timedelta, minimum_days: int, maximum_days: int) -> float:
    days = delay.total_seconds() / 86400
    if delay < timedelta(days=minimum_days):
        return floor(days * 1000) / 1000
    if delay > timedelta(days=maximum_days):
        return ceil(days * 1000) / 1000
    return round(days, 3)
