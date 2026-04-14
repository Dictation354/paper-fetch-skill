# FlareSolverr Source Workflow

## Goal

Run the FlareSolverr source workflow with the preset that matches your host.

The script default is now the portable headless preset:

- official upstream source code
- `HEADLESS=true`
- `Xvfb`
- no Docker sidecar dependency

On this specific WSLg host, the verified working route is still the explicit WSLg preset `.env.flaresolverr-source-wslg`.
The portable headless default is kept for better reuse on desktop Linux and headless servers, but on this host the official `Xvfb` route can fail because `/tmp/.X11-unix` is mounted read-only.

## Recommended Presets

| Environment | Recommended preset | Mode | Why this is the default recommendation |
| --- | --- | --- | --- |
| WSLg | `.env.flaresolverr-source-wslg` | `HEADLESS=false` | Best when you explicitly want the visible WSLg browser path and interactive debugging. |
| Desktop Linux | `.env.flaresolverr-source-headless` | `HEADLESS=true` + `Xvfb` | More portable for long-running background use and less dependent on the current desktop session state. |
| Headless server | `.env.flaresolverr-source-headless` | `HEADLESS=true` + `Xvfb` | Best fit for SSH, systemd, tmux, CI, and machines with no real display session. |

## One-Time Setup

```bash
cd /home/dictation/test
bash ./setup_flaresolverr_source.sh
```

The default preset in this directory is `.env.flaresolverr-source-headless`.
Because that preset uses `HEADLESS=true`, make sure the `Xvfb` binary is installed first.
On Debian/Ubuntu systems, that usually means installing the `xvfb` package:

```bash
sudo apt-get update
sudo apt-get install -y xvfb
```

The explicit WSLg preset in this directory is `.env.flaresolverr-source-wslg`.
That preset uses `HEADLESS=false`, so it does not rely on `Xvfb`.
On this host, that explicit WSLg preset remains the verified local path.

## Main Chain

The scripts now default to the headless preset, but the verified chain on this host still uses the explicit WSLg preset:

```bash
cd /home/dictation/test
bash ./start_flaresolverr_source.sh ./.env.flaresolverr-source-wslg
```

When `HEADLESS=false`, the start script launches FlareSolverr through `script` so the headful browser keeps a PTY even in background mode.
The startup probe also bypasses shell proxy settings, so `127.0.0.1:8191` is checked directly instead of through a local HTTP proxy.

## Use With fetch_fulltext.py

After the WSLg service is up on `http://127.0.0.1:8191/v1`, `fetch_fulltext.py` can use it as an optional HTML backend:

```bash
cd /home/dictation/test
python fetch_fulltext.py \
  --input your.csv \
  --output-dir out \
  --html-fetcher flaresolverr \
  --enable-pdf-fallback \
  --flaresolverr-url http://127.0.0.1:8191/v1
```

Default behavior is unchanged. If you do not pass `--html-fetcher flaresolverr`, the script still uses the existing Playwright HTML path.

For PNAS-like cases where the HTML route lands on an abstract page, `--enable-pdf-fallback` now reuses the FlareSolverr-solved cookies and user-agent to seed the Playwright browser context before downloading the PDF.

## Verified Results On This Host

As of 2026-04-14, this workflow has been rechecked on this host with recent `Science` DOIs:

- `10.1126/science.aeg3511` -> `success_html`
- `10.1126/science.ady3136` -> `success_html`

For the tested `Science` URLs, plain `curl` still hit a Cloudflare challenge, but the explicit WSLg FlareSolverr path was able to fetch the `/doi/full/...` HTML successfully.

The previously kept `PNAS` behavior remains relevant: some `PNAS` HTML routes can still land on abstract pages, so `--enable-pdf-fallback` should still be treated as part of the normal command for those targets.

## Start The Service

```bash
cd /home/dictation/test
bash ./start_flaresolverr_source.sh ./.env.flaresolverr-source-wslg
```

Important dependency note:

- `HEADLESS=true` requires the `Xvfb` package and an available `Xvfb` binary
- the WSLg preset here uses `HEADLESS=false`, so it uses the WSLg display instead of `Xvfb`
- on this host, use the WSLg preset explicitly if the default headless preset fails with the read-only `/tmp/.X11-unix` error

If you want to probe the service manually, bypass proxies for the local control port:

```bash
curl --noproxy '*' -fsS -X POST http://127.0.0.1:8191/v1 \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"sessions.list"}'
```

## Stop The Service

```bash
cd /home/dictation/test
bash ./stop_flaresolverr_source.sh
```

## Foreground Mode

```bash
cd /home/dictation/test
bash ./run_flaresolverr_source.sh
```
