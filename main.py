"""Entrypoint del proyecto -- Migración Histórica a Enablon.

Uso:
    python main.py export drills --mode sample --limit 100
    python main.py export drills --mode full --confirm-full-export
"""
from src.cli import cli

if __name__ == "__main__":
    cli()
