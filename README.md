# mewgrep

[Mew](https://www.mew.org/ja/) から使うための検索エンジンです。

## 注意

メモリをかなり食います。

CPU も結構食います。

解ってる人向けです。

## 必要なもの

- python3 (3.6 以上)
- sudachipy
- numpy
- scipy
- bs4 (BeautifulSoup)
- pyinotify

最新でないと動かないかもしれません。

## sudachipy にパッチを当てる

sudachipy には以下のパッチを当ててインストールしてください。
特に、utf8inputtextbuilder.py の修正は、これを当てないと IndexError が出ます。

```diff
--- sudachipy/utf8inputtextbuilder.py.org	2018-03-18 21:41:11.105646074 +0900
+++ sudachipy/utf8inputtextbuilder.py	2018-03-18 21:49:12.960241490 +0900
@@ -24,7 +24,7 @@
         if end > len(self.modified_text):
             end = len(self.modified_text)
 
-        self.modified_text = self.modified_text.replace(self.modified_text[begin:end], str_)
+        self.modified_text = self.modified_text[:begin] + str_ + self.modified_text[end:]
 
         offset = self.text_offsets[begin]
         length = len(str_)
```

```diff
--- sudachipy/dictionary.py.org	2018-03-18 18:01:24.085005430 +0900
+++ sudachipy/dictionary.py	2018-03-18 18:57:44.640156417 +0900
@@ -57,8 +57,8 @@
     def read_system_dictionary(self, filename):
         if filename is None:
             raise AttributeError("system dictionary is not specified")
-        with open(filename, 'r+b') as system_dic:
-            bytes_ = mmap.mmap(system_dic.fileno(), 0, access=mmap.ACCESS_READ)
+        with open(filename, 'rb') as system_dic:
+            bytes_ = mmap.mmap(system_dic.fileno(), 0, access=mmap.ACCESS_READ|mmap.MAP_SHARED)
         self.buffers.append(bytes_)
 
         offset = 0
@@ -74,8 +74,8 @@
         self.lexicon = dictionarylib.lexiconset.LexiconSet(dictionarylib.doublearraylexicon.DoubleArrayLexicon(bytes_, offset))
 
     def read_user_dictionary(self, filename):
-        with open(filename, 'r+b') as user_dic:
-            bytes_ = mmap.mmap(user_dic.fileno(), 0, prot=mmap.PROT_READ)
+        with open(filename, 'rb') as user_dic:
+            bytes_ = mmap.mmap(user_dic.fileno(), 0, prot=mmap.PROT_READ|mmap.MAP_SHARED)
         self.buffers.append(bytes_)
 
         user_lexicon = dictionarylib.doublearraylexicon.DoubleArrayLexicon(bytes_, 0)
```

## インストール方法

`*.py` を全て同じディレクトリに置いて下さい。

`mewgrepd.service` は `~/.config/systemd/user/` に置いて下さい。
`ExecStart=` は修正してください。

`mew-mewgrep.el` は emacs の load path が通った場所に置いて下さい。
`mew-prog-mewgrep` と `mew-prog-mewgrep-make-index` は修正してください。

以下を実行してください。

```sh
systemctl --user enable mewgrepd
systemctl --user start mewgrepd
```

## 使い方

- Mew の設定

  ```elisp
  (el-get-bundle mew
    (with-eval-after-load-feature 'mew-search
      (require 'mew-mewgrep))
    )
  ```

  私は el-get を使っているのでこうしています。
  mew-search が読み込まれたら mew-mewgrep を読み込む、と設定できれば
  問題ありません。

- index の作り方

  コマンドラインで以下のように実行してください。

  ```sh
  mewgrep-make-index.py --init
  ```

  仕様的におかしいメールについては、いろいろ例外のメッセージが出力されます。
  そのメールは除外して index が作成されます。

- index の更新の仕方

  Mew を起動して summary バッファで `k M` と入力します。

  代わりにコマンドラインで、

  ```sh
  mewgrep-make-index.py
  ```

  と実行してもできます。

- 検索の仕方

  Mew の summary バッファで `k /` または `k ?` と入力します。

  検索語を入力してください。複数の単語を入力できます。
  `&` `|` `!` `(` `)` も使えます。
  `|` より `&` の方が優先度が上です(一般の検索エンジンとは逆です、たぶん)。

  `k /` でなく `C-u k /` と入力すると、検索するフォルダを複数指定できます。

## 説明など

`mewgrep-make-index.py` は、index を作ります。
`--init` を付けると index を作り直します。
`--init` を付けなかった場合は、`~/Mail/.mewgrep-changelog.txt` を参照して、
作成/削除されたファイルのみ更新します。

`mewgrepd.py` は inotify を使って `~/Mail/` 以下を監視します。
作成/削除されたファイルのファイル名を `~/Mail/.mewgrep-changelog.txt` に
出力します。`C` は create、`D` は delete です。

`mewgrep.py` は検索します。
コメントにクエリの文法を簡単に書いてあります。
RFC で使われてる記法がこんなのだったかな、と思い出しながらイメージとして。

`voca.py` と `corpus.py` は上記プログラムから使われます。
`voca.py` は単語の管理、`corpus.py` は index の管理をします。

`mewgrep-make-index.py` の中に

```py
MAX_WORKERS = 4
```

というコードがあります。index を作る際の並列度です。
CPU の core 数に応じて変えると良いかと思います。

## 感想など

最近、自然言語処理を勉強してて、作りたくなったので作ってみました。
「自然言語処理」と言えるような処理は何もありません。sudachipy 使ってるだけです。

遅いしメモリは食うし。
index を作るのに時間がかかるのはある程度仕方のないことだと思いますし、
だから inotify なんか使って軽減してるわけですが。

検索精度があまり良くなくて残念な感じになってしまいました。

## 作者

masm11.
