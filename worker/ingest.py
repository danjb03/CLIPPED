"""Phase 1 — download a source video with yt-dlp into output/<job_id>/source.mp4."""

import os
import subprocess
import tempfile
import uuid

from paths import job_dir, source_path


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def _auth_args() -> tuple[list[str], str | None]:
    """yt-dlp auth/proxy args from env, plus an optional tempfile to clean up.

    - YTDLP_COOKIES        : raw cookies.txt contents (e.g. exported YouTube
                             cookies) — lets the server download as a logged-in
                             user, bypassing bot/PO-token blocks.
    - YTDLP_COOKIES_FILE   : path to a cookies.txt already on disk.
    - YTDLP_PROXY          : http(s)/socks proxy URL (e.g. a residential proxy).
    """
    args: list[str] = []
    tmp: str | None = None

    cookies_file = os.environ.get("YTDLP_COOKIES_FILE")
    cookies_raw = os.environ.get("YTDLP_COOKIES")
    if cookies_file and os.path.exists(cookies_file):
        args += ["--cookies", cookies_file]
    elif cookies_raw:
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        f.write(cookies_raw)
        f.close()
        tmp = f.name
        args += ["--cookies", tmp]

    proxy = os.environ.get("YTDLP_PROXY")
    if proxy:
        args += ["--proxy", proxy]

    extra = os.environ.get("YTDLP_EXTRA_ARGS")
    if extra:
        args += extra.split()

    return args, tmp


def download(url: str) -> str:
    """Download `url` to output/<job_id>/source.mp4 and return the job_id.

    Raises ValueError on a bad URL and RuntimeError if yt-dlp fails or no mp4
    is produced.
    """
    if not url or not url.strip():
        raise ValueError("url is required")

    job_id = new_job_id()
    jd = job_dir(job_id)
    jd.mkdir(parents=True, exist_ok=True)

    auth_args, cookie_tmp = _auth_args()

    # Best video+audio, merged to mp4. Cap at 1080p — we crop to vertical, so
    # pulling 4K just wastes download time and disk.
    out_tmpl = str(jd / "source.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f",
        "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        "--merge-output-format",
        "mp4",
        *auth_args,
        "-o",
        out_tmpl,
        url.strip(),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise RuntimeError("yt-dlp not found on PATH") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"yt-dlp failed: {e.stderr or e.stdout}") from e
    finally:
        if cookie_tmp and os.path.exists(cookie_tmp):
            os.unlink(cookie_tmp)

    src = source_path(job_id)
    if not src.exists():
        # Merge may have produced a different container; remux the first match.
        produced = sorted(jd.glob("source.*"))
        if not produced:
            raise RuntimeError("yt-dlp produced no output file")
        _remux_to_mp4(produced[0], src)

    return job_id


def _remux_to_mp4(src, dst) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-c", "copy", str(dst)],
        check=True,
        capture_output=True,
        text=True,
    )
