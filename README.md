# youtube_comment

### 概要
Youtubeの指定したチャンネルに対するコメントをCSV形式でダウンロードする

### 前提
#### 実行環境
Google Functionsで実行する想定

以下の情報をGoogle Functionsパラメータとして設定する
* クライアントID
* クライアントシークレット
* 取得コメント数の上限設定（概数）
* リダイレクトURI

#### 言語
Python 3.10
