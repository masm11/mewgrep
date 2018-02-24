#!/usr/bin/env python

import os
import sys
import re
import struct
import subprocess
import numpy as np
import scipy.sparse as sp
import MeCab

from voca import Voca
from corpus import Corpus

debugging = sys.stdout.isatty()

maildir = f'{os.environ["HOME"]}/Mail'
folders = set()
q = None
i = 1
while i < len(sys.argv):
    if sys.argv[i] == '-r':
        maildir = sys.argv[i + 1]
        i += 2
    elif sys.argv[i] == '-f':
        folders.add(sys.argv[i + 1])
        i += 2
    elif sys.argv[i] == '-q':
        q = sys.argv[i + 1].split()
        i += 2
    else:
        raise RuntimeError('bad arg.')

if not q:
    raise RuntimeError('-q <query> not specified.')

FILENAME_VOCA = f'{maildir}/.mewgrep-voca.txt'
FILENAME_PATHS = f'{maildir}/.mewgrep-paths.bin'
FILENAME_INDEX = f'{maildir}/.mewgrep-index.bin'
FILENAME_MATRIX = f'{maildir}/.mewgrep-matrix.bin'
FILENAME_CHGLOG = f'{maildir}/.mewgrep-changelog.txt'

if not debugging:
    sys.stderr = open('/dev/null', 'w')

print('loading voca.', file=sys.stderr)
voca = Voca()
voca.load(FILENAME_VOCA)

print('loading corpus.', file=sys.stderr)
corpus = Corpus(voca)
corpus.load(FILENAME_PATHS, None, FILENAME_MATRIX)

print('making matrix.', file=sys.stderr)
mailmat = corpus.get_matrix()

# EXPR = EXPR_OR
# EXPR_OR = EXPR_AND ( 'or' EXPR_AND )*
# EXPR_AND = EXPR_IAND ( 'and' EXPR_IAND )*
# EXPR_IAND = EXPR_NOT ( EXPR_NOT )*
# EXPR_NOT = 'not' EXPRNOT
#          | EXPR_PAR
# EXPR_PAR = '(' EXPR_OR ')'
#          | STR
# STR = 文字列

class QStateBack(Exception):
    pass

class QState:
    def __init__(self, parent=None, q=None):
        self.__parent = parent
        self.__initial_pos = self.__parent.__pos if self.__parent is not None else 0
        self.__pos = self.__initial_pos
        self.__q = q if q else self.__parent.__q
    def get_next_token(self):
        if self.__pos >= len(self.__q):
            return None
        tok = self.__q[self.__pos]
        self.__pos += 1
        return tok
    def save(self):
        return QState(parent=self)
    def restore(self):
        self.__pos = self.__initial_pos
    def finish(self):
        self.__parent.__pos = self.__pos
    def next_token_is(self, s):
        if self.__pos >= len(self.__q):
            return False
        if self.__q[self.__pos] == s:
            self.__pos += 1
            return True
        return False
    def next_token_is_keyword(self):
        if self.__pos >= len(self.__q):
            return True
        return self.__q[self.__pos] in { 'or', 'and', 'not', '(', ')' }
    def throw(self):
        raise QStateBack()
    def is_empty(self):
        return self.__pos >= len(self.__q)

def eval_expr(q):
    q = QState(q=q)
    r = eval_expr_or(q)
    if not q.is_empty():
        raise RuntimeError('syntax error.')
    return r

def eval_expr_or(q):
    try:
        q = q.save()
        r = eval_expr_and(q)
        if r is None:
            q.throw()
        while q.next_token_is('or'):
            s = eval_expr_and(q)
            if s is None:
                break
            r |= s
        return r
    except QStateBack:
        q.restore()
        return None
    finally:
        q.finish()

def eval_expr_and(q):
    try:
        q = q.save()
        r = eval_expr_iand(q)
        if r is None:
            q.throw()
        while q.next_token_is('and'):
            s = eval_expr_iand(q)
            if s is None:
                break
            r &= s
        return r
    except QStateBack:
        q.restore()
        return None
    finally:
        q.finish()

def eval_expr_iand(q):
    try:
        q = q.save()
        r = eval_expr_not(q)
        if r is None:
            q.throw()
        while True:
            s = eval_expr_not(q)
            if s is None:
                break
            r &= s
        return r
    except QStateBack:
        q.restore()
        return None
    finally:
        q.finish()

def eval_expr_not(q):
    try:
        q = q.save()
        if q.next_token_is('not'):
            s = eval_expr_not(q)
            if s is None:
                q.throw()
            return set(all_mails) - s
        s = eval_expr_par(q)
        if s is None:
            q.throw()
        return s
    except QStateBack:
        q.restore()
    finally:
        q.finish()

def eval_expr_par(q):
    try:
        q = q.save()
        if q.next_token_is('('):
            r = eval_expr_or(q)
            if r is None:
                q.throw()
            if not q.next_token_is(')'):
                q.throw()
            return r
        return eval_str(q)
    except QStateBack:
        q.restore()
        return None
    finally:
        q.finish()

SYMBOL_ONLY_REGEX = re.compile(r'^[\x00-/:-@\[-`{-\x7f]*$')

def get_words(text):
    words = set()
    m = tagger.parse(text)
    for line in m.splitlines():
        tab_idx = line.find('\t')
        if tab_idx == -1:
            continue
        surface = line[:tab_idx]
        features = line[tab_idx+1:]
        features = features.split(',')
        if features[0] in { '助詞', '記号' }:
            continue
        orig = '*'
        if len(features) >= 7:
            orig = features[6]
        if orig == '*':
            orig = surface
        if re.match(SYMBOL_ONLY_REGEX, orig):
            continue
        words.add(orig)
    return words

def eval_str(q):
    try:
        q = q.save()
        if q.is_empty():
            q.throw()
        if q.next_token_is_keyword():
            q.throw()
        
        sentence = q.get_next_token()
        words = get_words(sentence)
        
        r = set(all_mails)
        
        try:
            for word in words:
                # 1-hot vector.
                wvec = sp.csc_matrix(([1], ( [voca.get_no(word)], [0] )), shape=(voca.size(), 1), dtype=np.int8)
                rvec = mailmat.dot(wvec)
                r &= set(rvec.nonzero()[0])
        except KeyError:
            return set()
        
        return  r
    except QStateBack:
        q.restore()
        return None
    finally:
        q.finish()

if folders:
    all_mails = corpus.get_sub_paths(folders)
else:
    all_mails = frozenset(range(mailmat.shape[0]))

tagger = MeCab.Tagger()
#print(all_mails)
mails = eval_expr(q)
#print(mails)

def key_to_sort(p):
    i = p.rindex('/')
    return ( p[:i], int(p[i+1:]) )

print('\n'.join(sorted([corpus.get_path(mail) for mail in mails], key=key_to_sort)))

# print(subprocess.run(['bash', '-c', 'ps auxww | grep mewgrep']))
