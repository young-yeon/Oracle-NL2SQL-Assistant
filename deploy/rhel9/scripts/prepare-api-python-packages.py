from __future__ import annotations

import base64
import csv
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


STUB_PACKAGES = {
    "annoy": "1.17.3",
    "hf-xet": "1.4.3",
}

STUB_MODULES = {
    "annoy": (
        '"""Offline deployment stub for optional NeMo embedding dependency."""\n\n'
        "class AnnoyIndex:\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        raise RuntimeError(\n"
        '            "The optional annoy native package is not bundled. "\n'
        '            "This Oracle NL2SQL deployment does not use NeMo KB/embedding indexes. "\n'
        '            "Install the real annoy wheel if those features are enabled."\n'
        "        )\n"
    ),
    "hf-xet": (
        '"""Offline deployment stub for optional Hugging Face Xet dependency."""\n\n'
        '__version__ = "1.4.3"\n\n'
        "def __getattr__(name):\n"
        "    raise RuntimeError(\n"
        '        "The optional hf-xet native package is not bundled. "\n'
        '        "HF_HUB_DISABLE_XET=1 is set for this offline deployment."\n'
        "    )\n"
    ),
}


def wheel_record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def create_stub_wheel(fake_dir: Path, name: str, version: str) -> Path:
    normalized = name.replace("-", "_")
    dist_info = f"{normalized}-{version}.dist-info"
    wheel_name = f"{normalized}-{version}-py3-none-any.whl"
    wheel_path = fake_dir / wheel_name
    files: dict[str, bytes] = {
        f"{normalized}/__init__.py": STUB_MODULES[name].encode("utf-8"),
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: {name}\n"
            f"Version: {version}\n"
            "Summary: Offline stub for optional NeMo embedding dependency.\n"
        ).encode("utf-8"),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: oracle-nl2sql offline resolver helper\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode("utf-8"),
    }

    record_rows: list[list[str]] = []
    for path, data in files.items():
        record_rows.append([path, wheel_record_hash(data), str(len(data))])
    record_path = f"{dist_info}/RECORD"
    record_rows.append([record_path, "", ""])

    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, data in files.items():
            zf.writestr(path, data)
        record_buffer = []
        for row in record_rows:
            record_buffer.append(",".join(csv_escape(value) for value in row))
        zf.writestr(record_path, "\n".join(record_buffer) + "\n")
    return wheel_path


def csv_escape(value: str) -> str:
    output = []
    writer = csv.writer(output := CsvList())
    writer.writerow([value])
    return output.value.strip()


class CsvList(list[str]):
    @property
    def value(self) -> str:
        return "".join(self)

    def write(self, value: str) -> None:
        self.append(value)


def run(command: list[str], env: dict[str, str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True, env=env)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    requirements = repo_root / "apps/api/requirements.txt"
    package_dir = repo_root / "deploy/rhel9/offline/wheels/api-py312-linux-amd64"
    package_dir.mkdir(parents=True, exist_ok=True)

    ready = package_dir / ".ready"
    if ready.exists():
        ready.unlink()

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PIP_PROGRESS_BAR", "off")

    with tempfile.TemporaryDirectory(prefix="oracle-nl2sql-fake-wheels-") as temp:
        fake_dir = Path(temp)
        stub_wheels = [
            create_stub_wheel(fake_dir, name, version)
            for name, version in STUB_PACKAGES.items()
        ]
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--dest",
                str(package_dir),
                "--find-links",
                str(fake_dir),
                "--only-binary=:all:",
                "--implementation",
                "cp",
                "--python-version",
                "3.12",
                "--abi",
                "cp312",
                "--platform",
                "manylinux_2_34_x86_64",
                "--platform",
                "manylinux_2_28_x86_64",
                "--platform",
                "manylinux2014_x86_64",
                "-r",
                str(requirements),
            ],
            env,
        )

        for stub_wheel in stub_wheels:
            shutil.copy2(stub_wheel, package_dir / stub_wheel.name)

    for source_package in package_dir.glob("*.tar.gz"):
        source_package.unlink()
    for source_package in package_dir.glob("*.zip"):
        source_package.unlink()

    run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--dest",
            str(package_dir),
            "--only-binary=:all:",
            "setuptools",
            "wheel",
        ],
        env,
    )

    ready.write_text("ready\n", encoding="utf-8")
    print(f"API packagehouse ready: {package_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
