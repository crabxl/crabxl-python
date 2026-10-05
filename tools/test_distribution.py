"""Install one wheel or sdist into a clean, platform-native environment and test it."""

import argparse
import os
import subprocess
import tempfile
import venv
from pathlib import Path


def main(pattern):
    files = list(Path("dist").glob(pattern))
    if len(files) != 1:
        raise ValueError(f"Expected one distribution matching {pattern}")
    with tempfile.TemporaryDirectory(prefix="crabxl-package-") as directory:
        venv.EnvBuilder(with_pip=True).create(directory)
        executable = Path(directory) / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        subprocess.run(
            [str(executable), "-m", "pip", "install", f"{files[0].resolve()}[test]"],
            check=True,
        )
        subprocess.run([str(executable), "-m", "pytest", "tests", "-q"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pattern", help="A wheel or sdist glob matching exactly one file"
    )
    main(parser.parse_args().pattern)
