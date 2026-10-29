# cam-watch

[![CI](https://github.com/SuzalShrestha/cam-watch/actions/workflows/ci.yml/badge.svg)](https://github.com/SuzalShrestha/cam-watch/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

A small, self-hosted watcher for IP cameras. It finds people, pets and other objects on your camera stream.
When it finds one, it records a clip and sends you a photo on Telegram. No cloud, no subscription:
everything runs on your own computer.

- **Object detection** with [Ultralytics YOLO](https://github.com/ultralytics/ultralytics): any of the 80 COCO classes (person, cat, dog, car, ...).
- **Clips** from the main stream, saved without re-encoding (`ffmpeg -c copy`), so the CPU load stays low.
- **Telegram alerts** with an annotated photo (optional).
- **Face names** (optional): enroll people, and alerts tell you who was in the clip.
- **Daily timelapse**: one frame a minute, joined into a 60 s video each night.
- **Android TV** (optional): show the live stream on your TV when something happens.
- **Any camera** that gives an RTSP, HTTP/MJPEG or HLS stream. H.264 and H.265.

About 360 lines of Python in 3 files. Read them before you run them.

## Requirements

- Python 3.10 or newer
- [ffmpeg](https://ffmpeg.org/download.html) (`ffmpeg` and `ffprobe` on your `PATH`)
- A camera with a network stream (see [Camera URLs](#camera-urls))
- `adb`, only for the Android TV feature

A Raspberry Pi 5, a mini PC or an old laptop is sufficient for one camera with `yolo11n` on the sub stream.

## Install

```bash
git clone https://github.com/SuzalShrestha/cam-watch.git
cd cam-watch
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p ~/.config/cam-watch
cp config.example.ini ~/.config/cam-watch/config.ini
chmod 600 ~/.config/cam-watch/config.ini
```

Edit `~/.config/cam-watch/config.ini`: set the camera `url`, `detect_url`, `user` and `password`.
All settings are explained in [config.example.ini](config.example.ini).

## Run

```bash
.venv/bin/python cam.py --once   # self-check: gets one frame, runs detection, saves clips/once.jpg
.venv/bin/python cam.py          # watch until stopped
```

The first run downloads the YOLO model to `models/`. The face models download on first use, and their SHA-256 is checked.

### Timelapse

```bash
.venv/bin/python timelapse.py snap             # save one frame; run it every minute
.venv/bin/python timelapse.py build            # build yesterday's video; run it at 00:05
.venv/bin/python timelapse.py build 20260131   # build a given day
```

### Faces

Record a clip where only one person is in view and looks at the camera. Then:

```bash
.venv/bin/python cam.py --enroll alice clips/20260131-101500.mp4
```

You can also put clear photos in `faces/alice/*.jpg`. Face naming is off until one person is enrolled.

### More than one camera

Run one process for each camera. Give each one its own config file and its own `data_dir`:

```bash
CAM_WATCH_CONFIG=~/.config/cam-watch/garage.ini .venv/bin/python cam.py
```

## Camera URLs

Replace `HOST` with the camera IP. Put the login in `user` and `password` in the config.
Most cameras have a **main** stream (high resolution, for clips) and a **sub** stream (low resolution, for detection).

| Brand | Main stream (`url`) | Sub stream (`detect_url`) |
|---|---|---|
| Hikvision, Annke, many OEMs | `rtsp://HOST:554/Streaming/Channels/101` | `rtsp://HOST:554/Streaming/Channels/102` |
| Dahua, Amcrest, Lorex | `rtsp://HOST:554/cam/realmonitor?channel=1&subtype=0` | `rtsp://HOST:554/cam/realmonitor?channel=1&subtype=1` |
| Reolink | `rtsp://HOST:554/h264Preview_01_main` | `rtsp://HOST:554/h264Preview_01_sub` |
| Uniview, Uniarch | `rtsp://HOST:554/media/video1` | `rtsp://HOST:554/media/video2` |
| TP-Link Tapo, VIGI | `rtsp://HOST:554/stream1` | `rtsp://HOST:554/stream2` |
| Axis | `rtsp://HOST/axis-media/media.amp` | `rtsp://HOST/axis-media/media.amp?resolution=640x360` |
| Foscam | `rtsp://HOST:88/videoMain` | `rtsp://HOST:88/videoSub` |
| UniFi Protect | copy the RTSP URL from the camera settings in Protect | lower-quality URL from the same page |
| ESP32-CAM | `http://HOST:81/stream` | (same) |

Notes:

- Only the Uniview/Uniarch row is tested by the author. The other rows come from vendor documents and can change with the model or firmware. If your camera works, please [tell us](../../issues/new?template=camera_works.md).
- Reolink cameras with H.265 use `h265Preview_01_main`. Tapo cameras need a camera account, made in the Tapo app under *Advanced settings*.
- To find an unknown URL, use [ONVIF Device Manager](https://sourceforge.net/projects/onvifdm/), or test a URL with `ffprobe -rtsp_transport tcp "rtsp://user:pass@HOST:554/PATH"`.
- **Cameras with no RTSP** (USB webcams, Ring, Nest, Blink, Wyze): re-stream them as RTSP with [go2rtc](https://github.com/AlexxIT/go2rtc), [MediaMTX](https://github.com/bluenviron/mediamtx) or [docker-wyze-bridge](https://github.com/mrlt8/docker-wyze-bridge), then use that RTSP URL.

## Run as a service

### Linux (systemd)

`~/.config/systemd/user/cam-watch.service`:

```ini
[Unit]
Description=cam-watch
After=network-online.target

[Service]
WorkingDirectory=%h/cam-watch
ExecStart=%h/cam-watch/.venv/bin/python cam.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now cam-watch
loginctl enable-linger "$USER"   # keep it running after you log out
```

Timelapse, with `crontab -e`:

```
* * * * * cd ~/cam-watch && .venv/bin/python timelapse.py snap >> timelapse.log 2>&1
5 0 * * * cd ~/cam-watch && .venv/bin/python timelapse.py build >> timelapse.log 2>&1
```

### macOS (launchd)

`~/Library/LaunchAgents/cam-watch.plist` (change `/Users/you`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>cam-watch</string>
  <key>ProgramArguments</key><array>
    <string>/Users/you/cam-watch/.venv/bin/python</string>
    <string>/Users/you/cam-watch/cam.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/you/cam-watch</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/Users/you/cam-watch/cam.log</string>
  <key>StandardErrorPath</key><string>/Users/you/cam-watch/cam.log</string>
</dict></plist>
```

```bash
launchctl load ~/Library/LaunchAgents/cam-watch.plist
```

For the timelapse, make two more plists that run `timelapse.py snap` with `StartInterval` 60,
and `timelapse.py build` with `StartCalendarInterval` Hour 0, Minute 5.

## Tuning

- Too many false alerts: increase `confidence`, or use a bigger `model` (`yolo11s.pt`).
- Missed events: decrease `confidence`, or increase `checks_per_second`.
- High CPU: set `detect_url` to the sub stream, or decrease `checks_per_second`.
- Wrong face names: change the `FACE_*` values at the top of `cam.py`.

## Privacy and the law

Video and face recognition of people are personal data in many countries (for example GDPR in the EU).
Before you record or recognize people, find the local rules: signs, consent, and how long you keep footage.
Enroll only the faces of people who agree. All data stays on your computer, except the photos and videos that you send to Telegram.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Camera reports are the most useful contribution.

## License

[AGPL-3.0](LICENSE). cam-watch uses Ultralytics YOLO, which is AGPL-3.0, so this project uses the same license.
The face models come from [opencv_zoo](https://github.com/opencv/opencv_zoo): YuNet (MIT) and SFace (Apache-2.0).
