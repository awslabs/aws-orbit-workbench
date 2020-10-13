#!/usr/bin/env python

# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
Sample script showing how to do local port forwarding over paramiko.

This script connects to the requested SSH server and sets up local port
forwarding (the openssh -L option) from a local port through a tunneled
connection to a destination reachable from the SSH server machine.
"""
from typing import Callable, Any, Dict, Iterator, List, Optional, Tuple, Union, NewType
import getpass
import os
import socket
import select
import logging
import sys
import paramiko
try:
    import SocketServer
except ImportError:
    import socketserver as SocketServer
import threading

SSH_PORT = 22
DEFAULT_PORT = 4000

g_verbose = True

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()
logging.getLogger("paramiko").setLevel(logging.WARNING)


class ForwardServer(SocketServer.ThreadingTCPServer):

    """
    Attributes
    ----------
    daemon_threads: bool
    allow_reuse_address: bool


    Functions
    ----------
    def forward_server(
            local_port: Any,
            remote_host: Any,
            remote_port: Any,
            transport: Any
    ) -> ForwardServer:

    def start_forward(server: {serve_forever}) -> None:

    def verbose(s) -> None:
    def getFreeLocalPort() -> Any:
    def forward(server: Any, remote: Any, key_file: Any) -> Tuple[ForwardServer, Any]:
    """
    daemon_threads = True
    allow_reuse_address = True


class Handler(SocketServer.BaseRequestHandler):
    """
   Handles Socket

   Functions
   --------
   def handle(self) -> None:
    Tries to connect request
    """
    def handle(self) -> None:
        try:
            chan = self.ssh_transport.open_channel(
                "direct-tcpip",
                (self.chain_host, self.chain_port),
                self.request.getpeername(),
            )
        except Exception as e:
            verbose(
                "Incoming request to %s:%d failed: %s"
                % (self.chain_host, self.chain_port, repr(e))
            )
            return
        if chan is None:
            verbose(
                "Incoming request to %s:%d was rejected by the SSH server."
                % (self.chain_host, self.chain_port)
            )
            return

        verbose(
            "Connected!  Tunnel open %r -> %r -> %r"
            % (
                self.request.getpeername(),
                chan.getpeername(),
                (self.chain_host, self.chain_port),
            )
        )
        while True:
            r, w, x = select.select([self.request, chan], [], [])
            if self.request in r:
                data = self.request.recv(1024)
                if len(data) == 0:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                self.request.send(data)

        peername = self.request.getpeername()
        chan.close()
        self.request.close()
        verbose("Tunnel closed from %r" % (peername,))


def forward_server(
        local_port: Any,
        remote_host: Any,
        remote_port: Any,
        transport: Any
) -> ForwardServer:
    """
    Parameters
    ----------
    local_port: Any
    remote_host: Any
    remote_port: Any
    transport: Any

    Returns
    -------
    Forward server.
    """
    # this is a little convoluted, but lets me configure things for the Handler
    # object.  (SocketServer doesn't give Handlers any way to access the outer
    # server normally.)
    class SubHander(Handler):
        chain_host = remote_host
        chain_port = remote_port
        ssh_transport = transport

    server = ForwardServer(("", local_port), SubHander)
    return server


def start_forward(server: Any) -> None:
    """
    Start server
    Parameters
    ---------
   server: Any

    returns
    -------
    None
    """
    server.serve_forever()


def verbose(s) -> None:
    """
    Parameters
    ---------
    s: Any
    returns
    """
    if g_verbose:
        logger.debug(s)


def getFreeLocalPort() -> Any:
    """
    Gets Local Port
    returns
    ------
    local port
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    addr = s.getsockname()
    local_port = addr[1]
    s.close()
    return local_port


def forward(server: Any, remote: Any, key_file: Any) -> Tuple[ForwardServer, Any]:
    """
    Returns server and local port
    Parameters
    ----------

   server: Any
   remote: Any
   key_file: Any
    returns
    -------
    Forward Server.

    Examples
    --------
    """
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    logger.debug("Connecting using %s to ssh host %s:%s",key_file, server, '22')
    try:
        client.connect(
            server,
            '22',
            username='glue',
            key_filename=key_file
        )
    except Exception as e:
        raise Exception("*** Failed to connect to %s:%s: %r" % (server, '22', e))

    livy_port = 8998
    local_port = getFreeLocalPort()
    logger.debug( "Now forwarding port %s to %s:%s ...",local_port, remote, livy_port)

    server = forward_server(local_port, remote, livy_port, client.get_transport())

    fwd_thread = threading.Thread(target=start_forward,daemon=True, args=(server,))
    fwd_thread.start()

    return (server,local_port)
