import shutil
import subprocess

import pytest

from beekeeper.check import MAX_BYTES, check_reel, problems


def good() -> dict:
    return {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "43.4", "size": "7554013"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "pix_fmt": "yuv420p",
                "width": 1080,
                "height": 1920,
                "r_frame_rate": "30/1",
            },
            {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000"},
        ],
    }


def test_good_reel_passes():
    assert problems(good()) == []


def test_every_broken_rule_is_reported():
    info = good()
    video, audio = info["streams"]
    video.update(codec_name="hevc", pix_fmt="yuv444p", width=1920, height=1080)
    video["r_frame_rate"] = "30000/1001"
    audio.update(codec_name="mp3", sample_rate="44100")
    info["format"].update(duration="95.0", size=str(MAX_BYTES))
    found = problems(info)
    assert found == [
        "video codec hevc, want h264",
        "pixel format yuv444p, want yuv420p",
        "size 1920x1080, want 1080x1920",
        "frame rate 29.97 fps, want 30",
        "audio codec mp3, want aac",
        "sample rate 44100 Hz, want 48000",
        "length 95.0 s, want 3-90 s",
        "size 20.0 MB, want under 20 MB",
    ]


def test_missing_audio_and_short():
    info = good()
    info["streams"].pop()
    info["format"]["duration"] = "2.0"
    assert problems(info) == ["0 audio streams, want 1", "length 2.0 s, want 3-90 s"]


def test_not_mp4():
    info = good()
    info["format"]["format_name"] = "matroska,webm"
    assert problems(info) == ["container is matroska,webm, want mp4"]


def test_missing_file(tmp_path):
    found, _ = check_reel(tmp_path / "reel_de.mp4")
    assert found == [f"{tmp_path / 'reel_de.mp4'}: not found"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_real_file(tmp_path):
    reel = tmp_path / "reel_de.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error",
            "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30:d=3.5",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-t", "3.5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(reel),
        ],
        check=True,
    )  # fmt: skip
    found, info = check_reel(reel)
    assert found == []
    assert float(info["format"]["duration"]) == pytest.approx(3.5, abs=0.1)
