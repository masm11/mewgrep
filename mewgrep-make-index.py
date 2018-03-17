#!/usr/bin/env python

import sys
import os
import os.path
import time
import re
import subprocess
import concurrent.futures.process
import traceback
import scipy as sp
import MeCab
from bs4 import BeautifulSoup
import base64
import quopri
import datetime
import email.header

from voca import Voca
from corpus import Corpus

os.umask(0o077)

updating_index = True
if len(sys.argv) >= 2:
    if sys.argv[1] == '--init':
        updating_index = False

def print_progress(label):
    print(datetime.datetime.now())
    print(label)
    print(subprocess.run(['bash', '-c', 'ps auxww | grep make-index']))

maildir = f'{os.environ["HOME"]}/Mail'
indexdir = '/opt/mewgrep'
FILENAME_VOCA = f'{indexdir}/.mewgrep-voca.txt'
FILENAME_PATHS = f'{indexdir}/.mewgrep-paths.bin'
FILENAME_INDEX = f'{indexdir}/.mewgrep-index.bin'
FILENAME_MATRIX = f'{indexdir}/.mewgrep-matrix.bin'
FILENAME_CHGLOG = f'{indexdir}/.mewgrep-changelog.txt'

MAX_WORKERS = 5

MAIL_FILE_REGEX = r'^\d+$'

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

HEADER_CONTENT_TYPE_REGEX = re.compile(b'^Content-Type:\s*([a-z0-9\-_/]+)', re.IGNORECASE)
HEADER_CONTENT_TYPE_CHARSET_REGEX = re.compile(b'charset=(\"([^\"]+)\"|([^ \t;]+))"?', re.IGNORECASE)
HEADER_CONTENT_TYPE_BOUNDARY_REGEX = re.compile(b'boundary=(\"([^\"]+)\"|([^ \t;]+))', re.IGNORECASE)
HEADER_CONTENT_TRANSFER_ENCODING_REGEX = re.compile(b'^Content-Transfer-Encoding:\s*([a-z0-9\-_/]+)', re.IGNORECASE)
HEADER_SUBJECT = re.compile(b'Subject:\s*(.*)', re.IGNORECASE)

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

def decode_quoted_printable(body):
    return quopri.decodestring(body)

def decode_base64(body):
    return base64.standard_b64decode(body)

def decode_partially_encoded(data):
    # まず ascii で str に decode して、
    # email.header.decode_header() に食わせる。
    lst = email.header.decode_header(data.decode('ascii'))
    # 結果は、[ (bytes, str), ... ] というリスト。
    #   bytes は 部分的に base64 や quoted-printable を decode したバイト列
    #   str は charset。小文字。
    # ただし、もともと食わせた文字列に encode された部分がなければ、
    # そのまま [ (str, str) ] の型で返してくるようだ。
    return ''.join([ p[0].decode(p[1]) if p[1] else (p[0].decode('ascii') if isinstance(p[0], bytes) else p[0]) for p in lst ])

def parse_mail(mail, binary):
    # CR は全て削除。
    binary = binary.replace(b'\r', b'')
    # print(binary)
    # ヘッダとボディに分離。
    if binary[0] != 0x0a:
        hofs = binary.find(b'\n\n')
        if hofs == -1:
            raise RuntimeError('ヘッダの終端が見つからない。')
        header_binary = binary[:hofs]   # 最後の LR は除く。
        body_binary = binary[hofs+2:]
    else:
        header_binary = b''
        body_binary = binary[1:]

    # ヘッダを行ごとに分離。継続行も処理。
    header = []
    for line in header_binary.split(b'\n'):
        if len(line) == 0:
            continue
        first_byte = line[0]
        if first_byte == 32 or first_byte == 9:
            for i in range(len(line)):
                if line[i] not in (32, 9):
                    break
            header[len(header) - 1] += b' ' + line[i:]
        else:
            header.append(line)

    subject = None
    content_type = None
    charset = None
    boundary = None
    content_transfer_encoding = None
    for hdr in header:
        m = re.match(HEADER_CONTENT_TYPE_REGEX, hdr)
        if m:
            content_type = m.group(1).decode('utf-8', 'replace').lower()
            #print('content_type=', content_type)
            m = re.search(HEADER_CONTENT_TYPE_CHARSET_REGEX, hdr)
            if m:
                charset = m.group(2)
                if not charset:
                    charset = m.group(3)
                charset = charset.decode('utf-8', 'replace').lower()
                #print('charset=', charset)
            m = re.search(HEADER_CONTENT_TYPE_BOUNDARY_REGEX, hdr)
            if m:
                boundary = m.group(2)
                if not boundary:
                    boundary = m.group(3)
                #print('boundary=', boundary)

        m = re.match(HEADER_CONTENT_TRANSFER_ENCODING_REGEX, hdr)
        if m:
            content_transfer_encoding = m.group(1).decode('utf-8', 'replace').lower()
            #print('content_transfer_encoding=', content_transfer_encoding)

        m = re.match(HEADER_SUBJECT, hdr)
        if m:
            subject = m.group(1)

    if subject:
        subject = decode_partially_encoded(subject)
        mail.Subject.append(subject)

    if content_transfer_encoding == 'quoted-printable':
        body_binary = decode_quoted_printable(body_binary)
    elif content_transfer_encoding == 'base64':
        body_binary = decode_base64(body_binary)

    if content_type == 'text/plain':
        if charset:
            text = body_binary.decode(charset, 'replace')
        else:
            text = body_binary.decode('ascii', 'replace')
        mail.texts.append(text)
        return

    if content_type == 'text/html':
        soup = BeautifulSoup(body_binary, 'lxml')
        for s in soup(['script', 'style']):
            s.decompose()
        mail.texts.append(' '.join(soup.stripped_strings))
        return

    if isinstance(content_type, str) and content_type.startswith('multipart/'):
        bry = b'\n--' + boundary + b'--\n'
        endpos = body_binary.find(bry)
        if endpos == -1:
            raise RuntimeError('multipart terminator not found.')
        endpos += 1        # \n の分。
        bry = b'--' + boundary + b'\n'
        begpos = 0
        while begpos >= 0:
            begpos = body_binary.find(bry, begpos, endpos)
            if begpos == -1:
                raise RuntimeError('multipart not begin.')
            if begpos == 0:
                break
            if body_binary[begpos - 1] == 0x0a:
                break;
            begpos += 1
        begpos += len(bry)

        body_binaries = body_binary[begpos:endpos].split(bry)

        for body_bin in body_binaries:
            parse_mail(mail, body_bin)

#with open('/home/masm/Mail/inbox/309', 'rb') as f:
#    parse_mail(f.read())
#exit(0)

SYMBOL_ONLY_REGEX = re.compile(r'^[\x00-/:-@\[-`{-\x7f]*$')

tagger = MeCab.Tagger()
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

#mail_files = [ '/home/masm/Mail/inbox/98' ]

def get_words_from_mail(mail):
    with open(f'{maildir}/{mail.path}', 'rb') as f:
        binary = f.read()
    parse_mail(mail, binary)
    words = set()
    for txt in mail.texts:
        if txt:
            words |= get_words(txt)
    return words

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

print_progress('parsing new files.')
mails = [ Mail(path) for path in created ]
with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_mail = { executor.submit(get_words_from_mail, mail): mail for mail in mails }
    for future in concurrent.futures.as_completed(future_to_mail):
        mail = future_to_mail[future]
        try:
            corpus.add(mail.path, future.result())
        except Exception as e:
            print(mail.path)
            traceback.print_exc()

print_progress('saving.')
voca.save(f'{FILENAME_VOCA}.new')
corpus.save(f'{FILENAME_PATHS}.new', f'{FILENAME_INDEX}.new', f'{FILENAME_MATRIX}.new')

os.rename(f'{FILENAME_VOCA}.new', FILENAME_VOCA)
os.rename(f'{FILENAME_PATHS}.new', FILENAME_PATHS)
os.rename(f'{FILENAME_INDEX}.new', FILENAME_INDEX)
os.rename(f'{FILENAME_MATRIX}.new', FILENAME_MATRIX)

print_progress('done.')
