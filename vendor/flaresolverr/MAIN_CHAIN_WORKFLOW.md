# Main Chain Workflow

## Purpose

This directory now keeps only the verified main workflow for Science/PNAS full-text fetching on this machine.

For portability across other hosts, the shipped script default is now the headless preset `.env.flaresolverr-source-headless` with `HEADLESS=true + Xvfb`.
The previously verified WSLg preset remains available as `.env.flaresolverr-source-wslg` when you explicitly want the headful WSLg route.
On this specific host, the verified local path is still the explicit WSLg preset because the official `Xvfb` route can fail when `/tmp/.X11-unix` is mounted read-only.

The verified chain is:

1. Run FlareSolverr from the official upstream source tree.
2. Use the local WSLg display, with `HEADLESS=false`.
3. Keep a PTY attached when that headful WSLg browser is launched in background mode.
4. Launch the background service in its own session with `setsid`, instead of relying on a plain `nohup ... &`.
5. Expose the local FlareSolverr service at `http://127.0.0.1:8191/v1`.
6. Let `fetch_fulltext.py` use FlareSolverr as the HTML fetcher.
7. If the publisher HTML route lands on an abstract page, reuse the FlareSolverr-solved cookies and user-agent to seed a Playwright browser context, then download the PDF fallback.

This is the only chain that has been validated end-to-end in this directory.

## What Is Kept

The important kept files are:

- `fetch_fulltext.py`
  Main fetch pipeline. Handles PMC, Crossref, publisher HTML, and PDF fallback.
- `setup_flaresolverr_source.sh`
  One-time setup script for the official FlareSolverr source workflow.
- `start_flaresolverr_source.sh`
  Starts the local FlareSolverr service in the background.
- `run_flaresolverr_source.sh`
  Runs FlareSolverr in the foreground for diagnosis.
- `stop_flaresolverr_source.sh`
  Stops the background FlareSolverr service.
- `flaresolverr_source_common.sh`
  Shared env parsing and common path helpers.
- `.env.flaresolverr-source-wslg`
  Explicit WSLg environment file for the headful route.
- `.env.flaresolverr-source-wslg.example`
  Example env file.
- `.env.flaresolverr-source-headless`
  Default portable headless environment file.
- `.env.flaresolverr-source-headless.example`
  Example env file for the portable headless preset.
- `FLARESOLVERR_SOURCE_WORKFLOW.md`
  Short operator notes for the same chain.
- `MAIN_CHAIN_WORKFLOW.md`
  This detailed document.

The runtime dependencies used by the workflow are recreated by setup when needed:

- `.work/FlareSolverr`
  Official upstream FlareSolverr source checkout created by setup.
- `.venv-flaresolverr`
  Virtual environment used to run FlareSolverr.
- `.flaresolverr`
  Downloaded FlareSolverr release bundle, including the bundled Chrome used by the source workflow.

## Why This Chain

This host is using WSLg. The stable path here is not Docker and not a stored browser state file.

The reasons are:

- The official Docker route was not the stable winner for this target.
- A manual `storage_state.json` is not required for the working chain.
- The validated source path is official upstream code with no source patch.
- Reusing the WSLg display with `HEADLESS=false` proved stable on this machine.
- For PNAS-like cases, the HTML article path may still resolve to an abstract page even after the shield is bypassed, so the PDF fallback is part of the main practical chain.

## Recommended Presets

| Environment | Recommended preset | Mode | Recommendation |
| --- | --- | --- | --- |
| WSLg | `.env.flaresolverr-source-wslg` | `HEADLESS=false` | Use when you want the visible WSLg browser path and host-specific interactive debugging. |
| Desktop Linux | `.env.flaresolverr-source-headless` | `HEADLESS=true` + `Xvfb` | Best default for mixed desktop and background use because it depends less on the current graphical session. |
| Headless server | `.env.flaresolverr-source-headless` | `HEADLESS=true` + `Xvfb` | Best default for no-display environments such as SSH-only servers, systemd services, tmux, and CI. |

## Environment

The script default environment file is `.env.flaresolverr-source-headless`.

The explicit WSLg environment file is `.env.flaresolverr-source-wslg`.

The headless preset's main settings are:

- `HEADLESS="true"`
- `FLARESOLVERR_LOG_FILE="/home/dictation/test/run_logs/flaresolverr-source-headless.log"`
- `FLARESOLVERR_PID_FILE="/home/dictation/test/run_logs/flaresolverr-source-headless.pid"`

The WSLg preset's distinguishing settings are:

- `FLARESOLVERR_REPO_DIR="/home/dictation/test/.work/FlareSolverr"`
- `FLARESOLVERR_VENV_DIR="/home/dictation/test/.venv-flaresolverr"`
- `FLARESOLVERR_DOWNLOAD_DIR="/home/dictation/test/.flaresolverr"`
- `FLARESOLVERR_RELEASE_VERSION="v3.4.6"`
- `FLARESOLVERR_HOST="127.0.0.1"`
- `FLARESOLVERR_PORT="8191"`
- `HEADLESS="false"`
- `TZ="Asia/Shanghai"`

The resulting service endpoint is:

- `http://127.0.0.1:8191/v1`

## One-Time Setup

Run this once to prepare the source checkout, Python environment, and bundled Chrome:

```bash
cd /home/dictation/test
bash ./setup_flaresolverr_source.sh
```

The script default now uses `HEADLESS=true`, so install the `Xvfb` binary first.
On Debian/Ubuntu systems, that usually means:

```bash
sudo apt-get update
sudo apt-get install -y xvfb
```

If you explicitly switch to `.env.flaresolverr-source-wslg`, that WSLg route uses `HEADLESS=false` and does not depend on `Xvfb`.
On this host, that explicit WSLg route remains the verified local path because the official `Xvfb` route may fail with a read-only `/tmp/.X11-unix`.

What it does:

1. Clones or refreshes the official FlareSolverr repo under `.work/FlareSolverr`.
2. Creates `.venv-flaresolverr` if needed.
3. Installs FlareSolverr Python dependencies into that virtualenv.
4. Downloads the official FlareSolverr release bundle for the matching version.
5. Extracts the bundled Chrome.
6. Ensures the source tree points to the bundled Chrome through `src/chrome`.

## Start The Service

Normal background start:

```bash
cd /home/dictation/test
bash ./start_flaresolverr_source.sh ./.env.flaresolverr-source-wslg
```

By default, the kept scripts now use `.env.flaresolverr-source-headless`.

If you want the explicit WSLg route instead, pass `.env.flaresolverr-source-wslg` on the command line.
That explicit WSLg command is still the verified local command on this host.

When `HEADLESS=false`, `start_flaresolverr_source.sh` now wraps the launch in `script` so the browser still has a PTY while the service runs in background.
This avoids the failure mode where `sessions.list` succeeds but the first real `request.get` kills the background service.

Dependency note:

- `HEADLESS=true` requires the `Xvfb` package and an available `Xvfb` binary
- the explicit WSLg path in this directory uses `HEADLESS=false`, so it reuses the WSLg display instead of `Xvfb`

In this execution environment, a plain `nohup ... &` background child is not reliable enough by itself.
The parent command can exit, the child can be reaped, and you end up with a misleading symptom:

- `start_flaresolverr_source.sh` prints that the service started
- a quick `sessions.list` probe may still succeed
- but the listener disappears moments later
- then `fetch_fulltext.py` reports `flaresolverr_timeout` while trying to create a session or send `request.get`

That is why the kept background launcher now prefers `setsid`.
`setsid` and `script` are solving different problems:

- `setsid` keeps the background FlareSolverr service alive after the parent launcher exits
- `script` keeps a PTY attached for the headful WSLg browser path when `HEADLESS=false`

Both are part of the verified background workflow on this host.

The background service writes:

- default log file: `run_logs/flaresolverr-source-headless.log`
- default pid file: `run_logs/flaresolverr-source-headless.pid`
- WSLg log file when explicitly selected: `run_logs/flaresolverr-source-wslg.log`
- WSLg pid file when explicitly selected: `run_logs/flaresolverr-source-wslg.pid`

To confirm the service is reachable:

```bash
curl --noproxy '*' -fsS -X POST http://127.0.0.1:8191/v1 \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"sessions.list"}'
```

## Foreground Mode

If you need to see the browser/session logs directly:

```bash
cd /home/dictation/test
bash ./run_flaresolverr_source.sh
```

Use this mode when diagnosing startup failures, challenge handling, or timing issues.

## Stop The Service

```bash
cd /home/dictation/test
bash ./stop_flaresolverr_source.sh
```

## Main fetch_fulltext.py Command

`fetch_fulltext.py` should be run inside the Conda environment `science-fulltext`.

Recommended pattern:

```bash
conda run -n science-fulltext python fetch_fulltext.py \
  --input your.csv \
  --output-dir out \
  --html-fetcher flaresolverr \
  --enable-pdf-fallback \
  --flaresolverr-url http://127.0.0.1:8191/v1
```

If you prefer activating the environment first, use:

```bash
cd /home/dictation/test
conda activate science-fulltext
python fetch_fulltext.py \
  --input your.csv \
  --output-dir out \
  --html-fetcher flaresolverr \
  --enable-pdf-fallback \
  --flaresolverr-url http://127.0.0.1:8191/v1
```

FlareSolverr itself is launched by the local source-workflow scripts and does not need the `science-fulltext` Conda environment. The Conda requirement here is for running `fetch_fulltext.py` and its Python-side dependencies.

## Input CSV Format

The CSV must contain at least:

- `doi`

Optional columns supported by the pipeline:

- `label`
- `publisher`

Minimal example:

```csv
doi
10.1073/pnas.81.23.7500
```

## High-Level Pipeline

For each DOI, `fetch_fulltext.py` runs the following sequence:

1. Normalize the DOI and build an output slug.
2. Try PMC first.
3. If PMC succeeds, convert JATS XML to Markdown and finish.
4. If PMC does not produce a usable result, query Crossref for publisher metadata and candidate URLs.
5. If the publisher is supported, try publisher HTML candidates.
6. If HTML succeeds, save raw HTML and Markdown.
7. If HTML fails and `--enable-pdf-fallback` is enabled, try PDF candidates in a browser context.
8. Write one manifest row per DOI describing the final status and all attempts.

The relevant success statuses are:

- `success_pmc`
- `success_html`
- `success_pdf_fallback`

## How The FlareSolverr HTML Branch Works

When `--html-fetcher flaresolverr` is selected:

1. `fetch_fulltext.py` creates a FlareSolverr session.
2. It tries the publisher's candidate HTML URLs in order.
3. Each URL is fetched through `request.get`.
4. The returned page is checked for challenge markers, redirects, and full-text quality.
5. On success, the HTML is converted to Markdown.
6. The FlareSolverr session is destroyed before the function exits.

Default FlareSolverr fetch settings in `fetch_fulltext.py` are:

- `--flaresolverr-url http://127.0.0.1:8191/v1`
- `--flaresolverr-wait-seconds 8`
- `--flaresolverr-max-timeout-ms 120000`

The local requests to `127.0.0.1:8191` explicitly ignore shell proxy env vars, so a local HTTP proxy does not accidentally intercept the FlareSolverr control traffic.
The helper shell scripts now do the same for startup probes.

## Why PDF Fallback Is Part Of The Main Chain

For some PNAS articles, bypassing the shield is not the same as getting full HTML.

What can happen:

1. FlareSolverr successfully reaches the site and solves the challenge.
2. The publisher's `/doi/full/...` route still redirects to an abstract page such as `/doi/abs/...`.
3. The HTML quality checks correctly reject that page as not full text.

In that case, the main chain does not stop there. It moves to browser-context PDF fallback.

## How The PDF Fallback Works In The FlareSolverr Branch

This is the important part of the kept implementation.

FlareSolverr itself does not provide a real PDF binary download API in its current `v1` interface. So the main chain uses a two-stage approach:

1. FlareSolverr solves the shield and returns:
   - final URL
   - cookies
   - browser user-agent
   - rendered HTML
2. `fetch_fulltext.py` keeps the cookies and user-agent in memory only.
3. If HTML is rejected and PDF fallback is enabled, Playwright launches a browser context.
4. The context is seeded with the FlareSolverr-derived cookies and user-agent.
5. The script visits PDF candidate URLs and waits for a real browser download.
6. The downloaded PDF is converted to Markdown.

This gives you:

- FlareSolverr for shield bypass
- Playwright for true browser download behavior
- no dependence on `storage_state.json`

## Output Layout

Given `--output-dir out`, the main output tree is:

- `out/manifest.jsonl`
  One JSON line per DOI, with final result plus attempt history.
- `out/raw/xml/`
  Raw PMC XML when the PMC path succeeds.
- `out/raw/html/`
  Raw publisher HTML when the HTML path succeeds.
- `out/raw/pdf/`
  Raw PDF when the PDF fallback path succeeds.
- `out/markdown/`
  Final Markdown output.
- `out/logs/`
  Failure artifacts such as HTML snapshots, screenshots, and structured failure JSON.

## Manifest Semantics

Each manifest row includes:

- `doi`
- `publisher`
- `html_fetcher`
- `selected_source`
- `source_url`
- `status`
- `raw_path`
- `markdown_path`
- `error_kind`
- `attempts`

When the FlareSolverr HTML path fails but the PDF fallback succeeds, the manifest will usually look like this at a high level:

1. `publisher_html` attempt fails with `redirected_to_abstract`
2. `pdf_fallback` attempt succeeds
3. Final row status becomes `success_pdf_fallback`

## Failure Artifacts

When HTML fetching fails in the FlareSolverr branch, the pipeline can write:

- `logs/<slug>.failure.html`
- `logs/<slug>.failure.png`
- `logs/<slug>.failure.response.json`
- `logs/<slug>.html-failure.json`

Important detail:

- The logged FlareSolverr response is redacted before being written to disk, so cookie values are not stored in clear text.
- The in-memory cookie seed used for PDF fallback is not written into the manifest.

## Verified Example

This chain has already been validated on this machine against:

- `10.1126/science.aeg3511`
- `10.1126/science.ady3136`
- `10.1073/pnas.81.23.7500`

As of 2026-04-14, the observed behavior for recent `Science` DOIs is:

1. A plain `curl` request to the same `Science` full-text URL still receives a Cloudflare challenge.
2. The explicit WSLg FlareSolverr route can still fetch HTML from `https://www.science.org/doi/full/...`.
3. `10.1126/science.aeg3511` finishes with `success_html`.
4. `10.1126/science.ady3136` also finishes with `success_html`, and the generated Markdown contains sections such as `Structured Abstract`, `Discussion`, and `Materials and methods`.

Observed behavior for the PNAS DOI:

1. FlareSolverr successfully bypasses the challenge.
2. The HTML route is still rejected as abstract-only or redirected-to-abstract.
3. The seeded Playwright PDF fallback succeeds.
4. Final status is `success_pdf_fallback`.

This means the validated results in this directory now cover both cases:

- recent `Science` examples that reach `success_html` directly
- a `PNAS` example where `--enable-pdf-fallback` remains part of the normal command

## Practical Operating Procedure

For a normal run:

1. `cd /home/dictation/test`
2. `bash ./setup_flaresolverr_source.sh`
3. `bash ./start_flaresolverr_source.sh`
4. `conda run -n science-fulltext python fetch_fulltext.py --input your.csv --output-dir out --html-fetcher flaresolverr --enable-pdf-fallback --flaresolverr-url http://127.0.0.1:8191/v1`
5. `bash ./stop_flaresolverr_source.sh`

## Troubleshooting

### Service Does Not Start

Check:

- `.work/FlareSolverr` exists
- `.venv-flaresolverr` exists
- `.flaresolverr/.../chrome` exists
- if `HEADLESS=true`, `Xvfb` is installed and `command -v Xvfb` succeeds
- the current preset's log file for the actual startup error
- if the default headless preset fails on this WSLg host, try `.env.flaresolverr-source-wslg` explicitly

If setup looks incomplete, rerun:

```bash
bash ./setup_flaresolverr_source.sh
```

### FlareSolverr Is Reachable But fetch_fulltext.py Says Timeout

Check:

- the service really answers `sessions.list`
- the listener PID is still alive a few seconds later
- `ss -ltnp '( sport = :8191 )'` still shows a live Python listener on `127.0.0.1:8191`
- foreground mode for detailed logs
- local WSLg browser launch is healthy

On this host, one specific failure mode was:

- the service was launched with a plain `nohup ... &`
- startup probing saw a brief successful `sessions.list`
- the background child was then reaped after the parent launcher exited
- `fetch_fulltext.py` later failed with `flaresolverr_timeout`

The kept remedy is:

- use `start_flaresolverr_source.sh` as kept in this directory, which now prefers `setsid`
- do not replace it with a plain `nohup` launcher

You can also temporarily increase:

- `--flaresolverr-wait-seconds`
- `--flaresolverr-max-timeout-ms`

### HTML Fails With redirected_to_abstract

This is not necessarily a shield failure.

For PNAS, this often means:

- FlareSolverr reached the page successfully
- but the publisher still served an abstract route instead of full HTML

The intended remedy is:

- keep `--enable-pdf-fallback` enabled

### PDF Fallback Does Not Trigger

Look at:

- `logs/<slug>.pdf-failure.html`
- `logs/<slug>.pdf-failure.png`
- `logs/<slug>.pdf-failure.json`

Likely causes:

- the publisher did not trigger a browser download
- the response was not a real PDF
- the browser seed cookies were insufficient for that target

### Proxy-Related Confusion

The local FlareSolverr control calls are already made with proxy env bypass, so `127.0.0.1:8191` should not go through the shell's proxy settings.

If the publisher traffic itself needs a proxy, that is a separate concern from the local control channel.

## Current Defaults

The kept scripts now default to the WSLg env file:
The kept scripts now default to the headless env file:

- `run_flaresolverr_source.sh`
- `start_flaresolverr_source.sh`
- `stop_flaresolverr_source.sh`
- `setup_flaresolverr_source.sh`

For cross-host portability, the shortest default commands are now:

```bash
cd /home/dictation/test
bash ./setup_flaresolverr_source.sh
bash ./start_flaresolverr_source.sh
conda run -n science-fulltext python fetch_fulltext.py --input your.csv --output-dir out --html-fetcher flaresolverr --enable-pdf-fallback
bash ./stop_flaresolverr_source.sh
```

On this specific WSLg host, the shortest verified working commands still use `.env.flaresolverr-source-wslg` explicitly:

```bash
cd /home/dictation/test
bash ./setup_flaresolverr_source.sh ./.env.flaresolverr-source-wslg
bash ./start_flaresolverr_source.sh ./.env.flaresolverr-source-wslg
conda run -n science-fulltext python fetch_fulltext.py --input your.csv --output-dir out --html-fetcher flaresolverr --enable-pdf-fallback --flaresolverr-url http://127.0.0.1:8191/v1
bash ./stop_flaresolverr_source.sh ./.env.flaresolverr-source-wslg
```

## Bottom Line

If you only want the working path, remember just this:

1. Start the local WSLg FlareSolverr service.
2. Run `fetch_fulltext.py` with `--html-fetcher flaresolverr --enable-pdf-fallback`.
3. Let FlareSolverr solve the shield.
4. Let Playwright perform the seeded browser-context PDF download when full HTML is not available.
