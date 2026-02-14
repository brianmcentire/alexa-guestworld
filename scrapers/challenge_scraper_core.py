"""Shared parsing logic for the weekly challenge routes scraper.

Pure functions — no AWS or network calls.
"""

import re

from bs4 import BeautifulSoup

# SSML phonetic overrides for route/climb names that Alexa's default TTS
# mispronounces.  Maps exact name strings to SSML <phoneme> tags.
PHONETIC_OVERRIDES = {
    "Cote de la Redoute": '<phoneme alphabet="ipa" ph="koʊt də la ʁəˈdut">Cote de la Redoute</phoneme>',
    "Côte de la Redoute": '<phoneme alphabet="ipa" ph="koʊt də la ʁəˈdut">Côte de la Redoute</phoneme>',
    "Côte de Pike": '<phoneme alphabet="ipa" ph="koʊt də paɪk">Côte de Pike</phoneme>',
    "Bealach na Bà": '<phoneme alphabet="ipa" ph="ˈbjaləx nə ˈbɑː">Bealach na Bà</phoneme>',
    "La Laguna Negra": '<phoneme alphabet="ipa" ph="la laˈɡuna ˈneɡɾa">La Laguna Negra</phoneme>',
    "Côte de Domancy": '<phoneme alphabet="ipa" ph="koʊt də doˈmɑ̃si">Côte de Domancy</phoneme>',
    "Puy de Dôme": '<phoneme alphabet="ipa" ph="pɥi də doʊm">Puy de Dôme</phoneme>',
    "L'Alpe du Zwift": '<phoneme alphabet="ipa" ph="lalp dy zwɪft">L\'Alpe du Zwift</phoneme>',
    "Lagunas de Fuente de Piedra": '<phoneme alphabet="ipa" ph="laˈɡunas de ˈfwente de ˈpjedɾa">Lagunas de Fuente de Piedra</phoneme>',
}

_XP_PATTERN = re.compile(r'^(.+?)\s*\((\d+)\s*XP\)$')


def parse_challenge_calendar_html(html_content):
    """Parse challenge calendar HTML and return per-day challenge data.

    Args:
        html_content: raw HTML string or bytes from the challenges calendar page.

    Returns:
        Sorted list of (day_number, {"route": {...}, "climb": {...}}) tuples.
        Each entry dict has keys: name, xp (int), detail_url (str or None).
        A day may have only "route", only "climb", or both.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", class_=lambda c: c and "calendar-table" in c)
    if table is None:
        return []

    cells = table.find_all("td", class_=lambda c: c and "day-with-date" in c)

    days = []
    for cell in cells:
        day_span = cell.find("span", class_=lambda c: c and "day-number" in c)
        if not day_span:
            continue

        day_num = int(day_span.get_text())
        challenges = {}

        # Each event is inside a <span class="calnk"> with an <a> link and
        # <span class="spiffy-title"> for the name+XP text.
        for event in cell.find_all("span", class_="calnk"):
            title_span = event.find("span", class_="spiffy-title")
            if not title_span:
                continue

            title_text = title_span.get_text(strip=True)
            m = _XP_PATTERN.match(title_text)
            if not m:
                continue

            name = m.group(1).strip()
            xp = int(m.group(2))

            # Get detail URL from the <a> tag
            link = event.find("a", href=True)
            detail_url = link["href"] if link else None

            # Classify as route or climb by CSS class or URL pattern
            category = _classify_challenge(event, detail_url)
            if category:
                entry = {"name": name, "xp": xp, "detail_url": detail_url}
                challenges[category] = entry

        if challenges:
            days.append((day_num, challenges))

    days.sort(key=lambda x: x[0])
    return days


def _classify_challenge(event_tag, detail_url):
    """Determine whether an event is a 'route' or 'climb'.

    Uses CSS category class first, falls back to URL pattern.
    """
    # Walk up to find an ancestor with a category class
    for parent in event_tag.parents:
        if parent is None:
            break
        classes = parent.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()
        for cls in classes:
            if "category_367" in cls:
                return "route"
            if "category_370" in cls:
                return "climb"

    # Also check the event tag itself and its descendants
    all_tags = [event_tag] + list(event_tag.find_all(True))
    for tag in all_tags:
        classes = tag.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()
        for cls in classes:
            if "category_367" in cls:
                return "route"
            if "category_370" in cls:
                return "climb"

    # Fallback: URL pattern
    if detail_url:
        if "/route/" in detail_url:
            return "route"
        if "/portal/" in detail_url:
            return "climb"

    return None


def parse_route_detail_page(html_content):
    """Extract distance and elevation from a route/climb detail page.

    Args:
        html_content: raw HTML string or bytes from a route detail page.

    Returns:
        Dict with distance_km, distance_mi, elevation_m, elevation_ft,
        or None if the data cannot be extracted.
    """
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, "html.parser")

    distance_km = None
    distance_mi = None
    elevation_m = None
    elevation_ft = None

    # Look for distance/elevation in common patterns:
    # "XX.X km (XX.X miles)" and "XXX m (X,XXX')" or "XXX m (XXX ft)"
    text = soup.get_text()

    # Distance pattern: "22.5 km (14.0 miles)" or "22.5km (14.0mi)"
    dist_match = re.search(
        r'([\d.]+)\s*km\s*\(\s*([\d.]+)\s*mi(?:les?)?\s*\)', text, re.IGNORECASE)
    if dist_match:
        distance_km = float(dist_match.group(1))
        distance_mi = float(dist_match.group(2))

    # Elevation pattern: "350 m (1,148')" or "350m (1148 ft)" or "350 m (1,148 ft)"
    elev_match = re.search(
        r'([\d,]+)\s*m\s*\(\s*([\d,]+)\s*(?:ft|\'|feet)\s*\)', text, re.IGNORECASE)
    if elev_match:
        elevation_m = float(elev_match.group(1).replace(",", ""))
        elevation_ft = float(elev_match.group(2).replace(",", ""))

    if distance_km is None and elevation_m is None:
        return None

    result = {}
    if distance_km is not None:
        result["distance_km"] = distance_km
        result["distance_mi"] = distance_mi
    if elevation_m is not None:
        result["elevation_m"] = elevation_m
        result["elevation_ft"] = elevation_ft
    return result


def build_challenge_json(days_by_month, route_details=None):
    """Merge per-day challenge data with route detail data into final JSON structure.

    Args:
        days_by_month: dict mapping month key ("2026-02") to list of
            (day_number, {"route": {...}, "climb": {...}}) tuples.
        route_details: dict mapping detail URL to parsed detail dict
            (from parse_route_detail_page). May be None.

    Returns:
        Dict structured as: { "2026-02": { "1": { "route": {...}, "climb": {...} }, ... } }
    """
    if route_details is None:
        route_details = {}

    result = {}
    for month_key, days in days_by_month.items():
        month_data = {}
        for day_num, challenges in days:
            day_entry = {}
            for category in ("route", "climb"):
                if category not in challenges:
                    continue
                ch = challenges[category]
                entry = {"name": ch["name"], "xp": ch["xp"]}

                # Add SSML phonetic override if available
                if ch["name"] in PHONETIC_OVERRIDES:
                    entry["name_ssml"] = PHONETIC_OVERRIDES[ch["name"]]

                # Merge route detail data (distance, elevation)
                detail_url = ch.get("detail_url")
                if detail_url and detail_url in route_details:
                    detail = route_details[detail_url]
                    if detail:
                        for key in ("distance_km", "distance_mi",
                                    "elevation_m", "elevation_ft"):
                            if key in detail:
                                entry[key] = detail[key]

                day_entry[category] = entry
            if day_entry:
                month_data[str(day_num)] = day_entry
        if month_data:
            result[month_key] = month_data
    return result
