"""Entry point for starting the mail demo servers."""

from mailapp.server.server_app import start_server


def main():
    """Start SMTP and POP3 services until Ctrl+C."""
    start_server()


if __name__ == "__main__":
    main()
