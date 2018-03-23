#

import re
import struct
import numpy as np
import scipy.sparse as sp
import pickle

import datetime

class Corpus:
    def __init__(self, voca):
        self.__i2p = []
        self.__p2i = {}
        self.__i2m = []
        self.__voca = voca
        self.__dirty = False
    
    def save(self, paths_file, index_file, matrix_file):
        with open(paths_file, 'wb') as f:
            pickle.dump(self.__i2p, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        with open(index_file, 'wb') as f:
            pickle.dump(self.__i2m, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        with open(matrix_file, 'wb') as f:
            pickle.dump(self.get_matrix(), f, protocol=pickle.HIGHEST_PROTOCOL)
    
    def load(self, paths_file, index_file, matrix_file):
        # print('reading paths.')
        with open(paths_file, 'rb') as f:
            self.__i2p = pickle.load(f)
        self.__p2i = { path: i for i, path in enumerate(self.__i2p) }
        
        # print('reading index.')
        if index_file:
            with open(index_file, 'rb') as f:
                self.__i2m = pickle.load(f)
        else:
            self.__i2m = None
        
        # print('reading matrix.')
        with open(matrix_file, 'rb') as f:
            self.__mat = pickle.load(f)
        # print('done.')
        self.__dirty = False
        
    def add(self, path, words):
        try:
            i = self.__p2i[path]
        except KeyError:
            i = len(self.__i2p)
            self.__i2p.append(path)
            self.__p2i[path] = i
        
        m = { self.__voca.get_no(word) for word in words }
        
        while len(self.__i2m) < i + 1:
            self.__i2m.append(None)
        self.__i2m[i] = m
    
        self.__dirty = True

    def remove(self, path):
        try:
            i = self.__p2i[path]
            self.__i2p[i] = None
            del self.__p2i[path]
            self.__i2m[i] = None
        except KeyError:
            pass
        
        self.__dirty = True
    
    def clear(self):
        self.__i2p = None
        self.__p2i = None
        self.__i2m = None
        self.__voca = None
        self.__mat = None

    def get_path(self, i):
        return self.__i2p[i]
    
    def get_sub_paths(self, folders):
        return { i for i, p in enumerate(self.__i2p) if p is not None and re.sub(r'/\d+$', '', p) in folders }
    
    def get_matrix(self):
        if not self.__dirty:
            return self.__mat
        rows = []
        cols = []
        for i, m in enumerate(self.__i2m):
            if m:
                rows += [ i ] * len(m)
                cols += list(m)
        self.__mat = sp.csr_matrix(( [1] * len(cols), ( rows, cols ) ), shape=(len(self.__i2m), self.__voca.size()), dtype=np.int8)
        self.__dirty = False
        return self.__mat
