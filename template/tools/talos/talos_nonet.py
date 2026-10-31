"""pytest plugin: nothing in a baseline run may reach the network.

A test suite the company has never read can talk to real servers. One adopted repo's default run targeted its production host and
would have created accounts there. So the baseline refuses every connection, including localhost (it could be a real local database),
and writes down what was tried. A test that needed the network fails, and that failure is recorded as known. Python only: a subprocess
the suite starts is not covered, which is why the environment is also stripped of credentials.
"""
import os
import socket

LOG = os.environ.get("TALOS_NONET_LOG")


class Blocked(ConnectionRefusedError):
    pass


def _note(target) -> None:
    if LOG:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{target}\n")


_connect = socket.socket.connect


def connect(self, address):
    if self.family == getattr(socket, "AF_UNIX", object()):
        return _connect(self, address)
    _note(address[0] if isinstance(address, tuple) else address)
    raise Blocked("talos baseline: the network is blocked")


def connect_ex(self, address):
    _note(address[0] if isinstance(address, tuple) else address)
    return 111


def getaddrinfo(host, *args, **kwargs):
    _note(host)
    raise socket.gaierror("talos baseline: the network is blocked")


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.getaddrinfo = getaddrinfo
