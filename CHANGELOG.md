# Changelog

This file follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-29

First public release.

### Added
- Object detection on any RTSP, HTTP/MJPEG or HLS camera stream, with clips, Telegram alerts, face names, daily timelapse and Android TV display.
- Settings in a config file: stream URLs, login, objects, confidence, clip length, cooldown, model, data folder.
- Camera URL table for common brands.
- `--enroll NAME CLIP` command.
- Face models download on first use, with a SHA-256 check.

### Fixed
- Clips from H.264 cameras: the `hvc1` tag is now added only for H.265 streams.
