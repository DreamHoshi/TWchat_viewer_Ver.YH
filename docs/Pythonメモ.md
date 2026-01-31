## Pythonを使用するにあたって

Pythonのコードは.pyを開けばある
Pythonの実行はコマンドプロンプトから
仮想環境を使うことで、競合するソフトなどを心配しないでデバッグを試すことができる。
ソース：https://qiita.com/shun_sakamoto/items/7944d0ac4d30edf91fde

1.実行ファイル直下まで移動

今回は
cd C:\Python

2.
python -m venv [仮想環境名]

今回は
python -m venv venv

とした。

3.
.\[仮想環境名]\Scripts\activate

今回は
.\venv\Scripts\activate

とした。


これでvenvがアクティブになるので

pip install watchdog beautifulsoup4

と入力（watchdogとbeautifulsoup4をインストール）

------------------------
### 画像などを扱う場合
pip install pillow
------------------------

ファイルの実行は
python chat_viewer.py
python chat_viewer_ver3.py

試験的に作ったファイル
python chat_viewer_example.py

作成時は
pip install pyinstaller　を実行してinstallerをインストール

フォルダ直下二移動
cd C:\Python

pyinstaller --noconsole --onefile chat_viewer.py
アイコンも付ける場合
pyinstaller --noconsole --onefile --icon=zelippi_icon.ico --add-data "zelippi_icon.ico;." chat_viewer.py


------------------------
### インストールしたものを一括にまとめる
pip freeze > requirements.txt
別の環境で再インストール
pip install -r requirements.txt

------------------------

