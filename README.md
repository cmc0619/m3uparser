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
      - REMOVE_TERMS= # Optional, add more/different remove term values, does not override the defaults
      - REPLACE_TERMS= # Optional, add more/different replace values, does not override the defaults
      - CLEANERS= # Optional, add more/different cleaner values, does not override the defaults
      - CLEAN_SYNC= # If set to true will remove titles from VOD folders that are not present in m3u files, Defaults to false if blank.
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
| LIVE_TV       | true/false                                          | Parse live tv streams in m3u urls and creates a single livetv.m3u                                             | true/false                                   | true                                |
| UNSORTED      | true/false                                          | Creates a VOD folder for undefined streams, either misspelled or poorly labeled streams                       | true/false                                   | false                               |
| REMOVE_DUPLICATES | true/false                                      | Only writes the first occurrence of a title that resolves to the same .strm file                              | true                                         | true                                |

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

Providers often deliver the same title in several groups (for example `EN - Movies` and `4K - Movies`). After `SCRUB_HEADER`, `REPLACE_TERMS` and `REMOVE_TERMS` have been applied, if two streams resolve to exactly the same .strm file path (compared case-insensitively) only the first one found in the m3u is written and later ones are skipped, so the title shows up once in Jellyfin. Set `REMOVE_DUPLICATES=false` to restore the old behaviour where the last occurrence overwrote the earlier ones. Live TV channels are never de-duplicated.

The summary printed at the end of each run shows the number of entries dropped by `INCLUDE_TERMS`/`EXCLUDE_TERMS` and the number of duplicates skipped.

Default is set to `REMOVE_DUPLICATES=true`

### BYPASS_HEADER

Setting this to true will have the script download the m3u urls regardless if it is available from provider or not. It will still check for 200 response from url, but will not check for content-type or content-disposition from the header response. These two checks are useful for ensuring the m3u file downloaded is actually available from the provider. In some cases if your provider is "down", you still may get a 200ok response from their server, but the m3u file that will be downloaded will be empty, resulting in a failed parsing. There are cases where the provider does not have a content-disposition entry in their url header response, so setting this env variable to false will bypass this check and download the m3u file regardless. 

### CLEAN_SYNC

If this is set to true, then every time a parsing of m3u urls is complete, it will add new content from the m3u urls to your VOD libraries, and any content in your VOD libraries that is not in the m3u urls will be removed. This should be used with caution, if you add and remove m3u urls from the env variable often, then this will remove content from the VOD library. If your provider removes content often and you want to keep your VOD libraries in sync with what is available, then setting this to true is useful.

Default is set to `CLEAN_SYNC=false`

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
