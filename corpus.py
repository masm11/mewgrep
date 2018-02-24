#

import re
import struct
import numpy as np
import scipy.sparse as sp

class Corpus:
    def __init__(self):
        self.__i2p = []
        self.__p2i = {}
        self.__i2m = []
    
    def save(self, paths_file, index_file):
        with open(paths_file, 'w') as f:
            for word in self.__i2p:
                if not word:
                    word = ''
                print(word, file=f)
        ints = []
        for i, m in enumerate(self.__i2m):
            if m:
                ints.append(i)
                ints.append(len(m))
                ints += list(m)
        ints.insert(0, len(ints))
        with open(index_file, 'wb') as f:
            f.write(struct.pack(f'<{len(ints)}I', *ints))
    
    def load(self, paths_file, index_file):
        with open(paths_file) as f:
            self.__i2p = f.read().splitlines()
        self.__p2i = { path: i for i, path in enumerate(self.__i2p) }
        
        with open(index_file, 'rb') as f:
            nr_ints, = struct.unpack('<I', f.read(4))
            ints = struct.unpack(f'<{nr_ints}I', f.read(nr_ints * 4))
        
        i = 0
        while i < len(ints):
            mail_no = ints[i]
            i += 1
            
            nr_words = ints[i]
            i += 1
            
            word_idxes = ints[i:i+nr_words]
            i += nr_words
            
            while len(self.__i2m) < mail_no + 1:
                self.__i2m.append(None)
            self.__i2m[mail_no] = set(word_idxes)
    
    def add(self, path, words, voca):
        try:
            i = self.__p2i[path]
        except KeyError:
            i = len(self.__i2p)
            self.__i2p.append(path)
            self.__p2i[path] = i
        
        m = { voca.get_no(word) for word in words }
        
        while len(self.__i2m) < i + 1:
            self.__i2m.append(None)
        self.__i2m[i] = m
    
    def remove(self, path):
        try:
            i = self.__p2i[path]
            self.__i2p[i] = None
            del self.__p2i[path]
            self.__i2m[i] = None
        except KeyError:
            pass
    
    def get_path(self, i):
        return self.__i2p[i]
    
    def get_sub_paths(self, folders):
        return { i for i, p in enumerate(self.__i2p) if re.sub(r'/\d+$', '', p) in folders }
    
    def make_matrix(self, voca):
        rows = []
        cols = []
        for i, m in enumerate(self.__i2m):
            if m:
                rows += [ i ] * len(m)
                cols += list(m)
        return sp.csr_matrix(( [1] * len(cols), ( rows, cols ) ), shape=(len(self.__i2m), voca.size()), dtype=np.int8)
