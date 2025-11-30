#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
pywebview is a lightweight cross-platform wrapper around a webview component that allows to display HTML content in its
own dedicated window. Works on Windows, OS X and Linux and compatible with Python 2 and 3.

(C) 2014-2019 Roman Sirokov and contributors
Licensed under BSD license

http://github.com/r0x0r/pywebview/
"""


import logging
import sys
import os
import re
import threading
from uuid import uuid4
from proxy_tools import module_property

from webview import create_window
from webview.event import Event
from webview.guilib import initialize
from webview.util import _token, base_uri, parse_file_type, escape_string, make_unicode, escape_line_breaks, WebViewException
from webview.window import Window
from webview.localization import original_localization
from webview.wsgi import Routing, StaticFiles, StaticResources


__all__ = (
    # Stuff that's here
    'start', 'create_window', 'token', 'screens'
    # From wsgi
    'Routing', 'StaticFiles', 'StaticResources',
    # From event
    'Event',
    # from util
    '_token', 'base_uri', 'parse_file_type', 'escape_string', 'make_unicode',
    'escape_line_breaks', 'WebViewException',
    # from window
    'Window',
)

logger = logging.getLogger('pywebview')
handler = logging.StreamHandler()
formatter = logging.Formatter('[pywebview] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

log_level = logging.DEBUG if os.environ.get('PYWEBVIEW_LOG') == 'debug' else logging.INFO
logger.setLevel(log_level)

OPEN_DIALOG = 10
FOLDER_DIALOG = 20
SAVE_DIALOG = 30

DRAG_REGION_SELECTOR = '.pywebview-drag-region'

guilib = None
_debug = {
  'mode': False
}
_user_agent = None
_multiprocessing = False
_http_server = False

token = _token
windows = []

def start(func=None, args=None, localization={}, gui=None, debug=False, http_server=False, user_agent=None):
    """
    Start a GUI loop and display previously created windows. This function must
    be called from a main thread.

    :param func: Function to invoke upon starting the GUI loop.
    :param args: Function arguments. Can be either a single value or a tuple of
        values.
    :param localization: A dictionary with localized strings. Default strings
        and their keys are defined in localization.py.
    :param gui: Force a specific GUI. Allowed values are ``cef``, ``qt``, or
        ``gtk`` depending on a platform.
    :param debug: Enable debug mode. Default is False.
    :param http_server: Enable built-in HTTP server. If enabled, local files
        will be served using a local HTTP server on a random port. For each
        window, a separate HTTP server is spawned. This option is ignored for
        non-local URLs.
    :param user_agent: Change user agent string. Not supported in EdgeHTML.
    """
    global guilib, _debug, _multiprocessing, _http_server, _user_agent
    from webview import windows

    def _create_children(other_windows):
        if not windows[0].shown.wait(10):
            raise WebViewException('Main window failed to load')

        for window in other_windows:
            guilib.create_window(window)

    _debug['mode'] = debug

    if debug:
        logger.setLevel(logging.DEBUG)

    _user_agent = user_agent
    #_multiprocessing = multiprocessing
    multiprocessing = False # TODO
    _http_server = http_server

    if multiprocessing:
        from multiprocessing import Process as Thread
    else:
        from threading import Thread

    original_localization.update(localization)

    if threading.current_thread().name != 'MainThread':
        raise WebViewException('This function must be run from a main thread.')

    if len(windows) == 0:
        raise WebViewException('You must create a window first before calling this function.')

    guilib = initialize(gui)

    #for window in windows:
    windows[-1]._initialize(guilib, multiprocessing, http_server)

    #if len(windows) > 1:
    #    t = Thread(target=_create_children, args=(windows[1:],))
    #    t.start()

    if func:
        if args is not None:
            if not hasattr(args, '__iter__'):
                args = (args,)
            t = Thread(target=func, args=args)
        else:
            t = Thread(target=func)
        t.start()

    Thread(target=lambda:guilib.create_window(windows[-1])).start()


@module_property
def screens():
    guilib = initialize()
    screens = guilib.get_screens()
    return screens
