# -*- coding: utf-8 -
#
# This file is part of flower. See the NOTICE for more information.

import sys
import threading

_tls = threading.local()

import pyuv

from flower.core.channel import channel
from flower.core.sched import tasklet, getcurrent, schedule

def get_fd(io):
    if not isinstance(io, int):
        if hasattr(io, 'fileno'):
            if callable(io.fileno):
                fd = io.fileno()
            else:
                fd = io.fileno
        else:
            raise ValueError("invalid file descriptor number")
    else:
        fd = io
    return fd


def uv_mode(m):
    if m == 0:
        return pyuv.UV_READABLE
    elif m == 1:
        return pyuv.UV_WRITABLE
    else:
        return pyuv.UV_READABLE | pyuv.UV_WRITABLE

class UVExit(Exception):
    pass


class UV(object):

    def __init__(self):
        self.loop = pyuv.Loop()
        self._async = pyuv.Async(self.loop, self._wakeloop)
        self._async.unref()
        self.fds = {}
        self._lock = threading.RLock()
        self.running = False

        # start the server task
        self._runtask = tasklet(self.run, "uv_server")()

    def _wakeloop(self, handle):
        self.loop.update_time()

    def wakeup(self):
        self._async.send()

    def switch(self):
        if not self.running:
            self._runtask = tasklet(self.run)()

        getcurrent().remove()
        self._runtask.switch()

    def idle(self, handle):
        if getcurrent() is self._runtask:
            schedule()

    def run(self):
        t = pyuv.Timer(self.loop)
        t.start(self.idle, 0.0001, 0.0001)
        t.unref()
        self.running = True
        try:
            self.loop.run()
        finally:
            self.running = False

def uv_server():
    global _tls

    try:
        return _tls.uv_server
    except AttributeError:
        uv_server = _tls.uv_server = UV()
        return uv_server

def uv_sleep(seconds, ref=True):
    """ use the event loop for sleep. This an alternative to our own
    time events scheduler """

    uv = uv_server()
    c = channel()
    def _sleep_cb(handle):
        handle.stop()
        c.send(None)

    sleep = pyuv.Timer(uv.loop)
    sleep.start(_sleep_cb, seconds, seconds)
    if not ref:
        sleep.unref()

    c.receive()

def uv_idle(ref=True):
    """ use the event loop for idling. This an alternative to our own
    time events scheduler """

    uv = uv_server()
    c = channel()
    def _sleep_cb(handle):
        handle.stop()
        c.send(True)


    idle = pyuv.Idle(uv.loop)
    idle.start(_sleep_cb)
    if not ref:
        idle.unref()

    return c.receive()
