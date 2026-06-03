"""Bootstrap CLI helpers (PRD §7.7.1).

Usage::

    python -m app.cli hash <password>   # → Argon2id hash for APP_PASSWORD_HASH
"""

from __future__ import annotations

import typer

from app.services.auth import hash_password

cli = typer.Typer(help="OCI Ampere A1 server admin CLI", add_completion=False)


@cli.callback()
def _main() -> None:
    """Admin CLI. Keeps `hash` a named subcommand (not collapsed)."""


@cli.command(name="hash")
def hash_cmd(
    password: str = typer.Argument(..., help="Plaintext password to hash"),
) -> None:
    """Print an Argon2id hash to paste into APP_PASSWORD_HASH."""
    typer.echo(hash_password(password))


if __name__ == "__main__":
    cli()
