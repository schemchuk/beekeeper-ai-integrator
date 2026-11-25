import wave

import pytest

from beekeeper.sfx import LIBRARY, RATE, write_sfx


def test_write_sfx_makes_quiet_mono_wavs_that_repeat_exactly(tmp_path):
    paths = write_sfx(set(LIBRARY), tmp_path)
    assert paths == {name: f"sfx/{name}.wav" for name in LIBRARY}
    first = {n: (tmp_path / p).read_bytes() for n, p in paths.items()}
    write_sfx(set(LIBRARY), tmp_path)
    assert first == {n: (tmp_path / p).read_bytes() for n, p in paths.items()}
    for p in paths.values():
        with wave.open(str(tmp_path / p)) as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, RATE)
            assert 0.2 < w.getnframes() / RATE < 3


def test_unknown_sfx_names_the_known_ones(tmp_path):
    with pytest.raises(KeyError, match="unknown sfx thunder; known: keyboard, phone-buzz"):
        write_sfx({"thunder", "keyboard"}, tmp_path)
