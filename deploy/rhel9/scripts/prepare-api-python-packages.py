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


SOURCE_ONLY_PACKAGES = {
    "annoy": "1.17.3",
}


def wheel_record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def create_fake_wheel(fake_dir: Path, name: str, version: str) -> Path:
    normalized = name.replace("-", "_")
    dist_info = f"{normalized}-{version}.dist-info"
    wheel_name = f"{normalized}-{version}-py3-none-any.whl"
    wheel_path = fake_dir / wheel_name
    files: dict[str, bytes] = {
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.1\n"
            f"Name: {name}\n"
            f"Version: {version}\n"
            "Summary: Temporary resolver-only wheel; do not deploy.\n"
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
        fake_wheels = [
            create_fake_wheel(fake_dir, name, version)
            for name, version in SOURCE_ONLY_PACKAGES.items()
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

        for fake_wheel in fake_wheels:
            copied = package_dir / fake_wheel.name
            if copied.exists():
                copied.unlink()

    for name, version in SOURCE_ONLY_PACKAGES.items():
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--dest",
                str(package_dir),
                "--no-deps",
                "--no-binary=:all:",
                f"{name}=={version}",
            ],
            env,
        )

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
