"""Run the frozen 3.0 package from two independent directories."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "dist-2.0.1-test-3.0.0.24268-r7" / "War3ReforgedTrainer-v2.0.1-test.exe"


def run_copy(source: Path, work_dir: Path, index: int) -> dict[str, object]:
    target_dir = work_dir / f"client-{index}" / "nested" / "bin"
    target_dir.mkdir(parents=True)
    target = target_dir / "War3ReforgedTrainer.exe"
    shutil.copy2(source, target)
    report_path = target_dir / "runtime-self-test.json"
    environment = os.environ.copy()
    environment["__COMPAT_LAYER"] = "RunAsInvoker"
    completed = subprocess.run(
        [str(target), "--runtime-self-test", str(report_path)],
        cwd=work_dir / f"client-{index}",
        env=environment,
        timeout=60,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if completed.returncode != 0 or not report.get("ok") or not report.get("frozen"):
        raise RuntimeError(
            f"copy {index} self-test failed: exit={completed.returncode}, report={report}"
        )
    if report.get("retired_helper_present"):
        raise RuntimeError(f"copy {index} bundled a retired helper")
    return {
        "index": index,
        "path": str(target),
        "cwd": str(work_dir / f"client-{index}"),
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "runtime": report,
    }


def main(argv: list[str]) -> int:
    source = Path(argv[1]).resolve() if len(argv) > 1 else DEFAULT_EXE
    output = Path(argv[2]).resolve() if len(argv) > 2 else ROOT / "analysis" / "cross-device-sim-r7.json"
    if not source.is_file():
        raise FileNotFoundError(source)
    with tempfile.TemporaryDirectory(prefix="war3-24268-portability-") as temporary:
        work_dir = Path(temporary)
        copies = [run_copy(source, work_dir, index) for index in (1, 2)]
    if len({copy["sha256"] for copy in copies}) != 1:
        raise RuntimeError("Independent package copies have different hashes")
    result = {
        "ok": True,
        "scope": "Frozen-package path/cwd portability simulation; not a physical second computer",
        "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "copies": copies,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
    os.replace(temporary, output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
