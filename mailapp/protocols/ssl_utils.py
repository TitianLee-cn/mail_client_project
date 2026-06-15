"""SSL/TLS context helpers shared by SMTP and POP3."""

import ssl
from pathlib import Path


def create_server_ssl_context(certfile, keyfile, cafile=None):
    """Create a server-side SSL context."""
    certfile = Path(certfile)
    keyfile = Path(keyfile)
    if not certfile.is_file() or not keyfile.is_file():
        raise FileNotFoundError(
            f"TLS certificate/key missing: cert={certfile}, key={keyfile}. "
            "Run scripts/generate_dev_cert.sh."
        )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    if cafile:
        context.load_verify_locations(cafile=cafile)
    return context


def create_client_ssl_context(cafile=None, verify=True):
    """Create a client-side SSL context."""
    if verify:
        context = ssl.create_default_context(cafile=cafile)
    else:
        context = ssl._create_unverified_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def wrap_socket_with_ssl(sock, context, server_side=False):
    """Wrap a socket with SSL."""
    return context.wrap_socket(sock, server_side=server_side)
