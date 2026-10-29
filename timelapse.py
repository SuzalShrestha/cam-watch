"""Day timelapse. `snap`: save one frame (run it every minute). `build [YYYYMMDD]`: join a day's frames
into timelapse/YYYYMMDD.mp4, send it to Telegram, delete the frames. Default day is yesterday (run it at 00:05).

Stdlib only, so the per-minute run stays light. Config: same file as cam.py.
"""
import subprocess, sys
from datetime import datetime, timedelta

from common import data_dir, ff_input, load_config, log, send_telegram, stream_urls

cfg = load_config()
MAIN = stream_urls(cfg)[0]
OUT = data_dir(cfg) / "timelapse"
FPS = 24          # 1440 frames/day -> 60 s video
TG_LIMIT = 50e6   # Telegram bot upload limit


def snap():
    now = datetime.now()
    d = OUT / "frames" / f"{now:%Y%m%d}"
    d.mkdir(parents=True, exist_ok=True)
    # keyframes only: the first non-key frames after connect can decode half grey
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-skip_frame", "nokey", *ff_input(MAIN),
         "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "4", str(d / f"{now:%H%M%S}.jpg")],
        stdin=subprocess.DEVNULL, timeout=40, check=True,
    )


def send_video(path, caption):
    if path.stat().st_size > TG_LIMIT:
        return log(f"telegram skipped ({path.stat().st_size / 1e6:.1f} MB)")
    send_telegram(cfg["telegram"], "sendVideo", "video", path.name, path.read_bytes(), "video/mp4", caption, timeout=120)


def build(day, send=True):
    frames = OUT / "frames" / day
    jpgs = sorted(frames.glob("*.jpg"))
    if not jpgs:
        return log(f"no frames for {day}")
    video = OUT / f"{day}.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-pattern_type", "glob", "-i", str(frames / "*.jpg"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26", "-movflags", "+faststart", str(video)],
        stdin=subprocess.DEVNULL, check=True,
    )
    log(f"built {video.name} from {len(jpgs)} frames, {video.stat().st_size / 1e6:.1f} MB")
    if send:
        send_video(video, f"Timelapse {day[:4]}-{day[4:6]}-{day[6:]} ({len(jpgs)} min)")
    for j in jpgs:  # only reached when ffmpeg succeeded
        j.unlink()
    frames.rmdir()


if __name__ == "__main__":
    if sys.argv[1:2] == ["snap"]:
        snap()
    elif sys.argv[1:2] == ["build"]:
        build(sys.argv[2] if len(sys.argv) > 2 else f"{datetime.now() - timedelta(days=1):%Y%m%d}")
    else:
        sys.exit("usage: timelapse.py snap | build [YYYYMMDD]")
