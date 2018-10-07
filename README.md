# 技術書典５用

技術書典５（2018/10/8）で頒布した”ラズパイさんは百葉箱に恋をする？ ～Google Serverless編～”で使用するソースをまとめたリポジトリです。

# ファイル

|  No. | ファイル名 | 用途 |
| -- |-------- | ---------- |
| 2 |[hyakuyoubako_data_sender.py](https://github.com/Shuichiro-T/gijutsushoten5_hyakuyoubako/blob/master/hyakuyoubako_data_sender.py "hyakuyoubako_data_sender.py") | ラズパイで起動するPythonプログラム。BME280から気温、湿度、気圧を取得してGoogle IoT Coreへ5分おきに送信します。（Python2用です。ごめんなさい。） |
| 2 |[requirements.txt](https://github.com/Shuichiro-T/gijutsushoten5_hyakuyoubako/blob/master/requirements.txt "requirements.txt") | 上記プログラムに必要なライブラリが記載されているリスト。
| 3 |[table.json](https://github.com/Shuichiro-T/gijutsushoten5_hyakuyoubako/blob/master/table.json "table.json") | BigQueryにテーブルを作成するためのテーブル定義。 |


# 実行方法

上記１のプログラムを実行させる手順を紹介します。ラズパイとBME280は接続した状態にしておいてください。

## 1.Python用SMBUSライブラリのインストール
以下のコマンドを実行してライブラリをインストールします。virtualenv等の仮想環境上で実行する場合、"--system-site-packages"等の引数を入れるようにしてください。

```コマンド例
# apt-get install python-smbus
```


## 2.必要なライブラリをpipよりインストール

上記２を使用してpipからライブラリをインストールします。


```コマンド例
$ pip install -r requirements.txt
```

## 3.プログラムの実行

プログラムを実行します。引数は以下の通りです。

| パラメータ名 |設定値 |
| ----         | ------ |
| registry_id | Google IoT Coreで作成したレジストリID |
| project_id | Google IoT Coreを作成したプロジェクトID |
| device_id | Google IoT Coreで作成した端末ID |
| message_type | event  |
| algorithm | RS256  |
| private_key_file | Google IoT Coreでに登録した公開鍵と対になる秘密鍵のパス  |
| cloud_region | Google IoT Coreで作成したレジストリのリージョン  |
| Id | 任意の数字（データとして登録される端末キー）
| location_logitude | ラズパイを置く場所の経度（データとして登録される）  |
| location_latitude | ラズパイを置く場所の緯度（データとして登録される）  |

```プログラム実行例
$python hyakuyoubako_data_sender.py\
  --registry_id=device-reg\
  --project_id=<your_project_id>\
  --device_id=raspberrypi-1\
  --message_type=event\
  --algorithm=RS256\
  --private_key_file=./rsa_private.pem\
  --cloud_region=asia-east1\
  --id=002\
  --location_logitude=0.0\
  --location_latitude=0.0
