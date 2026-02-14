"""Shared calendar-parsing logic for the guest world scraper.

Pure functions — no AWS or network calls.
"""

from bs4 import BeautifulSoup


def parse_calendar_html(html_content):
    """Parse schedule HTML and return a list of (day_number, [world_names]) tuples.

    Args:
        html_content: raw HTML string or bytes from the schedule page.

    Returns:
        Sorted list of (int, list[str]) tuples, one per calendar day that
        contains at least one world name.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", class_=lambda c: c and "calendar-table" in c)
    if table is None:
        return []

    cells = table.find_all("td", class_=lambda c: c and "day-with-date" in c)

    days = []
    for cell in cells:
        day_span = cell.find("span", class_=lambda c: c and "day-number" in c)
        world_spans = cell.find_all("span", class_="spiffy-title")
        if day_span and world_spans:
            day_num = int(day_span.get_text())
            worlds = [span.get_text() for span in world_spans]
            days.append((day_num, worlds))

    days.sort(key=lambda x: x[0])
    return days


def format_csv(days):
    """Format parsed calendar days into CSV string.

    Args:
        days: list of (day_number, [world_names]) as returned by
              parse_calendar_html().

    Returns:
        String with lines like "World1 and World2,N\\n" where N is a
        1-based incrementing counter.
    """
    lines = []
    for i, (_, worlds) in enumerate(days, start=1):
        lines.append(" and ".join(worlds) + "," + str(i))
    return "\n".join(lines) + "\n" if lines else ""
