"""SSL/TLS helper functions reserved for secure transport demos."""

import ssl


def create_server_ssl_context(certfile, keyfile):
    """Create a server-side SSL context."""
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context


def create_client_ssl_context(cafile=None):
    """Create a client-side SSL context."""
    return ssl.create_default_context(cafile=cafile)


def wrap_socket_with_ssl(sock, context, server_side=False):
    """Wrap a socket with SSL."""
    return context.wrap_socket(sock, server_side=server_side)
