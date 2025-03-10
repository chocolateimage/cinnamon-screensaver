#!/usr/bin/python3

import gi
gi.require_version('CScreensaver', '1.0')

from gi.repository import GLib, CScreensaver, Gio
import os
import sys
import signal
import argparse
import gettext
import shlex
from enum import IntEnum
from subprocess import Popen, DEVNULL

import config
from util import settings
import constants as c

signal.signal(signal.SIGINT, signal.SIG_DFL)
gettext.install("cinnamon-screensaver", "/usr/share/locale")

class Action(IntEnum):
    EXIT = 1
    QUERY = 2
    TIME = 3
    LOCK = 4
    ACTIVATE = 5
    DEACTIVATE = 6
    VERSION = 7

class ScreensaverCommand:
    """
    This is a standalone executable that provides a simple way
    of controlling the screensaver via its dbus interface.
    """
    def __init__(self, mainloop):
        self.mainloop = mainloop
        self.proxy = None

        parser = argparse.ArgumentParser(description='Cinnamon Screensaver Command')
        parser.add_argument('--exit', '-e', dest="action_id", action='store_const', const=Action.EXIT,
                            help=_('Causes the screensaver to exit gracefully'))
        parser.add_argument('--query', '-q', dest="action_id", action='store_const', const=Action.QUERY,
                            help=_('Query the state of the screensaver'))
        parser.add_argument('--time', '-t', dest="action_id", action='store_const', const=Action.TIME,
                            help=_('Query the length of time the screensaver has been active'))
        parser.add_argument('--lock', '-l', dest="action_id", action='store_const', const=Action.LOCK,
                            help=_('Tells the running screensaver process to lock the screen immediately'))
        parser.add_argument('--activate', '-a', dest="action_id", action='store_const', const=Action.ACTIVATE,
                            help=_('Turn the screensaver on (blank the screen)'))
        parser.add_argument('--deactivate', '-d', dest="action_id", action='store_const', const=Action.DEACTIVATE,
                            help=_('If the screensaver is active then deactivate it (un-blank the screen)'))
        parser.add_argument('--version', '-V', dest="action_id", action='store_const', const=Action.VERSION,
                            help=_('Version of this application'))
        parser.add_argument('--away-message', '-m', dest="message", action='store', default="",
                            help=_('Message to be displayed in lock screen'))
        args = parser.parse_args()

        if not args.action_id:
            parser.print_help()
            quit()

        if args.action_id == Action.VERSION:
            print("cinnamon-screensaver %s" % config.VERSION)
            quit()

        self.action_id = args.action_id
        self.message = args.message

        custom_saver = settings.get_custom_screensaver()
        if custom_saver != '':
            self.handle_custom_saver(custom_saver)
            quit()

        CScreensaver.ScreenSaverProxy.new_for_bus(Gio.BusType.SESSION,
                                                  Gio.DBusProxyFlags.NONE,
                                                  c.SS_SERVICE,
                                                  c.SS_PATH,
                                                  None,
                                                  self._on_proxy_ready)

    def handle_custom_saver(self, custom_saver):
        if self.action_id in [Action.LOCK, Action.ACTIVATE]:
            try:
                Popen(shlex.split(custom_saver), stdin=DEVNULL)
            except OSError as e:
                print("Error %d running %s: %s" % (e.errno, custom_saver,
                                                   e.strerror))
        else:
            print("Action not supported with custom screensaver.")

    def _on_proxy_ready(self, object, result, data=None):
        try:
            self.proxy = CScreensaver.ScreenSaverProxy.new_for_bus_finish(result)
            self.perform_action()
        except GLib.Error as e:
            print("Can't connect to screensaver: %d - %s" % (e.code, e.message))
            self.mainloop.quit()

    def perform_action(self):
        if self.action_id == Action.EXIT:
            self.proxy.call_quit_sync()
        elif self.action_id == Action.QUERY:
            if self.proxy.call_get_active_sync():
                print(_("The screensaver is active\n"))
            else:
                print(_("The screensaver is inactive\n"))
        elif self.action_id == Action.TIME:
            time = self.proxy.call_get_active_time_sync()
            if time == 0:
                print(_("The screensaver is not currently active.\n"))
            else:
                print(gettext.ngettext ("The screensaver has been active for %d second.\n", "The screensaver has been active for %d seconds.\n", time) % time)
        elif self.action_id == Action.LOCK:
            self.proxy.call_lock_sync(self.message)
        elif self.action_id == Action.ACTIVATE:
            self.proxy.call_set_active_sync(True)
        elif self.action_id == Action.DEACTIVATE:
            self.proxy.call_set_active_sync(False)

        self.mainloop.quit()

if __name__ == "__main__":
    try:
        if os.environ["WAYLAND_DISPLAY"]:
            print("Cinnamon Screensaver is unavailable on Wayland.")
            sys.exit(0)
    except KeyError:
        pass

    ml = GLib.MainLoop.new(None, True)
    main = ScreensaverCommand(ml)

    ml.run()
