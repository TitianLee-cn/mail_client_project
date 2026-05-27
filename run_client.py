"""Entry point for the command line mail client."""

from mailapp.client.cli import run_cli


def main():
    """Start the interactive CLI."""
    run_cli()


if __name__ == "__main__":
    main()
