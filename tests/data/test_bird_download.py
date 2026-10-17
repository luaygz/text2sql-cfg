from __future__ import annotations

import hashlib
import io
import zipfile
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import httpx
import pytest

from text2sql.data import download
from text2sql.data.download import ArchiveTree, ChecksumMismatchError, Source, extract_tree, fetch


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _quiet(_: str) -> None:
    return None


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    """URL -> body served by a fake HTTP layer; unknown URLs get 404, nothing hits the network."""
    bodies: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = bodies.get(str(request.url))
        return httpx.Response(200, content=body) if body is not None else httpx.Response(404)

    def fake_stream(method: str, url: str, **_: Any) -> AbstractContextManager[httpx.Response]:
        client = httpx.Client(transport=httpx.MockTransport(handler))
        return client.stream(method, url)

    monkeypatch.setattr(download.httpx, "stream", fake_stream)
    return bodies


class TestFetch:
    def test_downloads_and_verifies(self, tmp_path: Path, served: dict[str, bytes]) -> None:
        served["https://x.test/a.json"] = b"[1, 2]"
        source = Source("https://x.test/a.json", _sha(b"[1, 2]"), "bird/a.json")
        assert fetch(source, tmp_path, _quiet).read_bytes() == b"[1, 2]"

    def test_checksum_mismatch_leaves_no_file(
        self, tmp_path: Path, served: dict[str, bytes]
    ) -> None:
        served["https://x.test/a.json"] = b"tampered"
        source = Source("https://x.test/a.json", _sha(b"original"), "bird/a.json")
        with pytest.raises(ChecksumMismatchError):
            fetch(source, tmp_path, _quiet)
        assert list((tmp_path / "bird").iterdir()) == []

    def test_verified_copy_is_not_downloaded_again(
        self, tmp_path: Path, served: dict[str, bytes]
    ) -> None:
        (tmp_path / "bird").mkdir()
        (tmp_path / "bird" / "a.json").write_bytes(b"cached")
        source = Source("https://x.test/a.json", _sha(b"cached"), "bird/a.json")
        # The fake server would answer 404, so success means no request was made.
        assert fetch(source, tmp_path, _quiet).read_bytes() == b"cached"

    def test_corrupt_local_copy_is_replaced(self, tmp_path: Path, served: dict[str, bytes]) -> None:
        (tmp_path / "bird").mkdir()
        (tmp_path / "bird" / "a.json").write_bytes(b"truncat")
        served["https://x.test/a.json"] = b"truncated"
        source = Source("https://x.test/a.json", _sha(b"truncated"), "bird/a.json")
        assert fetch(source, tmp_path, _quiet).read_bytes() == b"truncated"

    def test_http_error_raises(self, tmp_path: Path, served: dict[str, bytes]) -> None:
        source = Source("https://x.test/missing", _sha(b""), "bird/missing")
        with pytest.raises(httpx.HTTPStatusError):
            fetch(source, tmp_path, _quiet)


@pytest.fixture
def package(served: dict[str, bytes]) -> ArchiveTree:
    body = _zip_bytes(
        {
            "pkg/dbs/shop/shop.sqlite": b"db",
            "pkg/dbs/shop/database_description/item.csv": b"csv",
            "pkg/dbs/.DS_Store": b"junk",
            "pkg/other/huge.sql": b"skip me",
            "__MACOSX/pkg/dbs/._shop": b"junk",
        }
    )
    served["https://x.test/pkg.zip"] = body
    return ArchiveTree(
        archive=Source("https://x.test/pkg.zip", _sha(body), "bird/downloads/pkg.zip"),
        prefix="pkg/dbs/",
        target="bird/dbs",
    )


class TestExtractTree:
    def test_extracts_only_the_prefix_tree(self, tmp_path: Path, package: ArchiveTree) -> None:
        target = extract_tree(package, tmp_path, _quiet)
        files = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
        assert [f for f in files if not f.startswith(".extracted-")] == [
            "shop/database_description/item.csv",
            "shop/shop.sqlite",
        ]

    def test_second_run_is_a_no_op(
        self, tmp_path: Path, package: ArchiveTree, served: dict[str, bytes]
    ) -> None:
        target = extract_tree(package, tmp_path, _quiet)
        (target / "shop" / "shop.sqlite").write_bytes(b"locally modified")
        served.clear()
        extract_tree(package, tmp_path, _quiet)
        assert (target / "shop" / "shop.sqlite").read_bytes() == b"locally modified"

    def test_nested_zip(self, tmp_path: Path, served: dict[str, bytes]) -> None:
        inner = _zip_bytes({"dev_databases/shop/shop.sqlite": b"db"})
        outer = _zip_bytes({"release/dev_databases.zip": inner})
        served["https://x.test/dev.zip"] = outer
        tree = ArchiveTree(
            archive=Source("https://x.test/dev.zip", _sha(outer), "bird/downloads/dev.zip"),
            inner_zip="release/dev_databases.zip",
            prefix="dev_databases/",
            target="bird/dev_databases",
        )
        target = extract_tree(tree, tmp_path, _quiet)
        assert (target / "shop" / "shop.sqlite").read_bytes() == b"db"

    def test_rejects_paths_escaping_the_target(
        self, tmp_path: Path, served: dict[str, bytes]
    ) -> None:
        body = _zip_bytes({"pkg/dbs/../../evil.txt": b"x"})
        served["https://x.test/evil.zip"] = body
        tree = ArchiveTree(
            archive=Source("https://x.test/evil.zip", _sha(body), "bird/downloads/evil.zip"),
            prefix="pkg/dbs/",
            target="bird/dbs",
        )
        with pytest.raises(ValueError, match="unsafe path"):
            extract_tree(tree, tmp_path, _quiet)
        assert not (tmp_path / "evil.txt").exists()

    def test_wrong_prefix_fails_loudly(self, tmp_path: Path, package: ArchiveTree) -> None:
        wrong = ArchiveTree(archive=package.archive, prefix="nope/", target="bird/dbs")
        with pytest.raises(ValueError, match="no members"):
            extract_tree(wrong, tmp_path, _quiet)
