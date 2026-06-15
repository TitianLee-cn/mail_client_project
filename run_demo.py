"""One-command launcher for the course desktop demonstration."""

from mailapp.client.gui import run_gui
from mailapp.server.server_app import (
    init_services,
    start_all_services,
    stop_all_services,
)


def main():
    config = init_services()
    services = start_all_services()
    print(
        f"Demo services started: SMTP {config['smtp_host']}:{config['smtp_port']}, "
        f"POP3 {config['pop3_host']}:{config['pop3_port']}"
    )
    try:
        run_gui()
    except KeyboardInterrupt:
        print("\nStopping desktop demo.")
    finally:
        stop_all_services(services)


if __name__ == "__main__":
    main()
