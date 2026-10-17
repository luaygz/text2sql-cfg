"""`text2sql cache`: move response-cache rows between the local SQLite store and the committed
shards under `cache/llm/shards/` (see `text2sql.llm.shards`)."""

from __future__ import annotations

import typer

from text2sql.config import get_settings
from text2sql.llm.cache import ResponseCache
from text2sql.llm.shards import CACHE_FILENAME, export_shards, import_shards, shard_dir

app = typer.Typer(no_args_is_help=True)


@app.command("export")
def export_command() -> None:
    """Write every cached row that no shard holds yet into a new shard; commit the new file."""
    settings = get_settings()
    cache = ResponseCache(settings.cache_dir / CACHE_FILENAME)
    try:
        written = export_shards(cache, shard_dir(settings.cache_dir))
    finally:
        cache.close()
    if not written:
        typer.echo("Nothing to export: every cached row is already in a shard.")
    for shard in written:
        typer.echo(f"{shard.path}: {shard.rows} rows, {shard.size_bytes / 1e6:.1f} MB")


@app.command("import")
def import_command() -> None:
    """Load every shard the local store has not seen (clients also do this when they start)."""
    settings = get_settings()
    cache = ResponseCache(settings.cache_dir / CACHE_FILENAME)
    try:
        imported = import_shards(cache, shard_dir(settings.cache_dir))
    finally:
        cache.close()
    if not imported:
        typer.echo("Up to date: every shard is already in the local store.")
    for shard in imported:
        typer.echo(f"{shard.name}: {shard.rows} rows, {shard.new_rows} new")
