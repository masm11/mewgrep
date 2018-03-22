import re
import json
import traceback

import sudachipy.config
import sudachipy.dictionary
import sudachipy.tokenizer

class Tokenizer:
    
    EMOJI_REGEX = re.compile(r'[\U0001f000-\U0001f9ff]')
    SYMBOL_ONLY_REGEX = re.compile(r'^[\x00-/:-@\[-`{-\x7f]*$')
    
    def __init__(self):
        with open(sudachipy.config.SETTINGFILE, 'r') as f:
            settings = json.load(f)
        self.__tokenizer = sudachipy.dictionary.Dictionary(settings).create()

    def get_words(self, text):
        try:
            text = re.sub(self.EMOJI_REGEX, ' ', text)
            words = set()
            for m in self.__tokenizer.tokenize(sudachipy.tokenizer.Tokenizer.SplitMode.A, text):
                if m.part_of_speech()[0] in { '助詞', '補助記号' }:
                    continue
                word = m.normalized_form()
                if re.match(self.SYMBOL_ONLY_REGEX, word):
                    continue
                words.add(word)
            return words
        except Exception as e:
            with open('/dev/tty', 'w') as f:
                print(e, file=f)
                traceback.print_exc(file=f)
                print('----------------------------------------', file=f)
                print(text, file=f)
                print('----------------------------------------', file=f)
            raise e
    
