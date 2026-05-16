"""CondenseIt command-line interface."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from condenseit.config import get_config_path, load_config
from condenseit.ratings_import import import_ratings_path, import_ratings_url
from condenseit.read_import import import_read_url
from condenseit.services.digest_runner import execute_digest
from condenseit.services.post_run_format import format_post_run_lines
from condenseit.store.database import ContentStore

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@click.group()
@click.version_option()
def cli() -> None:
    """CondenseIt: AI-powered personal news digest."""


@cli.command()
@click.option("--dry-run", is_flag=True, help="Collect without LLM.")
@click.option("--no-deploy", is_flag=True, help="Skip VPS rsync.")
@click.option("--config", "-c", default=None, help="Path to config.yaml.")
@click.option("-v", "--verbose", is_flag=True)
def run(
    dry_run: bool,
    no_deploy: bool,
    config: str | None,
    verbose: bool,
) -> None:
    """Run the digest pipeline once."""
    _setup_logging(verbose)

    with console.status("[bold green]Running..."):
        result = execute_digest(
            config,
            dry_run=dry_run,
            skip_deploy=no_deploy,
        )
        stats = result["stats"]
        post = result.get("post")
        post_lines = format_post_run_lines(post if isinstance(post, dict) else None)
        console.print(
            Panel(
                "\n".join(post_lines),
                title="Post-run",
                style="cyan",
            ),
        )

    console.print(
        Panel(
            f"Digest complete.\n"
            f"Articles: {stats['articles_count']}\n"
            f"Videos: {stats.get('videos_count', 0)}\n"
            f"Time: {stats['processing_time']}\n"
            f"Model: {stats['model']}",
            title="CondenseIt",
            style="green",
        ),
    )


@cli.command()
@click.option("--port", default=8899, help="HTTP port.")
@click.option("--host", default="127.0.0.1", help="Bind host.")
@click.option("--config", "-c", default=None, help="Path to config.yaml.")
def serve(port: int, host: str, config: str | None) -> None:
    """Start web UI and admin panel."""
    import uvicorn

    from condenseit.web.app import create_app

    app = create_app(config)
    console.print(f"[bold]CondenseIt[/] http://{host}:{port}/")
    console.print(f"  Admin: http://{host}:{port}/admin/")
    uvicorn.run(app, host=host, port=port, log_level="info")


@cli.command("ratings-import")
@click.argument(
    "path",
    required=False,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--url",
    "import_url",
    default=None,
    help="HTTPS URL for a ratings JSON export (optional bearer via env).",
)
def ratings_import(path: Path | None, import_url: str | None) -> None:
    """Merge ratings from a JSON file and/or URL into the local SQLite store."""
    if path is None and not (import_url and import_url.strip()):
        raise click.UsageError("Provide a JSON file path and/or --url.")

    store = ContentStore()
    total = 0
    if path is not None:
        n = import_ratings_path(store, path)
        total += n
        console.print(f"Imported [bold]{n}[/] rating(s) from file.")
    if import_url and import_url.strip():
        token = os.environ.get("CONDENSEIT_RATINGS_IMPORT_BEARER_TOKEN", "")
        n = import_ratings_url(store, import_url.strip(), bearer_token=token)
        total += n
        console.print(f"Imported [bold]{n}[/] rating(s) from URL.")
    console.print(
        Panel(
            f"Total upserts this run: [bold]{total}[/]. "
            "Run ``condenseit run`` to apply preferences.",
            title="Ratings import",
            style="green",
        ),
    )


@cli.command("read-import")
@click.option(
    "--url",
    "import_url",
    required=True,
    help="HTTPS URL for a read-state JSON export (optional bearer via env).",
)
def read_import(import_url: str) -> None:
    """Merge read URLs from a JSON URL into the local SQLite store."""
    store = ContentStore()
    token = os.environ.get("CONDENSEIT_READ_IMPORT_BEARER_TOKEN", "")
    total = import_read_url(store, import_url.strip(), bearer_token=token)
    console.print(f"Imported [bold]{total}[/] read URL(s) from URL.")
    console.print(
        Panel(
            f"Total upserts this run: [bold]{total}[/]. "
            "Run ``condenseit run`` to filter already-read items.",
            title="Read import",
            style="green",
        ),
    )


@cli.command()
@click.option("--config", "-c", default=None)
def status(config: str | None) -> None:
    """Show config path and latest digest info."""
    cfg = load_config(config)
    store = ContentStore()
    latest = store.latest_digest()
    console.print(f"Config: {get_config_path(config)}")
    console.print(f"Model:  {store.get_setting('model', cfg.model)}")
    console.print(f"Provider: {store.get_setting('llm_provider', cfg.llm.provider)}")
    console.print(f"Ollama: {cfg.llm.ollama_host}")
    if latest:
        console.print(f"Latest digest id: {latest['id']} at {latest['created_at']}")
    else:
        console.print("No digests yet.")
