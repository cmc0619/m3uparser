import json
import os
from collections import Counter
from datetime import date

STATE_VERSION = 1


def today_str():
    """Today's date as ISO ``YYYY-MM-DD``."""
    return date.today().isoformat()


def empty_state():
    """A fresh, empty library state."""
    return {'version': STATE_VERSION, 'sources': {}, 'files': {}, 'shows': {}}


def load_state(state_file):
    """Load the library state JSON written by a previous run.

    The state remembers, per provider, how many entries its playlist held the
    last time it was trusted, per .strm file which provider supplied it and
    when it was last seen, and per show the year used for its folder. A missing or unreadable file yields an empty
    state, which makes the run behave exactly like the versions before state
    tracking existed.
    """
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return empty_state()
    if not isinstance(data, dict):
        return empty_state()
    return normalize_state(data)


def normalize_state(data):
    """Drop malformed sections and records so a damaged state file cannot stop a run.

    ``sources`` and ``files`` must be dicts of dicts, a file record's ``s``
    must be a list, and ``shows`` must map names to strings; anything else is
    discarded and treated as unknown.
    """
    for section in ('sources', 'files', 'shows'):
        if not isinstance(data.get(section), dict):
            data[section] = {}
    data['sources'] = {label: record for label, record in data['sources'].items() if isinstance(record, dict)}
    data['files'] = {path: record for path, record in data['files'].items()
                     if isinstance(record, dict) and isinstance(record.get('s', []), list)}
    data['shows'] = {key: year for key, year in data['shows'].items() if isinstance(year, str)}
    data['version'] = STATE_VERSION
    return data


def save_state(state_file, state):
    """Write the state atomically next to its final location."""
    directory = os.path.dirname(state_file)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    tmp_file = f'{state_file}.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, separators=(',', ':'), ensure_ascii=False)
    os.replace(tmp_file, state_file)


def judge_sources(state, sources, entries, min_source_ratio=0.5):
    """Decide, per configured provider, whether this run's playlist can be trusted.

    A provider is *present* when its playlist downloaded, produced at least
    one entry, and holds at least ``min_source_ratio`` of the entries it held
    the last time it was trusted. Anything else (download failure, empty
    body, a truncated list) marks it *absent*: its titles are left alone
    instead of being removed by CLEAN_SYNC.

    Returns ``{label: {'present', 'count', 'previous', 'reason'}}``.
    """
    counts = Counter(entry.get('source', '') for entry in entries)
    status = {}
    for source in sources:
        label = source['label']
        count = counts.get(label, 0)
        previous = state.get('sources', {}).get(label, {}).get('entries', 0) or 0
        if not source.get('downloaded'):
            present, reason = False, 'no playlist downloaded'
        elif count == 0:
            present, reason = False, 'playlist was empty'
        elif previous and count < min_source_ratio * previous:
            present, reason = False, f'only {count} entries, previous run had {previous}'
        else:
            present, reason = True, 'ok'
        status[label] = {'present': present, 'count': count, 'previous': previous, 'reason': reason}
    return status


def report_sources(status):
    """Print one line per provider describing how this run treated it."""
    for label, info in status.items():
        if info['present']:
            print(f"Source {label}: {info['count']} entries (previous {info['previous']})")
        else:
            print(f"Source {label}: {info['reason']} - its titles are kept until it returns")
            if info['count']:
                print(f"Source {label}: if the smaller playlist is genuine, lower MIN_SOURCE_RATIO or delete "
                      f"logs/library_state.json to accept it as the new baseline")


def relative_written(written, root_dir):
    """Map absolute written .strm paths to paths relative to ``root_dir``."""
    return {os.path.relpath(path, root_dir): label for path, label in written.items()}


def record_run(state, written, status, today=None):
    """Record this run's written files and the entry counts of trusted providers.

    ``written`` maps a relative .strm path to the provider label, or list of
    labels, that supplied it. A provider that was absent keeps its previous
    count so the next run still has a baseline to compare against.
    """
    today = today or today_str()
    files = state.setdefault('files', {})
    for rel_path, labels in written.items():
        if isinstance(labels, str):
            labels = [labels]
        files[rel_path] = {'s': [label for label in labels if label], 'd': today}
    sources = state.setdefault('sources', {})
    for label, info in status.items():
        if info['present']:
            sources[label] = {'entries': info['count'], 'd': today}
        elif label not in sources:
            sources[label] = {'entries': 0, 'd': ''}


def days_since(day_str, today):
    """Days between an ISO date string and ``today``; None when the string is unusable."""
    try:
        return (date.fromisoformat(today) - date.fromisoformat(day_str)).days
    except (TypeError, ValueError):
        return None


def retention_policy(state, status, remove_after_days=0, today=None):
    """Return ``should_remove(rel_path)`` for library files absent from this run.

    A file is kept when any provider recorded as supplying it is absent this
    run: nothing is known about what that provider still carries. When every
    supplying provider is present and none lists the title any more, the
    file is removed, unless ``remove_after_days`` is set and the title was
    last seen fewer than that many days ago, in which case it is kept a
    little longer in case it comes back. Files the state knows nothing about
    follow the old CLEAN_SYNC behaviour and are removed.

    ``should_remove.stats`` counts the decisions taken.
    """
    files = state.get('files', {})
    today = today or today_str()
    stats = {'removed': 0, 'kept_absent_source': 0, 'kept_aging': 0}

    def should_remove(rel_path):
        info = files.get(rel_path)
        if not info or not info.get('s'):
            stats['removed'] += 1
            return True
        for label in info['s']:
            source = status.get(label)
            if source is not None and not source['present']:
                stats['kept_absent_source'] += 1
                return False
        if remove_after_days > 0:
            age = days_since(info.get('d', ''), today)
            if age is not None and age < remove_after_days:
                stats['kept_aging'] += 1
                return False
        stats['removed'] += 1
        return True

    should_remove.stats = stats
    return should_remove


def report_retention(should_remove):
    """Print what the retention policy decided during sync."""
    stats = getattr(should_remove, 'stats', None)
    if stats is None:
        return
    print(f"Retention: removed {stats['removed']} files no longer listed by their provider, "
          f"kept {stats['kept_absent_source']} files whose provider was unavailable, "
          f"kept {stats.get('kept_aging', 0)} files still inside REMOVE_AFTER_DAYS")


def prune_state(state, local_root):
    """Forget files that no longer exist under the local library root."""
    files = state.get('files', {})
    for rel_path in list(files):
        if not os.path.isfile(os.path.join(local_root, rel_path)):
            del files[rel_path]
    return state
