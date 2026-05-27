"""Initialize and run SMTP/POP3 services together."""

import time

from mailapp.auth.user_store import ensure_default_users
from mailapp.common.logger import get_logger
from mailapp.config import get_config, load_config
from mailapp.protocols.pop3_server import start_pop3_server, stop_pop3_server
from mailapp.protocols.smtp_server import start_smtp_server, stop_smtp_server
from mailapp.storage.db import init_database

logger = get_logger(__name__)


def init_services():
    """Load config, initialize database, and create default users."""
    config = load_config()
    init_database()
    ensure_default_users(config.get("default_users", []))
    return config


def start_all_services():
    """Start SMTP and POP3 services."""
    config = get_config()
    smtp = start_smtp_server(config["smtp_host"], config["smtp_port"])
    pop3 = start_pop3_server(config["pop3_host"], config["pop3_port"])
    return {"smtp": smtp, "pop3": pop3}


def stop_all_services(services):
    """Stop all started services."""
    stop_smtp_server(services.get("smtp"))
    stop_pop3_server(services.get("pop3"))


def start_server():
    """Start full server and block until Ctrl+C."""
    config = init_services()
    services = start_all_services()
    print(f"SMTP server: {config['smtp_host']}:{config['smtp_port']}")
    print(f"POP3 server: {config['pop3_host']}:{config['pop3_port']}")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping services")
    finally:
        stop_all_services(services)
