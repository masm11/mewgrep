# mewgrep

[Mew](https://www.mew.org/ja/) から使うための検索エンジンです。

## 注意

メモリをかなり食います。

CPU も結構食います。

解ってる人向けです。

## 必要なもの

- python3 (3.6 以上)
- mecab-python
- numpy
- scipy
- bs4 (BeautifulSoup)
- pyinotify

最新でないと動かないかもしれません。

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

`voca.py` と `corpus.py` は上記プログラムから使われます。
`voca.py` は単語の管理、`corpus.py` は index の管理をします。

`mewgrep-make-index.py` の中に

```py
MAX_WORKERS = 5
```

というコードがあります。index を作る際の並列度です。
CPU の core 数に応じて変えると良いかと思います。

## 感想など

最近、自然言語処理を勉強してて、作りたくなったので作ってみました。
「自然言語処理」と言えるような処理は何もありません。mecab 使ってるだけです。

遅いしメモリは食うし。
index を作るのに時間がかかるのはある程度仕方のないことだと思いますし、
だから inotify なんか使って軽減してるわけですが、
検索自体に時間がかかってしまうのは本当に何とか改善したいなぁと思っています。

## 作者

masm11.
