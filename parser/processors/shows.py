import re

from .handlers import dedupe_key

YEAR_SUFFIX = re.compile(r'\s*\(((?:19|20)\d{2})\)\s*$')
COUNTRY_SUFFIX = re.compile(r'\s*\(([A-Z]{2})\)\s*$')


def split_show_title(title):
    """Split a show title into its base name, year and country tag.

    Trailing ``(YYYY)`` and ``(CC)`` country tags are peeled off in any order,
    so ``Acapulco (2021) (US)``, ``Acapulco (US) (2021)`` and ``Acapulco``
    all give the base ``Acapulco``; the first two also give the year
    ``2021`` and the country ``US``.
    """
    base = title.strip()
    year = ''
    country = ''
    while True:
        match = YEAR_SUFFIX.search(base)
        if match:
            year = year or match.group(1)
            base = base[:match.start()].rstrip()
            continue
        match = COUNTRY_SUFFIX.search(base)
        if match:
            country = country or match.group(1)
            base = base[:match.start()].rstrip()
            continue
        break
    return base, year, country


def merge_show_years(entries, enabled=True):
    """Give every provider's episodes of a show one folder name, with a year when known.

    Series and television entries are grouped by their show title with the
    year and country tag removed. Within a group:

    - one distinct year known: every member is renamed ``<base> (<year>)``,
      so a provider that lists ``Acapulco`` joins the provider that lists
      ``Acapulco (2021) (US)`` in the ``Acapulco (2021)`` folder;
    - no year known anywhere: members keep ``<base>`` with any country tag
      removed;
    - two or more different years (``Battlestar Galactica`` 1978 and 2004):
      members with a year keep their own ``<base> (<year>)`` and members
      without a year are left as ``<base>`` rather than guessed into either;
    - two or more different country tags (``The Office (US)`` and
      ``The Office (UK)``): these are different shows, so every member keeps
      its own country tag and year as ``<base> (<CC>) (<year>)`` and an
      untagged copy is left as ``<base>``.

    The base name comes from the first member seen, so the first listed
    provider decides spelling. Does nothing when ``enabled`` is False.
    """
    if not enabled:
        return entries

    groups = {}
    for entry in entries:
        title = entry.get('show_title')
        if not title or not (entry.get('series') or entry.get('television')):
            continue
        base, year, country = split_show_title(title)
        key = dedupe_key(base)
        group = groups.setdefault(key, {'base': base, 'years': set(), 'countries': set(), 'members': []})
        if year:
            group['years'].add(year)
        if country:
            group['countries'].add(country)
        group['members'].append((entry, year, country))

    for key, group in groups.items():
        base = group['base']
        years = group['years']
        if len(group['countries']) > 1:
            # Different country tags mean different shows: keep them apart and never guess a year
            for entry, year, country in group['members']:
                entry['show_title'] = base + (f" ({country})" if country else '') + (f" ({year})" if year else '')
            continue
        for entry, year, _country in group['members']:
            if len(years) == 1:
                entry['show_title'] = f"{base} ({next(iter(years))})"
            elif year:
                entry['show_title'] = f"{base} ({year})"
            else:
                entry['show_title'] = base
    return entries
