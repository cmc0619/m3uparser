![m3uparser](./parser/assets/other_img/logo.png)

# m3u|>arser

m3u|>arser will parse your m3u urls and make a .strm library.

Docker Compose Example

```
services:
  m3uparser:
    container_name: m3uparser
    image: xaque87/m3uparser:latest
    environment:
      - PUID=1000 # Defaults 1000 if blank.
      - PGID=1000 # Defaults 1000 if blank.
      - M3U_URL= # "https://m3u_URL1.com, https://m3u_URL2.com, etc..."
      - M3U_LABELS= # Optional, a short name per M3U_URL in the same order, e.g. "chico, alpha"
      - HOURS=12 # update interval, setting this optional, default 12hrs.
      - SCRUB_HEADER= # Optional, add more/different scrub values, does not override the defaults
      - EXCLUDE_TERMS= # Optional, this acts as a filter to ignore streams that contain defined value in group-title, tvg-name or #EXTGRP
      - INCLUDE_TERMS= # Optional, only keep streams that contain one of the defined values in group-title, tvg-name or #EXTGRP
      - FILTER_LIVE_TV= # Default is false, true will apply INCLUDE_TERMS/EXCLUDE_TERMS to live tv channels as well
      - REMOVE_DUPLICATES= # Default is true, only writes the first occurrence of a title that shows up in more than one group
      - DUPLICATE_VERSIONS= # Default is false, true keeps every provider's copy of a title as a Jellyfin version instead of only the first
      - MERGE_SHOW_YEARS= # Default is false, true names show folders with the year when any provider supplies one so providers share a folder
      - REMOVE_TERMS= # Optional, add more/different remove term values, does not override the defaults
      - REPLACE_TERMS= # Optional, add more/different replace values, does not override the defaults
      - CLEANERS= # Optional, add more/different cleaner values, does not override the defaults
      - CLEAN_SYNC= # If set to true will remove titles from VOD folders that are not present in m3u files, Defaults to false if blank.
      - MIN_SOURCE_RATIO= # Default 0.5, a provider returning fewer than this share of last run's entries is treated as down and nothing of its is removed
      - REMOVE_AFTER_DAYS= # Default 0, keep a title that vanished from a working provider this many days before removing it
      - LIVE_TV= # Default is true, true will make a combined livetv.m3u from all live tv streams found in m3u files. Will be placed in /VODS/Live_TV 
      - UNSORTED= # Default is false, true will put at /VODS/Unsorted_VOD
      - JELLYFIN_URL= # Requires a Jellyfin server to be running. http://<jfin_url:8096> DO NOT use quotes around server url.
      - API_KEY= # Generate API key on server and enter it here. Requires a Jellyfin server to be running.
      - TF_HOST= # IP address used for Threadfin, example 127.0.0.1
      - TF_PORT= # Port used for Threadfin, example 34400
      - TF_USER= # Username being used for Threadfin
      - TF_PASS= # Password for Threadfin
      - REFRESH_LIB= # Requires a Jellyfin server to be running. Will refresh libraries after each parsing.

    volumes:
      - /path/to/your/media/library:/usr/src/app/VODS
      - /path/to/your/media/library:/usr/src/app/logs/
```

| ENV VARIABLE  | VALUES                                              | DESCRIPTION                                                                                                   | EXAMPLE                                      | DEFAULT VALUES                      |
| ------------- |:---------------------------------------------------:|:-------------------------------------------------------------------------------------------------------------:|:--------------------------------------------:|:-----------------------------------:|
| M3U_URL       | any url(s), in quotes, and seperated with a comma , | Include all URLs you want to be parsed                                                                        | "https://m3u_URL1.com, https://m3u_URL2.com" | n/a                                 |
| M3U_LABELS    | names, in quotes, seperated with a comma ,          | Optional short name per M3U_URL, in the same order. Defaults to the first part of each URL's hostname        | "chico, alpha"                              | hostname                            |
| BYPASS_HEADER | true/false                                          | Bypass checking url header for content-type and content-disposition.                                          | False                                        | False                               |
| HOURS         | numeric value                                       | Number representing the interval you want to update from m3u urls                                             | 12                                           | 8                                   |
| SCRUB_HEADER  | any text, in quotes, and seperated with a comma ,   | Removes value and preceding text from begining of group-title line                                            | "HD :"                                       | "HD :, SD :"                        |
| EXCLUDE_TERMS | any text, in quotes, and seperated with a comma ,   | Excludes content that contains a defined term in the group-title, tvg-name or #EXTGRP line                    | "AR -, FR -"                                 | ""                                  |
| INCLUDE_TERMS | any text, in quotes, and seperated with a comma ,   | Only keeps content that contains a defined term in the group-title, tvg-name or #EXTGRP line                  | "EN"                                         | ""                                  |
| FILTER_LIVE_TV| true/false                                          | Apply INCLUDE_TERMS/EXCLUDE_TERMS to live tv channels as well as VOD                                          | false                                        | false                               |
| REMOVE_TERMS  | any text, in quotes, and seperated with a comma ,   | Removes value(s) set from file and directory names                                                            | "x264, 720p"                                 | "720p, WEB, h264, H264, HDTV, x264" |
| REPLACE_TERMS | "term-to-replace=replace-value"                     | Replaces one value with another. Separate terms with an = and term on left is replaced with term to the right | "replace-this=with-this"                     | "1/2=\u00BD, /=-"                   |
| CLEANERS      | series,movie,tv,unsorted                            | Type of stream to apply REMOVE_TERMS value to                                                                 | tv, movies                                   | tv                                  |
| REFRESH_LIB   | true/false                                          | Refresh Jellyfin libraries after parsing                                                                      | false                                        | false                               |
| CLEAN_SYNC    | true/false                                          | Will remove titles from VOD folders that are not present in m3u.                                              | false                                        | false                               |
| MIN_SOURCE_RATIO | 0 to 1                                           | With CLEAN_SYNC, a provider whose playlist shrank below this share of its previous run is treated as unavailable and its titles are kept | 0.5                      | 0.5                                 |
| REMOVE_AFTER_DAYS | number of days                                  | With CLEAN_SYNC, keep a title that disappeared from a working provider for this many days before removing it. 0 removes immediately | 3                 | 0                                   |
| LIVE_TV       | true/false                                          | Parse live tv streams in m3u urls and creates a single livetv.m3u                                             | true/false                                   | true                                |
| UNSORTED      | true/false                                          | Creates a VOD folder for undefined streams, either misspelled or poorly labeled streams                       | true/false                                   | false                               |
| REMOVE_DUPLICATES | true/false                                      | Only writes the first occurrence of a title that resolves to the same .strm file                              | true                                         | true                                |
| DUPLICATE_VERSIONS | true/false                                     | Write one ` - provider` version file per provider for titles carried by several M3U_URLs, so Jellyfin shows one title with a version picker | false                     | false                               |
| MERGE_SHOW_YEARS | true/false                                       | Put every provider's episodes of a show in one folder, named with the year when any provider supplies it and with country tags removed | false                    | false                               |

## Instalation Process

```
mkdir m3uparser
cd m3uparser
curl -o docker-compose.yaml https://raw.githubusercontent.com/Xaque8787/m3uparser/main/m3uparser/docker-compose.yaml
curl -o m3uparser.env https://raw.githubusercontent.com/Xaque8787/m3uparser/main/m3uparser/m3uparser.env
```

Then edit the m3uparser.env file with your credentials and desired values.

Then run:

```
docker compose up -d
```

If you prefer inline `environment:` entries over an env file, or want to build the image from this repository instead of pulling it, start from [`m3uparser/docker-compose.example.yaml`](./m3uparser/docker-compose.example.yaml) and replace the `<placeholder>` values.

## Basic Information

### Expanding default values

**Add more values to the environment variables in the compose file to extend the defaults.**

### How it works

The parser uses the `group-title` value in the `#EXTINF` line of m3u files to structure the file and folder hierarchy. There are five stream types:

- **series**: Shows with season/episode values.
- **tv**: Shows with 'aired on date', such as talk shows with guest stars.
- **movies**: Movies with release years.
- **live-tv**: Live TV streams.
- **unsorted**: Streams that do not fit into the above categories.

Key=Value pairs are made from each item in the EXTINF line. The values are then used to determine stream type, extract relavent information, and finally clean out unwanted values to then make the end resulting .strm libraries.

## Examples and Explanations

### MULTIPLE PROVIDERS;   M3U_URL, M3U_LABELS

Every URL in `M3U_URL` is downloaded and combined into one playlist, in the order you list them. When two providers deliver the same title, the first listed provider wins and the later copy is treated as a duplicate, so put your preferred provider first. Each stream remembers which provider it came from; the provider name is the first part of the URL's hostname (`http://chicotv.top/...` becomes `chicotv`) unless you set `M3U_LABELS` with one name per URL in the same order.

A provider that fails to download, or returns an empty playlist, is skipped for that run and reported in the log. If nothing at all could be downloaded the run is aborted and the library is left untouched.

### SCRUB_HEADER
The `group-title` value often contains more information than just the TV show or Movie name. The `SCRUB_HEADER` values work by matching the first instance of the given values in the `group-title` string, and removing the values and anything that precedes it. The goal is to use a common string found amongst the `group-title` values.

Example: `SCRUB_HEADER="HD :, SD :"`. This removes these values,`HD :` and `SD :`, if they exist, and any preceding text from the `group-title` line. So a line like this, `group-title="Movie VOD",HD : The Fall Guy 2024` will become `group-title= The Fall Guy 2024`. Ensure spaces are included where needed. Add multiple values to `SCRUB_HEADER=`, separated by commas, in a single set of quotes.
Note that any quotes that exist in the `group-title` are stripped before the `SCRUB_HEADER` is applied, so they do not need to be included in the SCRUB_HEADER value.

**ESCAPING SPECIAL CHARACTERS**

You can escape characters like `,` by using a `\` So if your `group-title` looks like this `group-title="Movie VOD",The Fall Guy 2024`, your SCRUB_HEADER value should look like this `SCRUB_HEADER="\,"` So this finds the first instance of a `,` and then removes it and anything that precedes it.

Special characters such as `+` in the group name are handled, so `group-title="Documentary+",Get Gotti` with `SCRUB_HEADER="\,"` becomes `Get Gotti`. Stripping a `"<group>",` prefix this way is the recommended approach, since `\,` matches regardless of what the group name is. Note that empty items in the comma separated list are ignored (`"a,,,b"` is the same as `"a, b"`), so a bare `,` must always be written as `\,`.

Default is set to: `SCRUB_HEADER="HD :, SD :"`

### REMOVE_TERMS & CLEANERS

`REMOVE_TERMS` removes specified terms, and any attached text, from titles. For instance, `REMOVE_TERMS="x264"`, would remove the entire string `x264-somegarbge`. This setting is case-sensitive and should have multiple values separated by commas, in a single set of quotes. i.e `REMOVE_TERMS="x264, h264, X264"`

A common format seen is to put qualities and language tag in sets of brackets like this `[EN]` or `[h265]`. To remove all of these use a `REMOVE_TERM="["`

Default is set to: `"720p, WEB, h264, H264, HDTV, x264"`

The `CLEANERS` variable defines which stream types `REMOVE_TERMS` applies to. For example, `CLEANERS=series,tv` applies `REMOVE_TERMS` to series and TV shows.

Default is set to: `tv`

### REPLACE_TERMS

Add more replacements to `REPLACE_TERMS` in the format `"replace=value"`. For example: `REPLACE_TERMS="replace-this=with-this, dontwant=wantinstead"`. This replaces specified terms in all streams, except live TV.

Default is set to: `"1/2=\u00BD, /=-"`

### EXCLUDE_TERMS & INCLUDE_TERMS

`EXCLUDE_TERMS` drops any stream that contains one of the given terms. `INCLUDE_TERMS` does the opposite: when it is set, only streams that contain at least one of the given terms are kept and everything else is dropped. Both check the `group-title`, the `tvg-name` and the `#EXTGRP` line (if present), and both use the same format, multiple values separated by commas, in a single set of quotes. `EXCLUDE_TERMS` always wins, so a stream that matches both an include and an exclude term is dropped.

Example: `INCLUDE_TERMS="EN"` keeps only English tagged groups. `EXCLUDE_TERMS="AR -, FR -"` drops the Arabic and French groups.

Terms are matched case-insensitively and literally, so characters like `+`, `[` or `|` can be used as they are. When a term starts or ends with a letter or digit, that edge has to be on a word boundary. `EN` matches `EN - Series`, `[EN]` and `Movies EN`, but not `Documentary`, `General` or `ENTERTAINMENT`. Edges that are symbols match exactly where written, so `FR -` matches `FR - Films` and `US |` matches `US | Sports`.

The filters are applied to the raw values before `SCRUB_HEADER` and `REPLACE_TERMS` run, so write the terms as they appear in the source m3u.

By default the filters only affect the VOD folders (movies, series, tv, unsorted) and live TV channels are always written to `livetv.m3u`. Set `FILTER_LIVE_TV=true` to apply `INCLUDE_TERMS`/`EXCLUDE_TERMS` to live TV channels as well.

Defaults are set to: `EXCLUDE_TERMS=""`, `INCLUDE_TERMS=""`, `FILTER_LIVE_TV=false`

### REMOVE_DUPLICATES

Providers often deliver the same title in several groups (for example `EN - Movies` and `4K - Movies`). After `SCRUB_HEADER`, `REPLACE_TERMS` and `REMOVE_TERMS` have been applied, if two streams resolve to the same .strm file path only the first one found in the m3u is written and later ones are skipped, so the title shows up once in Jellyfin. Paths are compared ignoring case, the punctuation `: ; , . ! ? ' "`, and differences in spacing, hyphens and underscores, so `Avatar: The Last Airbender` and `Avatar the Last Airbender` count as the same title, as do `Cook Off` and `Cook-Off!`. Everything else must match exactly, so `18` and `18½` stay separate. Set `REMOVE_DUPLICATES=false` to restore the old behaviour where the last occurrence overwrote the earlier ones. Live TV channels are never de-duplicated.

The summary printed at the end of each run shows the number of entries dropped by `INCLUDE_TERMS`/`EXCLUDE_TERMS` and the number of duplicates skipped.

Default is set to `REMOVE_DUPLICATES=true`

### DUPLICATE_VERSIONS

With more than one `M3U_URL`, `REMOVE_DUPLICATES` keeps only the first provider's stream for a title the providers share. Set `DUPLICATE_VERSIONS=true` to keep every provider's stream instead. Each .strm is then written with a ` - <provider>` suffix, using the names from `M3U_LABELS` or the URL hostname, and all providers' files for one title share the folder and base name of the first provider that listed it:

```
Movie_VOD/Tangled (2010)/Tangled (2010) - chicotv.strm
Movie_VOD/Tangled (2010)/Tangled (2010) - alphax8k.strm
TV_VOD/Acapulco (2021)/Season 01/Acapulco (2021) S01E01 - chicotv.strm
TV_VOD/Acapulco (2021)/Season 01/Acapulco (2021) S01E01 - alphax8k.strm
```

Jellyfin shows such a folder as one title with a version picker, so a stream that fails on one provider can be switched to the other without a second library entry. Jellyfin does not fail over on its own; the version to play is chosen by you, and the first listed provider is the default. Repeats within the same provider are still skipped. Turning this on renames every existing .strm once, which Jellyfin treats as a library change on the next scan.

Default is set to `DUPLICATE_VERSIONS=false`

### MERGE_SHOW_YEARS

Providers name shows differently: one lists `Acapulco S01E01`, another `4K-A+ - Acapulco (2021) (US) S01E01`. Even after `REMOVE_TERMS` strips the prefix, `Acapulco` and `Acapulco (2021) (US)` are different folders and Jellyfin shows two series. With `MERGE_SHOW_YEARS=true` shows are grouped by their name with the trailing year and `(US)` style country tag removed, and each group gets one folder name:

- when exactly one year is known across the group, every provider's episodes go in `Acapulco (2021)`, which is the name Jellyfin matches best;
- when no provider supplies a year, the folder is the bare name with any country tag removed;
- when the group has two or more different years, such as `Battlestar Galactica (1978)` and `(2004)`, those stay separate and a copy with no year is left alone rather than guessed into either.
- when the group has two or more different country tags, such as `The Office (US)` and `The Office (UK)`, they are different shows: each keeps its tag and year, as in `The Office (US) (2005)`, and an untagged copy is left alone.

The first listed provider decides the spelling of the name. The year chosen for a show is remembered in `logs/library_state.json`, so when the provider that supplies it is unavailable for a run the folder keeps its name instead of losing the year and coming back later. Only shows are affected; movies already carry their year. The first run after enabling this renames existing show folders once. Combine with `DUPLICATE_VERSIONS=true` to keep each provider's stream of an episode as a version in the shared folder.

Default is set to `MERGE_SHOW_YEARS=false`

### BYPASS_HEADER

Setting this to true will have the script download the m3u urls regardless if it is available from provider or not. It will still check for 200 response from url, but will not check for content-type or content-disposition from the header response. These two checks are useful for ensuring the m3u file downloaded is actually available from the provider. In some cases if your provider is "down", you still may get a 200ok response from their server, but the m3u file that will be downloaded will be empty, resulting in a failed parsing. There are cases where the provider does not have a content-disposition entry in their url header response, so setting this env variable to false will bypass this check and download the m3u file regardless. 

### CLEAN_SYNC

If this is set to true, then every time a parsing of m3u urls is complete, it will add new content from the m3u urls to your VOD libraries, and any content in your VOD libraries that is not in the m3u urls will be removed. This should be used with caution, if you add and remove m3u urls from the env variable often, then this will remove content from the VOD library. If your provider removes content often and you want to keep your VOD libraries in sync with what is available, then setting this to true is useful.

Default is set to `CLEAN_SYNC=false`

**Providers that fail or come back short.** Every .strm remembers which providers supplied it (kept in `logs/library_state.json`, so mount the logs folder). When a provider's playlist cannot be downloaded, is empty, or holds fewer than `MIN_SOURCE_RATIO` of the entries it had on the previous run, that provider is treated as unavailable for the run: its titles are left in place and nothing of its is removed, while other providers still sync normally. A provider that is present and simply no longer lists a title has that title removed straight away, so a few thousand titles dropping out of a large playlist are removed immediately, but a playlist that comes back empty or truncated never wipes the library. If every provider fails the run is aborted before touching anything. Removing a URL from `M3U_URL` is different from a failure: that provider is no longer configured, so its titles are removed on the next run. The log reports each provider's status and how many files were removed or kept. A provider that genuinely shrank below the ratio stays treated as unavailable, because its baseline is only updated on trusted runs; lower `MIN_SOURCE_RATIO` or delete `logs/library_state.json` to accept the smaller playlist as the new baseline.

Default is set to `MIN_SOURCE_RATIO=0.5`

**Aging out titles.** Removal of a title that a working provider no longer lists is immediate by default. Set `REMOVE_AFTER_DAYS` to a number of days to keep such titles for a grace period first: each .strm remembers when it was last listed, and it is only removed once it has been missing for that many days. A title that comes back within the period simply carries on. This only applies to providers that are present; titles of an unavailable provider are always kept regardless.

Default is set to `REMOVE_AFTER_DAYS=0`

### LIVE TV STREAMS

Set `LIVE_TV=true` to generate a `livetv.m3u` file with all live TV streams from the provided m3u URLs. This file will be placed next to your VOD folders, /VODS/Live_TV

Default is set to: `LIVE_TV=true`

### UNSORTED

Set `UNSORTED=true` to create a VOD folder for poorly named or unidentified streams. This folder can be added manually to your Jellyfin server and edited through the web UI.

Default is set to `UNSORTED=false`

### JELLYFIN INTEGRATION;   JELLYFIN_URL, API_KEY, REFRESH_LIB

To utilize the Jellyfin integration, you must have a Jellyfin server accessible if you supplied the compose file with the `API_KEY` and `JELLYFIN_URL` env variable. If you supply a address to your working server, and an api key you generated on that server; then when this script is ran it will refresh your library if `REFRESH_LIB=true` to add new titles that are in m3u urls, if `CLEAN_SYNC=true` it will also then remove any titles not found in the m3u urls but are in your VOD libraries. If you have `LIVE_TV=true`, then it will also refresh your tv guide.

**`JELLYFIN_URL`** should include http:// or https:// (DO NOT SURROUND WITH "")
Logs will now be uploaded to the server as well.
**`API_KEY`** Generate on server. Dashboard > Api Key > Add
**`REFRESH_LIB`** True or false, depending on your preference.

If you do not have a Jellyfin server set up, but would like a easy way to get one set up, checkout the branch of this repo for an automated setup https://github.com/Xaque8787/m3uparser/tree/ezpztv

### THREADFIN INTEGRATION;   TF_HOST, TF_PORT, TF_USER, TF_PASS

If you have Threadfin setup and want to refresh the m3u/xmltv data when the script is run/re run, then supply the ip:port username and password to the appropriate env variables.

### ADDITIONAL OPTIONS

If you want to incorporate each of the Movie_VOD and TV_VOD folders into an existing library, then you can use these volume mounts below. Be careful, if you do this and have set `CLEAN_SYNC=true`, then this will remove any of your existing media in those host locations that are not present in the m3u urls. This is more than likely unwanted, so be sure to set `CLEAN_SYNC=false` if you do use the below mounts. (false is default value if CLEAN_SYNC is blank or absent from compose file)

```
volumes:
      - /path/to/your/media/library/tvshows:/usr/src/app/VODS/TV_VOD
      - /path/to/your/media/library/movies:/usr/src/app/VODS/Movie_VOD
      - /path/to/your/media/library/liveTVm3us:/usr/src/app/VODS/Live_TV
```
