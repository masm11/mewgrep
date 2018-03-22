#

class Voca:
    def __init__(self):
        self.__i2w = []
        self.__w2i = {}

    def get_no(self, word):
        try:
            return self.__w2i[word]
        except KeyError:
            n = len(self.__i2w)
            self.__i2w.append(word)
            self.__w2i[word] = n
            return n
    
    def get_word(self, i):
        return self.__i2w[i]
    
    def save(self, file):
        with open(file, 'w') as f:
            for word in self.__i2w:
                print(word, file=f)
    
    def load(self, file):
        with open(file) as f:
            v = f.read()
            if v[-1] == '\n':
                v = v[:-1]
            self.__i2w = v.split('\n')   # splitlines() は行境界が固定で、U+2028 なんかも含まれてるので、ここでは使えない。
            self.__w2i = { word: i for i, word in enumerate(self.__i2w) }

    def size(self):
        return len(self.__i2w)
