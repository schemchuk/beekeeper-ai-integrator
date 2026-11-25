import subprocess
import sys

import pytest

from beekeeper import __version__
from beekeeper.cli import main


def test_no_arguments_prints_help(capsys):
    assert main([]) == 0
    assert "usage: beekeeper" in capsys.readouterr().out


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_module_entry_point():
    result = subprocess.run(
        [sys.executable, "-m", "beekeeper", "--help"], capture_output=True, text=True, check=True
    )
    assert "usage: beekeeper" in result.stdout
