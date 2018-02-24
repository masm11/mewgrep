#!/usr/bin/env python

import os
import sys
import pyinotify
import re

os.umask(0o077)

maildir = f'{os.environ["HOME"]}/Mail'
i = 1
while i < len(sys.argv):
    if sys.argv[i] == '-r':
        maildir = sys.argv[i + 1]
        i += 2
    else:
        raise RuntimeError('bad arg.')

wm = pyinotify.WatchManager()
mask = 0
mask |= pyinotify.IN_CREATE
mask |= pyinotify.IN_DELETE
mask |= pyinotify.IN_MOVED_FROM
mask |= pyinotify.IN_MOVED_TO
mask |= pyinotify.IN_CLOSE_WRITE

MAIL_FILE_REGEX = re.compile(r'^.*/\d+$')

class EventHandler(pyinotify.ProcessEvent):
    def __init__(self):
        self.__f = open(f'{maildir}/.mewgrep-changelog.txt', 'a')
        self.__changelog_path = f'{maildir}/.mewgrep-changelog.txt'
    
    def __record_changelog(self, mark, path):
        path = path[len(maildir)+1:]		# +1 for '/'.
        if re.match(MAIL_FILE_REGEX, path):
            self.__f.write(f'{mark}\t{path}\n')
            self.__f.flush()
    def __reopen_changelog(self):
        self.__f.close()
        self.__f = open(self.__changelog_path, 'a')
    
    def process_IN_CREATE(self, event):
        if event.dir:
            wm.add_watch(event.pathname, mask, rec=True)
    def process_IN_DELETE(self, event):
        if not event.dir:
            self.__record_changelog('D', event.pathname)
            if event.pathname == self.__changelog_path:
                self.__reopen_changelog()
    def process_IN_MOVED_FROM(self, event):
        if not event.dir:
            self.__record_changelog('D', event.pathname)
            if event.pathname == self.__changelog_path:
                self.__reopen_changelog()
    def process_IN_MOVED_TO(self, event):
        if not event.dir:
            self.__record_changelog('C', event.pathname)
    def process_IN_CLOSE_WRITE(self, event):
        if not event.dir:
            self.__record_changelog('C', event.pathname)

# hardlink したファイルの編集は非対応。

handler = EventHandler()
notifier = pyinotify.Notifier(wm, handler)
wm.add_watch(maildir, mask, rec=True)
notifier.loop()
