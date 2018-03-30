#!/usr/bin/env python

import sys
import os
import os.path
import time
import re
import subprocess
import concurrent.futures.process
import multiprocessing
import traceback
import datetime

from voca import Voca
from corpus import Corpus
from mailparser import MailParser
from tokenizer import Tokenizer

os.umask(0o077)

def print_progress(label):
    print(datetime.datetime.now())
    print(label)
    print(subprocess.run(['bash', '-c', 'ps auxww | grep make-index']))

class FileLister:
    def __init__(self, maildir):
        self.__maildir = maildir
        self.__folders = set()

    def add_folder(self, folder):
        self.__folders.add(folder)

    def listup(self):
        paths = set()
        if len(self.__folders) != 0:
            for folder in self.__folders:
                self.__listup_recursive(paths, f'{self.__maildir}/{folder}')
        else:
            names = os.listdir(self.__maildir)
            for name in names:
                if name not in {'trash', 'spam'}:
                    p = f'{self.__maildir}/{name}'
                    if os.path.isdir(p):
                        self.__listup_recursive(paths, p)
        prefixlen = len(self.__maildir) + 1
        return { path[prefixlen:] for path in paths }

    def __listup_recursive(self, paths, path):
        names = os.listdir(path)
        for name in names:
            p = f'{path}/{name}'
            if os.path.isdir(p):
                self.__listup_recursive(paths, p)
            elif re.match(MAIL_FILE_REGEX, name):
                paths.add(p)

class Mail:
    def __init__(self, path):
        self.path = path
        self.Subject = []
        self.From = []
        self.To = []
        self.Cc = []
        self.Bcc = []
        self.Reply_to = []
        self.Date = []
        self.texts = []
        # self.body_words = None
        self.body_word_indices = set()

tokenizer = Tokenizer()
def get_words_from_mail(maildir, mail):
    # clear corpus (and voca), because such a big data is not needed in forked processes.
    corpus.clear()
    
    # with open('/dev/tty', 'w') as f:
    #     print(f'>>> {mail.path}', file=f)
    mail_parser = MailParser(maildir, mail)
    mail_parser.read_binary()
    mail_parser.parse()
    words = set()
    for txt in mail.texts:
        if txt:
            words |= tokenizer.get_words(txt)
    return words

if __name__ == '__main__':
    updating_index = True
    if len(sys.argv) >= 2:
        if sys.argv[1] == '--init':
            updating_index = False

    maildir = f'{os.environ["HOME"]}/Mail'
    indexdir = '/opt/mewgrep'
    FILENAME_VOCA = f'{indexdir}/.mewgrep-voca.txt'
    FILENAME_PATHS = f'{indexdir}/.mewgrep-paths.bin'
    FILENAME_INDEX = f'{indexdir}/.mewgrep-index.bin'
    FILENAME_MATRIX = f'{indexdir}/.mewgrep-matrix.bin'
    FILENAME_CHGLOG = f'{indexdir}/.mewgrep-changelog.txt'

    MAX_WORKERS = 4

    MAIL_FILE_REGEX = r'^\d+$'

    voca = Voca()
    corpus = Corpus(voca)

    if not updating_index:
        print_progress('listing.')
        file_lister = FileLister(maildir)
        # file_lister.add_folder('inbox')
        removed = set()
        created = file_lister.listup()

    else:
        print_progress('loading.')
        voca.load(FILENAME_VOCA)
        corpus.load(FILENAME_PATHS, FILENAME_INDEX, FILENAME_MATRIX)

        removed = set()
        created = set()

        with open(FILENAME_CHGLOG) as f:
            try:
                os.remove(f'{FILENAME_CHGLOG}.old')
                pass
            except FileNotFoundError:
                pass
            os.rename(f'{FILENAME_CHGLOG}', f'{FILENAME_CHGLOG}.old')

            # wait for mewgrepd to reopen changelog.
            for i in range(5):
                if os.path.exists(FILENAME_CHGLOG):
                    break
                time.sleep(1)

            for line in f:
                evtype, path = line.split()
                if evtype == 'C':
                    created.add(path)
                elif evtype == 'D':
                    removed.add(path)

    print_progress('processing removed files.')
    for path in removed:
        corpus.remove(path)

    print('pid=', os.getpid())
    # multiprocessing.set_start_method('forkserver')

    print_progress('parsing files.')
    mails = [ Mail(path) for path in created ]
    nr_total = len(mails)
    nr_done = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_mail = { executor.submit(get_words_from_mail, maildir, mail): mail for mail in mails }
        for future in concurrent.futures.as_completed(future_to_mail):
            mail = future_to_mail[future]
            try:
                corpus.add(mail.path, future.result())
                nr_done += 1
            except Exception as e:
                print(mail.path)
                traceback.print_exc()
                nr_done += 1
            with open('/dev/tty', 'w') as f:
                print(f'{nr_done} / {nr_total}', end='\r', flush=True, file=f)
    
    print_progress('saving.')
    voca.save(f'{FILENAME_VOCA}.new')
    corpus.save(f'{FILENAME_PATHS}.new', f'{FILENAME_INDEX}.new', f'{FILENAME_MATRIX}.new')

    os.rename(f'{FILENAME_VOCA}.new', FILENAME_VOCA)
    os.rename(f'{FILENAME_PATHS}.new', FILENAME_PATHS)
    os.rename(f'{FILENAME_INDEX}.new', FILENAME_INDEX)
    os.rename(f'{FILENAME_MATRIX}.new', FILENAME_MATRIX)

    print_progress('done.')
