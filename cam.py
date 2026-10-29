"""Watch a camera stream for people, pets or other objects. On a hit: record a clip, send a Telegram photo.

Works with any camera ffmpeg and OpenCV can open (RTSP, HTTP/MJPEG, HLS); see README for brand URLs.
Config: $CAM_WATCH_CONFIG or ~/.config/cam-watch/config.ini. Run `python cam.py --once` as a self-check.
Faces: after each person clip, known faces are named. Add a person with `python cam.py --enroll NAME CLIP.mp4`
(a clip where only they are in view), or put their photos in faces/NAME/.
"""
import hashlib, os, subprocess, sys, threading, time, urllib.request
from datetime import datetime
from pathlib import Path

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
import cv2
from ultralytics import YOLO

from common import HERE, data_dir, ff_input, frame_step, load_config, log, send_telegram, stream_urls

cfg = load_config()
MAIN, DETECT = stream_urls(cfg)
DATA = data_dir(cfg)
CLIPS, FACES, MODELS = DATA / "clips", DATA / "faces", HERE / "models"
det_cfg = cfg["detect"]
OBJECTS = [s.strip() for s in det_cfg.get("objects", "person, cat, dog, bird").split(",") if s.strip()]
CONF = det_cfg.getfloat("confidence", 0.5)
CHECKS_PER_SECOND = det_cfg.getfloat("checks_per_second", 2)
CLIP_SECONDS = det_cfg.getint("clip_seconds", 30)  # fixed-length clip per event
COOLDOWN = det_cfg.getint("cooldown", 60)          # seconds between events
YOLO_MODEL = det_cfg.get("model", "yolo11n.pt")    # downloaded on first run
# Face knobs: tune for your camera.
FACE_MIN_PX = 60       # smaller "faces" are mostly posters, packaging and screens
FACE_MATCH = 0.363     # SFace cosine threshold from the OpenCV model docs
FACE_MIN_SCORE = 0.85  # real faces score 0.86-0.93; printed faces, heads looking down and IR shadows score lower
ENROLL_MIN_SCORE = 0.9
FACE_MODELS = {  # file: (opencv_zoo folder, sha256)
    "face_detection_yunet_2023mar.onnx": ("face_detection_yunet", "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
    "face_recognition_sface_2021dec.onnx": ("face_recognition_sface", "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"),
}


def detect(model, classes, frame):
    """Return the annotated frame and a summary like "person x1, cat x2" ("" when nothing found)."""
    r = model(frame, classes=list(classes), conf=CONF, verbose=False)[0]
    names = [classes[int(c)] for c in r.boxes.cls]
    return r.plot(), ", ".join(f"{k} x{names.count(k)}" for k in dict.fromkeys(names))


def send_photo(img, caption):
    ok, jpg = cv2.imencode(".jpg", img)
    send_telegram(cfg["telegram"], "sendPhoto", "photo", "p.jpg", jpg.tobytes(), "image/jpeg", caption)


def hevc_tag():
    """QuickTime and browsers play HEVC mp4 only with the hvc1 tag, and ffmpeg rejects that tag for H.264."""
    try:
        codec = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name",
                                "-of", "csv=p=0", *ff_input(MAIN)], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:  # clips still record, they just keep ffmpeg's default tag
        codec = f"unknown ({e})"
    log(f"main stream codec: {codec}")
    return ["-tag:v", "hvc1"] if codec == "hevc" else []


def record(tag):
    name = CLIPS / f"{datetime.now():%Y%m%d-%H%M%S}.mp4"
    # ponytail: one clip at a time, fixed length; extend or merge events if clip_seconds proves too short
    return subprocess.Popen(
        ["ffmpeg", "-v", "error", *ff_input(MAIN), "-t", str(CLIP_SECONDS), "-c:v", "copy", *tag, "-c:a", "aac", str(name)],
        stdin=subprocess.DEVNULL,
    ), name


def model_file(name):
    """Path to a face model, downloaded from opencv_zoo and checked on first use."""
    p = MODELS / name
    if not p.exists():
        folder, sha = FACE_MODELS[name]
        log(f"downloading {name}")
        data = urllib.request.urlopen(f"https://github.com/opencv/opencv_zoo/raw/main/models/{folder}/{name}", timeout=300).read()
        if hashlib.sha256(data).hexdigest() != sha:
            raise RuntimeError(f"checksum mismatch for {name}")
        MODELS.mkdir(exist_ok=True)
        tmp = p.with_suffix(f".{threading.get_ident()}.part")  # face threads can download at the same time
        tmp.write_bytes(data)
        tmp.replace(p)
    return str(p)


def face_tools():
    # new objects per call: OpenCV dnn nets are not thread-safe
    return (cv2.FaceDetectorYN.create(model_file("face_detection_yunet_2023mar.onnx"), "", (0, 0), 0.6),
            cv2.FaceRecognizerSF.create(model_file("face_recognition_sface_2021dec.onnx"), ""))


def faces_in(det, rec, img, min_score=FACE_MIN_SCORE):
    det.setInputSize((img.shape[1], img.shape[0]))
    found = det.detect(img)[1]
    return [(f, rec.feature(rec.alignCrop(img, f))) for f in ([] if found is None else found)
            if f[2] >= FACE_MIN_PX and f[-1] >= min_score]


def clip_frames(path):
    """One frame per second of a clip."""
    cap, i = cv2.VideoCapture(str(path)), 0
    every = frame_step(cap.get(cv2.CAP_PROP_FPS), 1)
    while True:
        ok, img = cap.read()
        if not ok:
            return
        i += 1
        if i % every == 0:
            yield img


def enroll(name, clip):
    """Save the biggest face of each second of the clip (up to 10) to faces/NAME/."""
    det, rec = face_tools()
    out = FACES / name
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for img in clip_frames(clip):
        got = faces_in(det, rec, img, ENROLL_MIN_SCORE)
        if not got:
            continue
        x, y, w, h = (int(v) for v in max(got, key=lambda g: g[0][2])[0][:4])
        cv2.imwrite(str(out / f"{Path(clip).stem}-{n}.jpg"), img[max(0, y - h):y + 2 * h, max(0, x - w):x + 2 * w])
        n += 1
        if n == 10:
            break
    print(f"enrolled {n} face crops for {name} in {out}" if n else "no clear face found: record a clip looking at the camera")


def name_faces(clip):
    """Return (frame with the biggest face, labelled; set of names). Unknown faces are named "unknown"."""
    det, rec = face_tools()
    known = [(p.parent.name, e) for p in FACES.glob("*/*.jpg") for _, e in faces_in(det, rec, cv2.imread(str(p)))[:1]]
    best, best_w, names = None, 0, set()
    for img in clip_frames(clip):
        got = faces_in(det, rec, img)
        for f, emb in got:
            score, who = max([(rec.match(e, emb, cv2.FaceRecognizerSF_FR_COSINE), n) for n, e in known], default=(0, ""))
            who = who if score >= FACE_MATCH else "unknown"
            names.add(who)
            x, y, w, h = (int(v) for v in f[:4])
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0) if who != "unknown" else (0, 0, 255), 3)
            cv2.putText(img, f"{who} {score:.2f}", (x, y - 8), 0, 1.0, (255, 255, 255), 2)
        if got and max(g[0][2] for g in got) > best_w:
            best, best_w = img, max(g[0][2] for g in got)
    return best, names


def face_report(proc, clip):
    proc.wait()
    try:
        img, names = name_faces(clip)
    except Exception as e:  # faces are extra; never stop the recorder
        return log(f"faces failed: {e}")
    log(f"faces in {clip.name}: {', '.join(sorted(names)) or 'none'}")
    if names:
        send_photo(img, f"Faces in {clip.stem}: {', '.join(sorted(names))}")


def show_on_tv():
    """Wake an Android TV device over adb (CEC switches the TV to it) and play the main stream in VLC; Home after the clip."""
    host = cfg.get("tv", "host", fallback="")
    if not host:
        return
    dev = f"{host}:5555"
    adb = lambda *a: subprocess.run(["adb", "-s", dev, *a], capture_output=True, timeout=20)
    try:
        subprocess.run(["adb", "connect", dev], capture_output=True, timeout=10)
        adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
        adb("shell", "am", "start", "-p", "org.videolan.vlc", "-a", "android.intent.action.VIEW", "-d", MAIN)
        # ponytail: main stream may be heavy for a cheap stick; play DETECT if it stutters
        threading.Timer(CLIP_SECONDS, lambda: adb("shell", "input", "keyevent", "KEYCODE_HOME")).start()
    except Exception as e:  # the TV is optional; never stop recording
        log(f"tv failed: {e}")


def main():
    if sys.argv[1:2] == ["--enroll"]:
        if len(sys.argv) != 4:
            sys.exit("usage: cam.py --enroll NAME CLIP.mp4")
        return enroll(sys.argv[2], sys.argv[3])
    MODELS.mkdir(exist_ok=True)
    CLIPS.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(MODELS / YOLO_MODEL))
    classes = {i: n for i, n in model.names.items() if n in OBJECTS}
    if missing := set(OBJECTS) - set(classes.values()):
        sys.exit(f"[detect] objects not known to {YOLO_MODEL}: {', '.join(missing)}. Known: {', '.join(model.names.values())}")
    if "--once" in sys.argv:
        cap = cv2.VideoCapture(DETECT)
        for _ in range(20):  # the first frames after connect can be half-decoded
            ok, frame = cap.read()
        assert ok, "no frame from the detect stream"
        img, seen = detect(model, classes, frame)
        cv2.imwrite(str(CLIPS / "once.jpg"), img)
        print(f"self-check ok: frame {frame.shape}, seen={seen or 'nothing'}, saved {CLIPS / 'once.jpg'}")
        return
    tag = hevc_tag()
    last, proc, i = 0.0, None, 0
    while True:
        cap = cv2.VideoCapture(DETECT)
        log("connected" if cap.isOpened() else "connect failed, retry in 10 s")
        step = frame_step(cap.get(cv2.CAP_PROP_FPS), CHECKS_PER_SECOND)
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            i += 1
            if i % step or time.time() - last < COOLDOWN:
                continue
            img, seen = detect(model, classes, frame)
            if seen:
                last = time.time()
                if proc is None or proc.poll() is not None:
                    proc, name = record(tag)
                    log(f"{seen}, recording {name.name}")
                    if "person" in seen and any(FACES.glob("*/*.jpg")):  # off until someone is enrolled
                        threading.Thread(target=face_report, args=(proc, name), daemon=True).start()
                    show_on_tv()
                send_photo(img, f"{seen.capitalize()} at {datetime.now():%T}")
        cap.release()
        time.sleep(10)


if __name__ == "__main__":
    main()
