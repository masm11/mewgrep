import re
import base64
import quopri
import email.header
from bs4 import BeautifulSoup

class MailParser:

    HEADER_CONTENT_TYPE_REGEX = re.compile(b'^Content-Type:\s*([a-z0-9\-_/]+)', re.IGNORECASE)
    HEADER_CONTENT_TYPE_CHARSET_REGEX = re.compile(b'charset=(\"([^\"]+)\"|([^ \t;]+))"?', re.IGNORECASE)
    HEADER_CONTENT_TYPE_BOUNDARY_REGEX = re.compile(b'boundary=(\"([^\"]+)\"|([^ \t;]+))', re.IGNORECASE)
    HEADER_CONTENT_TRANSFER_ENCODING_REGEX = re.compile(b'^Content-Transfer-Encoding:\s*([a-z0-9\-_/]+)', re.IGNORECASE)
    HEADER_SUBJECT = re.compile(b'Subject:\s*(.*)', re.IGNORECASE)
    
    def __init__(self, maildir, mail):
        self.__maildir = maildir
        self.__mail = mail
    
    def read_binary(self):
        with open(f'{self.__maildir}/{self.__mail.path}', 'rb') as f:
            self.__binary = f.read()
    
    def __decode_quoted_printable(self, body):
        return quopri.decodestring(body)
    
    def __decode_base64(self, body):
        return base64.standard_b64decode(body)
    
    def __decode_partially_encoded(self, data):
        # まず ascii で str に decode して、
        # email.header.decode_header() に食わせる。
        lst = email.header.decode_header(data.decode('ascii'))
        # 結果は、[ (bytes, str), ... ] というリスト。
        #   bytes は 部分的に base64 や quoted-printable を decode したバイト列
        #   str は charset。小文字。
        # ただし、もともと食わせた文字列に encode された部分がなければ、
        # そのまま [ (str, str) ] の型で返してくるようだ。
        return ''.join([ p[0].decode(p[1]) if p[1] else (p[0].decode('ascii') if isinstance(p[0], bytes) else p[0]) for p in lst ])
    
    def __parse(self, binary):
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
            m = re.match(self.HEADER_CONTENT_TYPE_REGEX, hdr)
            if m:
                content_type = m.group(1).decode('utf-8', 'replace').lower()
                #print('content_type=', content_type)
                m = re.search(self.HEADER_CONTENT_TYPE_CHARSET_REGEX, hdr)
                if m:
                    charset = m.group(2)
                    if not charset:
                        charset = m.group(3)
                    charset = charset.decode('utf-8', 'replace').lower()
                    #print('charset=', charset)
                m = re.search(self.HEADER_CONTENT_TYPE_BOUNDARY_REGEX, hdr)
                if m:
                    boundary = m.group(2)
                    if not boundary:
                        boundary = m.group(3)
                    #print('boundary=', boundary)

            m = re.match(self.HEADER_CONTENT_TRANSFER_ENCODING_REGEX, hdr)
            if m:
                content_transfer_encoding = m.group(1).decode('utf-8', 'replace').lower()
                #print('content_transfer_encoding=', content_transfer_encoding)

            m = re.match(self.HEADER_SUBJECT, hdr)
            if m:
                subject = m.group(1)
        
        if subject:
            subject = self.__decode_partially_encoded(subject)
            self.__mail.Subject.append(subject)
        
        if content_transfer_encoding == 'quoted-printable':
            body_binary = self.__decode_quoted_printable(body_binary)
        elif content_transfer_encoding == 'base64':
            body_binary = self.__decode_base64(body_binary)
        
        if content_type == 'text/plain':
            if charset:
                text = body_binary.decode(charset, 'replace')
            else:
                text = body_binary.decode('ascii', 'replace')
            self.__mail.texts.append(text)
            return
        
        if content_type == 'text/html':
            soup = BeautifulSoup(body_binary, 'lxml')
            for s in soup(['script', 'style']):
                s.decompose()
            self.__mail.texts.append(' '.join(soup.stripped_strings))
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
                self.__parse(body_bin)

    def parse(self):
        self.__parse(self.__binary)
