"""Build deterministic source and research-evidence release archives from Git."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

DEFAULT_VERSION = "v1.0.1"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def source_member(name):
    path = PurePosixPath(name)
    if name.startswith("results/"):
        return (len(path.parts) == 2 and name.startswith("results/step28-") and path.suffix in (".png", ".json", ".txt")) or name in {
            "results/step27-evaluation.json", "results/step27-evaluation.png",
            "results/step27-effects.png", "results/step27-mechanisms.png"}
    return (path.suffix in (".py", ".md", ".html", ".json", ".txt", ".png")
            or name in ("LICENSE", ".gitignore", ".gitattributes", ".python-version")
            or name.startswith(".github/workflows/") and path.suffix in (".yml", ".yaml")) and not any(
                p in (".git", ".venv", ".cache", "__pycache__", "exports", "dist") for p in path.parts)


def build_release(repo, output, version=DEFAULT_VERSION, ref="HEAD"):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Use a semantic release version such as v1.0.0.")
    commit = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
    names = git(repo, "ls-tree", "-r", "--name-only", "-z", commit).decode().split("\0")[:-1]
    if any(PurePosixPath(n).is_absolute() or ".." in PurePosixPath(n).parts for n in names):
        raise ValueError("Unsafe archive member path.")
    output.mkdir(parents=True, exist_ok=True)
    prefix = f"Artificial_Evolution-{version}"
    targets = {"source": output / f"{prefix}-source.zip", "research": output / f"{prefix}-research.zip"}
    if any(p.exists() for p in (*targets.values(), output / "SHA256SUMS.txt", output / "BUILD-INFO.json")):
        raise ValueError("Preserve existing release artifacts; use a new output directory.")
    counts = {}
    for kind, destination in targets.items():
        selected = ([n for n in names if source_member(n)] if kind == "source"
                    else [n for n in names if n == "LICENSE" or n.startswith("results/")])
        hashes = {}
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            def write(name, data):
                info = zipfile.ZipInfo(f"{prefix}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
            for name in selected:
                data = git(repo, "show", f"{commit}:{name}")
                hashes[name] = hashlib.sha256(data).hexdigest()
                write(name, data)
            write(f"release-{kind}-manifest.json", json.dumps({"version": version, "commit": commit, "kind": kind,
                  "files_sha256": hashes}, indent=2, sort_keys=True).encode() + b"\n")
        counts[kind] = len(selected)
    checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in targets.values()}
    (output / "SHA256SUMS.txt").write_text("".join(f"{digest}  {name}\n" for name, digest in checksums.items()))
    info = {"format_version": 1, "version": version, "commit": commit, "file_counts": counts,
            "archives_sha256": checksums, "inputs": "Committed Git blobs only; untracked files and working-tree changes are excluded.",
            "extraction": "Extract both archives into the same directory; their Artificial_Evolution-version prefixes and overlapping evidence files match."}
    (output / "BUILD-INFO.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args()
    try:
        print(json.dumps(build_release(args.repo, args.output, args.version, args.ref), indent=2))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
