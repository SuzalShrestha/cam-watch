import pytest

from common import ff_input, frame_step, load_config, stream_urls, with_login


def test_with_login():
    assert with_login("rtsp://10.0.0.5:554/s1", "admin", "p@ss:w/rd") == "rtsp://admin:p%40ss%3Aw%2Frd@10.0.0.5:554/s1"
    assert with_login("rtsp://me:x@10.0.0.5/s1", "admin", "y") == "rtsp://me:x@10.0.0.5/s1"  # URL login wins
    assert with_login("http://10.0.0.5:81/stream") == "http://10.0.0.5:81/stream"


def test_config(tmp_path, monkeypatch):
    ini = tmp_path / "c.ini"
    ini.write_text("[camera]\nurl = rtsp://h/main\nuser = u\npassword = p\n")
    monkeypatch.setenv("CAM_WATCH_CONFIG", str(ini))
    cfg = load_config()
    assert stream_urls(cfg) == ("rtsp://u:p@h/main", "rtsp://u:p@h/main")
    assert cfg["telegram"].get("token") is None  # optional sections exist
    ini.write_text("[camera]\n")
    with pytest.raises(SystemExit):
        load_config()


def test_ff_input():
    assert ff_input("rtsp://h/s") == ["-rtsp_transport", "tcp", "-i", "rtsp://h/s"]
    assert ff_input("http://h/s") == ["-i", "http://h/s"]


def test_frame_step():
    assert frame_step(20, 2) == 10
    assert frame_step(0, 2) == 5      # unknown fps counts as 10
    assert frame_step(90000, 1) == 10
    assert frame_step(5, 10) == 1
