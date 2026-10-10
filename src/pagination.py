"""Small, independent calculations for paging a filtered request list."""

from dataclasses import dataclass
from math import ceil

import pandas as pd


@dataclass
class RequestPage:
    rows: pd.DataFrame
    number: int
    pages: int
    first: int
    last: int


def paginate_requests(requests: pd.DataFrame, page: int, page_size: int) -> RequestPage:
    """Clamp a page safely, including when the matching list is empty."""
    if page_size < 1:
        raise ValueError("Rows per page must be positive.")
    pages = max(1, ceil(len(requests) / page_size))
    number = min(max(1, page), pages)
    start = (number - 1) * page_size
    rows = requests.iloc[start:start + page_size]
    return RequestPage(
        rows, number, pages, start + 1 if len(rows) else 0, start + len(rows),
    )
