"""Explicit, offline adapter management. Candidates never become active automatically."""

import argparse, hashlib, json, os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from war3_game_profile import (
    load_profile,
    default_profile,
    import_profile,
    installed_profile_directory,
    ProfileCatalog,
)
from war3_capabilities import CapabilitySet
from war3_operations import OPERATIONS


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".adapter-")
    try:
        with os.fdopen(fd, "w", encoding="utf8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inspect")
    p.add_argument("profile", nargs="?", default="profiles/3.0.0.24268.json")
    p = sub.add_parser("import")
    p.add_argument("profile")
    p.add_argument("--directory", default=str(installed_profile_directory()))
    p = sub.add_parser("diagnose")
    p.add_argument("image")
    p = sub.add_parser("candidate")
    p.add_argument("image")
    p.add_argument("--output", required=True)
    p = sub.add_parser("manifest")
    p.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "import":
        print(import_profile(args.profile, args.directory))
        return
    if args.command == "inspect":
        p = load_profile(args.profile)
        caps = CapabilitySet(p)
        report = {
            "id": p.id,
            "digest": p.digest,
            "fingerprint": p.fingerprint,
            "bridge_profile_version": p.data["bridge_profile_version"],
            "compiled_module_checks": {
                name: vars(caps.check(name)) for name in OPERATIONS
            },
            "native_availability": "requires live registered names, signatures, code and machine ABI validation",
        }
    elif args.command == "manifest":
        profile = default_profile()
        root = Path(__file__).resolve().parents[1]
        files = [
            *root.glob("war3_*.py"),
            *root.glob("war3_services/*.py"),
            *root.glob("tools/war3_bridge*.[ch]"),
            *root.glob("profiles/*.json"),
        ]
        report = {
            "baseline": "70446ba",
            "trainer_version": "2.0.7",
            "development_only": True,
            "adapter_version": profile.data["adapter_version"],
            "bridge_profile_version": profile.data["bridge_profile_version"],
            "profile_digest": profile.digest,
            "files": {
                str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(
                    p.read_bytes()
                ).hexdigest()
                for p in sorted(files)
            },
        }
        atomic_json(args.output, report)
    else:
        import pefile

        image = Path(args.image)
        pe = pefile.PE(str(image), fast_load=True)
        fp = (
            pe.FILE_HEADER.Machine,
            pe.FILE_HEADER.TimeDateStamp,
            pe.OPTIONAL_HEADER.SizeOfImage,
        )
        report = {
            "image": str(image.resolve()),
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "fingerprint": fp,
        }
        if args.command == "candidate":
            data = default_profile().to_dict()
            data["id"] = "candidate-" + report["sha256"][:12]
            data["status"] = "candidate"
            data["fingerprint"] = dict(zip(("machine", "timestamp", "image_size"), fp))
            for module in data["modules"].values():
                module["enabled"] = False
            atomic_json(args.output, data)
            report["candidate"] = args.output
            report["warning"] = (
                "RVA/layout inherited as search hypotheses only; no semantic validation or write authorization"
            )
            report["code_checks"] = [
                {
                    "group": group,
                    "rva": row["rva"],
                    "matches": pe.get_data(row["rva"], len(bytes.fromhex(row["bytes"])))
                    == bytes.fromhex(row["bytes"]),
                }
                for group, rows in data["checks"].items()
                for row in rows
            ]
            atomic_json(str(args.output) + ".evidence.json", report)
        else:
            try:
                report["known_adapter"] = ProfileCatalog().select(fp).id
            except ValueError as exc:
                report["known_adapter"] = None
                report["reason"] = str(exc)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
