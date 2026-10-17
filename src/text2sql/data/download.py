"""Fetch benchmark data into `data/` from pinned URLs, verified against pinned SHA-256 checksums.

    uv run --frozen python -m text2sql.data.download bird

Idempotent: a file whose checksum already matches is not downloaded again, and a directory tree
whose extraction marker is present is not extracted again. Archives stay in data/bird/downloads/
so a deleted tree can be rebuilt offline. Sources and the reasons for choosing them are recorded
in docs/adr/003-bird-data.md.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import httpx
import typer

from text2sql.config import get_settings

_CHUNK = 1 << 20

type Log = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class Source:
    """One file to fetch; `dest` is relative to the data directory."""

    url: str
    sha256: str
    dest: str


@dataclass(frozen=True, slots=True)
class ArchiveTree:
    """The members of a zip archive under `prefix`, unpacked into `target` without the prefix.

    `inner_zip` names a zip stored inside `archive` that holds the tree (BIRD's dev.zip nests one).
    """

    archive: Source
    prefix: str
    target: str
    inner_zip: str | None = None


BIRD_FILES: tuple[Source, ...] = (
    Source(
        # The BIRD team's canonical Mini-Dev JSON (500 SQLite questions), pinned to a commit.
        url="https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/"
        "f65faf4ae3b638c1fa6df1d3370c8d92c8366301/data/mini_dev_sqlite-00000-of-00001.json",
        sha256="88ceb0710163cae46a256ecea8f0a8c98286599530b60587fda5c3cfe57d45d2",
        dest="bird/mini_dev_sqlite.json",
    ),
    Source(
        # Arcwise-Plat-SQL (Jin et al. 2026), pinned to a repository commit.
        url="https://raw.githubusercontent.com/uiuc-kang-lab/text_to_sql_benchmarks/"
        "fe766045c55b6875a43b30e9ac7683df5582f8cf/data/arcwise_plat_sql_only_with_diff.json",
        sha256="e7bf76408f99266506ea558d84982c69422e5db3dfecab5f08a3a8d3900e8395",
        dest="bird/arcwise_plat_sql.json",
    ),
    Source(
        # Filtered BIRD train questions and SQL (no databases), for few-shot retrieval.
        url="https://huggingface.co/datasets/birdsql/bird23-train-filtered/resolve/"
        "4068469807b255fcfc0816bdd520946fe460d256/data/train-00000-of-00001.jsonl",
        sha256="2ee64aa593e1adc59be7d5b9ce2395372a8ee27fdd94a3fb4d2fe09f3cd34bc8",
        dest="bird/train_filtered.jsonl",
    ),
)

BIRD_TREES: tuple[ArchiveTree, ...] = (
    ArchiveTree(
        # Mini-Dev package databases (byte-identical in the 2024-06 and 2025-07 packages).
        archive=Source(
            url="https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip",
            sha256="cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f",
            dest="bird/downloads/minidev.zip",
        ),
        prefix="minidev/MINIDEV/dev_databases/",
        target="bird/minidev_databases",
    ),
    ArchiveTree(
        # BIRD Dev databases (release dev_20240627), which Arcwise-Plat-SQL was checked against.
        archive=Source(
            url="https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip",
            sha256="cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630",
            dest="bird/downloads/dev.zip",
        ),
        inner_zip="dev_20240627/dev_databases.zip",
        prefix="dev_databases/",
        target="bird/dev_databases",
    ),
)


class ChecksumMismatchError(Exception):
    """A downloaded file does not match its pinned checksum."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(source: Source, data_dir: Path, log: Log) -> Path:
    """Download `source` unless a verified copy exists; verify before moving it into place."""
    dest = data_dir / source.dest
    if dest.is_file() and sha256_of(dest) == source.sha256:
        log(f"ok        {source.dest}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    log(f"download  {source.url}")
    digest = hashlib.sha256()
    with (
        httpx.stream("GET", source.url, follow_redirects=True, timeout=60.0) as response,
        part.open("wb") as fh,
    ):
        response.raise_for_status()
        for chunk in response.iter_bytes(_CHUNK):
            digest.update(chunk)
            fh.write(chunk)
    if digest.hexdigest() != source.sha256:
        part.unlink()
        raise ChecksumMismatchError(
            f"{source.url}: expected sha256 {source.sha256}, got {digest.hexdigest()}"
        )
    part.replace(dest)
    log(f"verified  {source.dest}")
    return dest


def _relative_member(name: str, prefix: str) -> PurePosixPath | None:
    """Path of a member below `prefix`, or None if it should be skipped; rejects zip slip."""
    if not name.startswith(prefix) or name.endswith("/"):
        return None
    relative = PurePosixPath(name[len(prefix) :])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe path in archive: {name}")
    if relative.name == ".DS_Store":
        return None
    return relative


def _unpack(archive: zipfile.ZipFile, prefix: str, target: Path) -> int:
    count = 0
    for info in archive.infolist():
        relative = _relative_member(info.filename, prefix)
        if relative is None:
            continue
        dest = target.joinpath(*relative.parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as src, dest.open("wb") as out:
            shutil.copyfileobj(src, out, _CHUNK)
        count += 1
    return count


def extract_tree(tree: ArchiveTree, data_dir: Path, log: Log) -> Path:
    """Unpack `tree` unless its marker shows it came from the pinned archive already."""
    target = data_dir / tree.target
    marker = target / f".extracted-{tree.archive.sha256[:16]}"
    if marker.is_file():
        log(f"ok        {tree.target}")
        return target
    archive_path = fetch(tree.archive, data_dir, log)
    if target.exists():
        shutil.rmtree(target)
    log(f"extract   {tree.target}")
    with zipfile.ZipFile(archive_path) as outer:
        if tree.inner_zip is None:
            count = _unpack(outer, tree.prefix, target)
        else:
            with tempfile.TemporaryDirectory(dir=archive_path.parent) as tmp:
                inner_path = Path(outer.extract(tree.inner_zip, tmp))
                with zipfile.ZipFile(inner_path) as inner:
                    count = _unpack(inner, tree.prefix, target)
    if count == 0:
        raise ValueError(f"{tree.archive.url} has no members under {tree.prefix}")
    marker.write_text(tree.archive.url + "\n", encoding="utf-8")
    return target


def download_bird(data_dir: Path, log: Log) -> None:
    for source in BIRD_FILES:
        fetch(source, data_dir, log)
    for tree in BIRD_TREES:
        extract_tree(tree, data_dir, log)


app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def main() -> None:
    """Download benchmark data with pinned checksums."""


@app.command()
def bird() -> None:
    """BIRD Mini-Dev questions and databases, BIRD Dev databases, Arcwise-Plat-SQL, train pairs."""
    download_bird(get_settings().data_dir, typer.echo)


if __name__ == "__main__":
    app()
