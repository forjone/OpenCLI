from utils.subtitle import parse_subtitle


def test_srt():
    src = """1
00:00:01,000 --> 00:00:03,500
你好，世界

2
00:00:04,000 --> 00:00:05,200
今天我们讲 Python
"""
    assert parse_subtitle(src, "x.srt") == "你好，世界\n今天我们讲 Python"


def test_vtt():
    src = """WEBVTT

NOTE this is a comment

00:00:01.000 --> 00:00:03.500
Hello world

00:00:04.000 --> 00:00:05.200
This is a test
"""
    assert parse_subtitle(src, "x.vtt") == "Hello world\nThis is a test"


def test_ass():
    src = """[Script Info]
Title: foo

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.50,Default,,0,0,0,,{\\an8}你好\\N世界
Dialogue: 0,0:00:04.00,0:00:05.00,Default,,0,0,0,,今天讲 Python
"""
    out = parse_subtitle(src, "x.ass")
    assert "你好 世界" in out
    assert "今天讲 Python" in out
    assert "{" not in out  # tag stripped


def test_lrc():
    src = """[ti:title]
[00:01.23]第一行歌词
[00:05.67]第二行歌词
"""
    out = parse_subtitle(src, "x.lrc")
    assert out == "第一行歌词\n第二行歌词"


def test_empty_returns_empty():
    assert parse_subtitle("\n\n   \n", "x.srt") == ""


def test_unknown_extension_strips_timestamps_anyway():
    # Falls through to SRT-like parser
    src = "1\n00:00:01,000 --> 00:00:03,500\nhello\n"
    assert parse_subtitle(src, "x.unknown") == "hello"
