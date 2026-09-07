import re
from functools import lru_cache


@lru_cache(maxsize=None)
def term_pattern(term):
    """Compile a filter term into a case-insensitive, whole-word regular expression.

    The term itself is matched literally (``re.escape``), so characters such as
    ``+``, ``[`` or ``|`` never act as regex syntax. When the term starts or
    ends with a letter or digit, that edge must sit on a word boundary, so
    ``EN`` matches ``EN - Series``, ``[EN]`` or ``Movies EN`` but not
    ``Documentary`` or ``General``. An edge that is a symbol (``FR -``,
    ``[EN]``) is matched exactly where it is written.
    """
    # [^\W_] is "a letter or digit": unlike \w it does not count the underscore,
    # so EN still matches EN_MOVIES or EN_US
    pattern = re.escape(term)
    if term[0].isalnum():
        pattern = r'(?<![^\W_])' + pattern
    if term[-1].isalnum():
        pattern = pattern + r'(?![^\W_])'
    return re.compile(pattern, flags=re.IGNORECASE)


def term_in_text(text, terms):
    """Return True when any of ``terms`` is found in ``text`` (see ``term_pattern``)."""
    if not text or not terms:
        return False
    return any(term_pattern(term).search(text) for term in terms if term)


def filter_entry(entry, INCLUDE_TERM=None, EXCLUDE_TERM=None):
    """Decide whether an entry should be dropped by INCLUDE_TERMS / EXCLUDE_TERMS.

    The raw (pre SCRUB_HEADER) ``group-title``, the ``tvg-name`` and the
    ``#EXTGRP`` line are all checked. When INCLUDE_TERMS is set, an entry must
    match at least one include term to be kept. EXCLUDE_TERMS always wins, so
    an entry matching both an include and an exclude term is dropped.

    Returns True when the entry should be excluded.
    """
    fields = [
        entry.get('group-title', ''),
        entry.get('tvg-name', ''),
        entry.get('extgrp', ''),
    ]
    fields = [field for field in fields if field]

    if INCLUDE_TERM and not any(term_in_text(field, INCLUDE_TERM) for field in fields):
        return True
    if EXCLUDE_TERM and any(term_in_text(field, EXCLUDE_TERM) for field in fields):
        return True
    return False


def parse_m3u_file(m3u_file_path, clean_group_title, process_value, REPLACE_TERMS, REPLACE_DEFAULTS, SCRUB_HEADER,
                   SCRUB_DEFAULTS, REMOVE_TERMS, REMOVE_DEFAULTS, EXCLUDE_TERM, INCLUDE_TERM=None,
                   filter_live_tv=False):
    """Parse the combined m3u file into a list of entry dictionaries.

    Each ``#EXTINF`` line (plus an optional ``#EXTGRP`` line and its stream
    URL) becomes one dictionary. Entries matching the INCLUDE_TERMS /
    EXCLUDE_TERMS filters are kept in the list but flagged with
    ``exclude=True`` so that no .strm file is written for them. Live TV
    entries are only flagged when ``filter_live_tv`` is True.

    Returns a ``(entries, errors)`` tuple.
    """
    try:
        with open(m3u_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    i = 0
    total_lines = len(lines)
    parsed_dictionaries = []
    errors = []
    INCLUDE_TERM = INCLUDE_TERM or []
    EXCLUDE_TERM = EXCLUDE_TERM or []

    while i < total_lines:
        line = lines[i].strip()

        # Check if the line starts with #EXTINF
        if line.startswith("#EXTINF"):
            try:
                # Extract key=value pairs from the #EXTINF line and remove header value(s)
                key_value_pairs = extract_key_value_pairs(line)

                # Check if the next line is #EXTGRP or a URL
                if i + 1 < total_lines and lines[i + 1].startswith("#EXTGRP"):
                    key_value_pairs['extgrp'] = lines[i + 1].strip()
                    i += 1  # Move to the next line

                # Check if the next line is a URL
                if i + 1 < total_lines and not lines[i + 1].startswith("#EXTINF"):
                    key_value_pairs['stream_url'] = lines[i + 1].strip()
                    i += 1  # Move to the next line

                # Apply INCLUDE_TERMS / EXCLUDE_TERMS against the raw values, before SCRUB_HEADER
                filtered = filter_entry(key_value_pairs, INCLUDE_TERM, EXCLUDE_TERM)

                if 'group-title' in key_value_pairs:
                    key_value_pairs['group-title'] = process_value(key_value_pairs['group-title'],
                                                                   remove_header=SCRUB_DEFAULTS)
                    key_value_pairs['group-title'] = process_value(key_value_pairs['group-title'],
                                                                   remove_header=SCRUB_HEADER)
                    key_value_pairs['group-title'] = process_value(key_value_pairs['group-title'],
                                                                   replace=REPLACE_DEFAULTS)
                    key_value_pairs['group-title'] = process_value(key_value_pairs['group-title'],
                                                                   replace=REPLACE_TERMS)

                clean_group_title(key_value_pairs, REMOVE_TERMS, REMOVE_DEFAULTS)

                if filtered and (filter_live_tv or not key_value_pairs.get('livetv')):
                    key_value_pairs['exclude'] = True

                parsed_dictionaries.append(key_value_pairs)

            except Exception as e:
                error_message = f"Error processing line: {line}\nError: {e}"
                print(error_message)
                errors.append(error_message)

        i += 1

    return parsed_dictionaries, errors


def extract_key_value_pairs(line):
    # Define the regular expression pattern for key=value pairs
    pattern = r'(\w[\w-]*?)="(.*?)"'

    # Find all matches in the string
    matches = re.finditer(pattern, line)

    result = {}
    last_end = 0
    last_key = None

    for match in matches:
        key = match.group(1).strip()
        value = match.group(2).strip()
        result[key] = value

        if last_key is not None:
            # Add any text between the previous key-value pair and this key-value pair to the last key's value
            result[last_key] += line[last_end:match.start()].strip()
        last_key = key
        last_end = match.end()

    if last_key is not None:
        # Add any remaining text to the last key's value
        result[last_key] += line[last_end:].strip()

    # Extract EXTINF line
    extinf_match = re.search(r'^#EXTINF:.+$', line)
    if extinf_match:
        result['extinf_line'] = extinf_match.group(0)

    # Extract duration from #EXTINF line
    duration_match = re.search(r'^#EXTINF:(-?\d*)\s', line)
    if duration_match:
        duration = duration_match.group(1)
        result['duration'] = duration if duration else ''
    # Extract resolution from #EXTINF line
    resolution_match = re.search(r'.*?\b(HD|SD)\s*', line)
    if resolution_match:
        result['resolution'] = resolution_match.group(1)

    return result
