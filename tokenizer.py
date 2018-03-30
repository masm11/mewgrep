import re
import json
import traceback
import socket

class Tokenizer:
    
    def __init__(self):
        pass
    
    def get_words(self, text, modes = 'ABC'):
        sock = None
        try:
            h = { 'modes': modes, 'text': text }
            j = json.dumps(h)
            sock = socket.create_connection(('127.0.0.1', 18080))
            sock.send(j.encode('UTF-8'))
            sock.shutdown(socket.SHUT_WR)
            buf = b''
            while True:
                b = sock.recv(1024)
                if b is None or b == b'':
                    break
                buf += b
            words = set()
            j = json.loads(buf.decode('UTF-8'))
            for word in j:
                words.add(word)
            # print(words)
            return words
        except Exception as e:
            with open('/dev/tty', 'w') as f:
                print(e, file=f)
                traceback.print_exc(file=f)
                print('----------------------------------------', file=f)
                print(text, file=f)
                print('----------------------------------------', file=f)
            raise e
        finally:
            if sock:
                sock.close()
