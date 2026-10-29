"""Config, stream URLs and Telegram upload, shared by cam.py and timelapse.py.

Stdlib only, so the per-minute timelapse run stays light.
"""
import configparser, os, sys, urllib.parse, urllib.request, uuid
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent


def log(msg):
    print(datetime.now().strftime("%F %T"), msg, flush=True)


def load_config(path=None):
    """Read $CAM_WATCH_CONFIG (default ~/.config/cam-watch/config.ini). Optional sections are added empty."""
    path = Path(path or os.environ.get("CAM_WATCH_CONFIG", "~/.config/cam-watch/config.ini")).expanduser()
    cfg = configparser.ConfigParser(interpolation=None)
    if not cfg.read(path) or not cfg.get("camera", "url", fallback=""):
        sys.exit(f"no [camera] url in {path}: copy config.example.ini there and edit it")
    for s in ("detect", "telegram", "tv"):
        if not cfg.has_section(s):
            cfg.add_section(s)
    return cfg


def with_login(url, user="", password=""):
    """Put user:password into the URL, percent-encoded, unless the URL already has a login."""
    u = urllib.parse.urlsplit(url)
    if not user or u.username:
        return url
    q = lambda s: urllib.parse.quote(s, safe="")
    return u._replace(netloc=f"{q(user)}:{q(password)}@{u.netloc}").geturl()


def stream_urls(cfg):
    """(main url, detect url). The detect url falls back to the main one."""
    cam = cfg["camera"]
    login = cam.get("user", ""), cam.get("password", "")
    return with_login(cam["url"], *login), with_login(cam.get("detect_url") or cam["url"], *login)


def data_dir(cfg):
    return Path(cfg.get("camera", "data_dir", fallback="") or HERE).expanduser()


def ff_input(url):
    """ffmpeg input args. TCP for RTSP (UDP drops packets on Wi-Fi); other inputs reject the option."""
    return (["-rtsp_transport", "tcp"] if url.startswith("rtsp") else []) + ["-i", url]


def frame_step(fps, per_second):
    """Use every Nth frame to check about per_second frames a second. A bad fps report (0, 90000) counts as 10."""
    fps = fps if 1 <= fps <= 120 else 10
    return max(1, round(fps / per_second))


def send_telegram(tg, method, field, filename, data, mime, caption, timeout=15):
    """Upload one file with sendPhoto or sendVideo. Does nothing without token and chat_id. Never raises."""
    if not (tg.get("token") and tg.get("chat_id")):
        return
    b = uuid.uuid4().hex
    body = b"".join(
        [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in (("chat_id", tg["chat_id"]), ("caption", caption))]
        + [f'--{b}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode(), data, f"\r\n--{b}--\r\n".encode()]
    )
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{tg['token']}/{method}", body, {"Content-Type": f"multipart/form-data; boundary={b}"}
    )
    try:
        urllib.request.urlopen(req, timeout=timeout).read()
    except Exception as e:  # an alert failure must not stop recording
        log(f"telegram failed: {e}")
