import os
import re
import shutil
from urllib.parse import urlparse

import requests
from parser.utils import write_to_file


def process_live_tv_entries(entries, livetv_file):
    with open(livetv_file, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for entry in entries:
            if entry.get('livetv'):
                extinf_line = entry.get('extinf_line', '')
                extgrp_line = entry.get('extgrp', '')
                stream_url_line = entry.get('stream_url', '')

                # Write EXTINF line
                f.write(extinf_line + '\n')

                # Write EXTGRP line
                if extgrp_line:
                    f.write(f"{extgrp_line}\n")

                # Write stream URL
                f.write(stream_url_line + '\n')


def strm_path_for_entry(entry, tv_dir, movies_dir, unsorted_dir):
    """Return the .strm path an entry would be written to, or None if it is skipped.

    Entries flagged with ``exclude`` (INCLUDE_TERMS / EXCLUDE_TERMS) and live TV
    entries never produce a .strm file.
    """
    if entry.get("exclude"):
        return None

    if entry.get('series') and entry.get('tv_show'):
        show_title = entry.get('show_title')
        season = entry.get('season')
        season_episode = entry.get('season_episode')
        series_dir = os.path.join(tv_dir, show_title, f"Season {season}")
        return os.path.join(series_dir, f"{show_title} {season_episode}.strm")

    if entry.get('television') and entry.get('tv_show'):
        air_date = entry.get('air_date')
        show_title = entry.get('show_title')
        guest_star = entry.get('guest_star')
        television_file = [show_title]
        if guest_star:
            television_file.append(guest_star)
        television_file.append(air_date)
        tv_strm_file = ", ".join(television_file)
        tv_show_dir = os.path.join(tv_dir, show_title)
        return os.path.join(tv_show_dir, f"{tv_strm_file}.strm")

    if entry.get('movie'):
        movie_title = entry.get('movie_title')
        movie_date = entry.get('movie_date')
        movie_dir_path = os.path.join(movies_dir, f"{movie_title} ({movie_date})")
        return os.path.join(movie_dir_path, f"{movie_title} ({movie_date}).strm")

    if entry.get('unsorted'):
        group_title = entry.get('group-title', '')
        unsorted_dir_path = os.path.join(unsorted_dir, group_title)
        return os.path.join(unsorted_dir_path, f"{group_title}.strm")

    return None


def handle_entry(entry, tv_dir, movies_dir, unsorted_dir, write_to_file, errors, seen_paths=None):
    """Write the .strm file for a single entry and return its path.

    When ``seen_paths`` is a set, it is used to de-duplicate entries: if the
    final (fully cleaned) .strm path was already produced during this run,
    compared case-insensitively, the entry is flagged ``duplicate=True`` and
    skipped. The first occurrence in the m3u wins.
    """
    try:
        strm_file = strm_path_for_entry(entry, tv_dir, movies_dir, unsorted_dir)
        if strm_file is None:
            return None

        dedupe_key = strm_file.lower()
        if seen_paths is not None and dedupe_key in seen_paths:
            entry['duplicate'] = True
            return None

        strm_dir = os.path.dirname(strm_file)
        if not os.path.exists(strm_dir):
            os.makedirs(strm_dir)
            # print(f"Created directory: {strm_dir}")
        # print(f"Writing to file: {strm_file}")
        write_to_file(strm_file, entry.get('stream_url', ''))
        # Only remember the path once the file exists, so a failed first write
        # does not make later occurrences of the same title look like duplicates
        if seen_paths is not None:
            seen_paths.add(dedupe_key)
        return strm_file

    except Exception as e:
        error_message = f"Error handling entry: {entry}\nError: {e}"
        print(error_message)
        errors.append(error_message)
        return None


def proc_entries(entries, errors, tv_dir, movies_dir, unsorted_dir, remove_duplicates=True):
    """Write .strm files for all entries.

    With ``remove_duplicates`` enabled (the default), titles that resolve to
    the same .strm path after all cleaning and replacements are only written
    once, so a title delivered in several m3u groups shows up a single time
    in Jellyfin.
    """
    tv_strm_files = []
    movie_strm_files = []
    unsorted_strm_files = []
    seen_paths = set() if remove_duplicates else None
    for entry in entries:
        strm_file = handle_entry(entry, tv_dir, movies_dir, unsorted_dir, write_to_file, errors, seen_paths)
        if strm_file:
            if entry.get('tv_show'):
                tv_strm_files.append(strm_file)
            elif entry.get('movie'):
                movie_strm_files.append(strm_file)
            elif entry.get('unsorted'):
                unsorted_strm_files.append(strm_file)
    # Print the final parsed dictionaries
    # print("\nFinal parsed dictionaries:")
    # for d in entries:
        # print(d)


def move_files(file_path, destination_path):
    destination_file_path = os.path.join(destination_path, os.path.basename(file_path))
    if os.path.isfile(destination_file_path):
        os.remove(destination_file_path)
        print(f"Removed existing file at {destination_file_path}")
    shutil.move(file_path, destination_path)

    print(f"Moved {file_path} to {destination_path}")


SOURCE_MARKER = '#M3UPARSER-SOURCE:'
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/123.0.0.0 Safari/537.36")
# Seconds to wait for a connection, then between bytes of the response
REQUEST_TIMEOUT = (15, 120)


def source_label(url, index, labels=None):
    """Return a short label for the m3u source at ``index`` in M3U_URL.

    An explicit entry in M3U_LABELS wins; otherwise the first component of the
    URL's hostname is used (``http://chicotv.top/get.php?...`` becomes
    ``chicotv``). Labels are reduced to letters, digits, ``.``, ``_`` and ``-``
    so they are safe inside file names.
    """
    label = ''
    if labels and index < len(labels):
        label = labels[index]
    if not label:
        host = urlparse(url).hostname or ''
        label = host.split('.')[0] if host else ''
    label = re.sub(r'[^A-Za-z0-9._-]+', '', label)
    return label or f'source{index + 1}'


def unique_label(label, seen_labels):
    """Return ``label`` or the first ``label2``, ``label3``... that is not in ``seen_labels``."""
    candidate = label
    suffix = 2
    while candidate in seen_labels:
        candidate = f'{label}{suffix}'
        suffix += 1
    return candidate


def redact_url(url):
    """Return a URL safe for logs: scheme, host and path only, without the query string.

    Provider playlist URLs carry the account username and password as query
    parameters, and the log file is kept on disk and uploaded to Jellyfin.
    """
    parts = urlparse(url)
    if not parts.scheme or not parts.hostname:
        return '<invalid url>'
    host = parts.hostname
    if parts.port:
        host = f'{host}:{parts.port}'
    return f'{parts.scheme}://{host}{parts.path}'


def download_m3u(vodurl, file_path, skip_header=None):
    """Download one m3u URL to ``file_path``. Returns True when a file was written.

    Requests use a bounded connect and read timeout so a provider that stops
    responding cannot stall the whole run, and log lines never include the
    query string or response headers.
    """
    headers = {"User-Agent": USER_AGENT}
    shown = redact_url(vodurl)
    try:
        if not skip_header:
            # Default behavior: check headers before downloading
            response = requests.head(vodurl, headers=headers, timeout=REQUEST_TIMEOUT)
            print(f"HEAD request to {shown} returned status code: {response.status_code}")
            if response.status_code != 200:
                print(f"URL is not accessible: {shown} - Status code: {response.status_code}")
                return False
            content_type = response.headers.get('Content-Type')
            content_disposition = response.headers.get('content-disposition')
            if not (content_type and 'filename=' in (content_disposition or '')):
                print(f"URL not valid: {shown} - Content-Type or filename missing. Skipping...")
                return False
        else:
            print('Skipping url header check.')

        response = requests.get(vodurl, headers=headers, timeout=REQUEST_TIMEOUT)
        print(f"GET request to {shown} returned status code: {response.status_code}")
        if response.status_code != 200:
            print(f"GET request failed for {shown} - Status code: {response.status_code}")
            return False
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(f"Downloaded file from URL: {shown}")
        return True
    except requests.RequestException as e:
        print(f"Error processing URL {shown}: {type(e).__name__}: {str(e).replace(vodurl, shown)}")
        return False


def prepare_m3us(URLS, m3u_dir, m3u_file_path, skip_header=None, M3U_LABELS=None):
    """Download every M3U_URL and combine them into one playlist, in M3U_URL order.

    Each source's content is preceded by a ``#M3UPARSER-SOURCE:<label>`` line so
    the parser can tag entries with the provider they came from. Because the
    combined file follows M3U_URL order, the first listed provider wins when
    several supply the same title.

    Returns a list of ``{'label', 'url', 'file', 'downloaded'}`` dicts, one
    per configured URL, including sources that failed to download
    (``downloaded`` False). A download cut off mid-line loses that last,
    incomplete line so it cannot swallow the next source's marker.
    """
    sources = []
    seen_labels = set()
    for index, vodurl in enumerate(URLS):
        label = unique_label(source_label(vodurl, index, M3U_LABELS), seen_labels)
        seen_labels.add(label)
        file_path = os.path.join(m3u_dir, f'{index:02d}_{label}.m3u')
        downloaded = download_m3u(vodurl, file_path, skip_header)
        sources.append({'label': label, 'url': vodurl, 'file': file_path, 'downloaded': downloaded})

    print("All URLs processed.")

    # Create the output file and add #EXTM3U at the beginning
    with open(m3u_file_path, 'w', encoding='utf-8') as outfile:
        outfile.write("#EXTM3U\n")
        for source in sources:
            file_path = source['file']
            if not (source['downloaded'] and os.path.isfile(file_path)):
                print(f"No playlist downloaded for source {source['label']}")
                continue
            print(f"Processing file: {file_path}")
            with open(file_path, 'r', encoding='utf-8', errors='replace') as infile:
                # Skip the first line and append the rest to the output file
                lines = infile.readlines()[1:]
            if lines and not lines[-1].endswith('\n'):
                print(f"Playlist for source {source['label']} ends mid-line; dropping the incomplete last line")
                lines.pop()
            # A provider cannot claim another provider's entries by emitting our own marker
            lines = [line for line in lines if not line.lstrip().startswith(SOURCE_MARKER)]
            if len(lines) < 2:
                print(f"Playlist for source {source['label']} is empty. Skipping...")
                continue
            outfile.write(f"\n{SOURCE_MARKER}{source['label']}\n")
            outfile.writelines(lines)

    print(f"All files have been combined into {m3u_file_path}")

    # Check if the combined m3u file has 3 or fewer lines
    print("Checking the combined m3u file for line count...")
    with open(m3u_file_path, 'r', encoding='utf-8') as m3u_file:
        print("Reading the combined m3u file for line count...")
        lines = m3u_file.readlines()
        print(f"Lines in the combined m3u file: {len(lines)}")
        if len(lines) <= 1:
            raise ValueError(f"The m3u file {m3u_file_path} has 3 or fewer lines. Aborting.")

    return sources

# def prepare_m3us(URLS, m3u_dir, m3u_file_path):
#     for vodurl in URLS:
#         try:
#             response = requests.head(vodurl)
#             print(f"HEAD response headers for {vodurl}: {response.headers}")
#             print(f"HEAD request to {vodurl} returned status code: {response.status_code}")
#
#             if response.status_code == 200:
#                 content_type = response.headers.get('Content-Type')
#                 content_disposition = response.headers.get('content-disposition')
#
#                 if content_type and 'filename=' in (content_disposition or ''):
#                     response = requests.get(vodurl)
#                     print(f"GET request to {vodurl} returned status code: {response.status_code}")
#
#                     if response.status_code == 200:
#                         # Determine the filename from the URL
#                         filename = os.path.basename(vodurl)
#                         file_path = os.path.join(m3u_dir, filename)
#
#                         # Save the file content
#                         with open(file_path, 'wb') as file:
#                             file.write(response.content)
#                         print(f"Downloaded file from URL: {vodurl}")
#                     else:
#                         print(f"GET request failed for {vodurl} - Status code: {response.status_code}")
#                 else:
#                     print(f"URL not valid: {vodurl} - Content-Type or filename missing. Skipping...")
#             else:
#                 print(f"URL is not accessible: {vodurl} - Status code: {response.status_code}")
#         except requests.RequestException as e:
#             print(f"Error processing URL {vodurl}: {e}")
#
#     print("All URLs processed.")
#
#     # Create the output file and add #EXTM3U at the beginning
#     with open(m3u_file_path, 'w') as outfile:
#         outfile.write("#EXTM3U\n")
#         # Loop through each file in the specified directory
#         for file in os.listdir(m3u_dir):
#             file_path = os.path.join(m3u_dir, file)
#             print(f"Processing file: {file_path}")
#             # Check if the file exists and is readable
#             if os.path.isfile(file_path):
#                 with open(file_path, 'r') as infile:
#                     # Skip the first line and append the rest to the output file
#                     lines = infile.readlines()[1:]
#                     if lines:
#                         outfile.write("\n")
#                         outfile.writelines(lines)
#             else:
#                 print(f"Cannot read {file_path}")
#
#     print(f"All files have been combined into {m3u_file_path}")


# sync_directories with remove from src if not in dest
def sync_directories(src, dest, remove_sync):
    if remove_sync:
        for item in os.listdir(src):
            src_item = os.path.join(src, item)
            dest_item = os.path.join(dest, item)

            if os.path.isdir(src_item):
                if not os.path.exists(dest_item):
                    os.makedirs(dest_item)
                    # print(f"Created directory: {dest_item}")
                sync_directories(src_item, dest_item, remove_sync)
            elif os.path.isfile(src_item):
                if not os.path.exists(dest_item):
                    shutil.copy2(src_item, dest_item)
                    print(f"Added content: {dest_item}")
                else:
                    # Check if contents differ
                    with open(src_item, 'rb') as f_src, open(dest_item, 'rb') as f_dest:
                        if f_src.read() != f_dest.read():
                            shutil.copy2(src_item, dest_item)
                            print(f"Updated content: {dest_item}")

        # Remove files and directories in dest that are not in src
        for item in os.listdir(dest):
            dest_item = os.path.join(dest, item)
            src_item = os.path.join(src, item)

            if not os.path.exists(src_item):
                if os.path.isdir(dest_item):
                    shutil.rmtree(dest_item)
                    print(f"Removed directory: {dest_item}")
                elif os.path.isfile(dest_item):
                    os.remove(dest_item)
                    print(f"Removed file: {dest_item}")
    else:
        for item in os.listdir(src):
            src_item = os.path.join(src, item)
            dest_item = os.path.join(dest, item)

            if os.path.isdir(src_item):
                if not os.path.exists(dest_item):
                    os.makedirs(dest_item)
                sync_directories(src_item, dest_item, remove_sync)
            elif os.path.isfile(src_item):
                if not os.path.exists(dest_item):
                    shutil.copy2(src_item, dest_item)
                    print(f"Content added: {dest_item}")
                else:
                    # Check if contents differ
                    with open(src_item, 'rb') as f_src, open(dest_item, 'rb') as f_dest:
                        if f_src.read() != f_dest.read():
                            shutil.copy2(src_item, dest_item)
                            print(f"Content updated: {dest_item}")

# def sync_directories(src, dest):
#     for item in os.listdir(src):
#         src_item = os.path.join(src, item)
#         dest_item = os.path.join(dest, item)
#
#         if os.path.isdir(src_item):
#             if not os.path.exists(dest_item):
#                 os.makedirs(dest_item)
#             sync_directories(src_item, dest_item)
#         elif os.path.isfile(src_item):
#             if not os.path.exists(dest_item):
#                 shutil.copy2(src_item, dest_item)
#                 print(f"Added content to {dest_item}")
