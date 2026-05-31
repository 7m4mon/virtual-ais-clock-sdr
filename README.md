# virtual-ais-clock-sdr

AISの仮想ターゲットを使って、プロッター上にアナログ時計のような表示を作る実験です。

このプログラムは、仮想の船舶情報からAIS Message 1のpayload bitstringを生成し、WebSocket経由でGNU Radio側へ送信します。

主に以下のプロジェクトと組み合わせて遊ぶことを想定しています。

- https://github.com/Mictronics/ais-simulator

## これは何？

AISでは、船舶の位置情報などが定期的に送信されます。

このプロジェクトでは、実在しない複数の仮想船を時計の針や文字盤の位置に配置し、それらのAIS payload bitstringを生成します。

秒針はありません。

現在の構成では、以下の仮想ターゲットを生成します。

- 中心マーカー
- 12個の時刻マーカー
- 時針
- 分針

生成したbitstringは、Mictronics/ais-simulator の Websocket PDU block に送信し、その後 `bitstring_to_frame` block でAISフレーム化して使う想定です。

## 重要な注意

このプログラムは実験・学習・シミュレーション用です。

**実際のAIS周波数で送信してはいけません。**

AISは船舶の安全に関わる無線システムです。  
偽のAIS信号を実際に送信すると、航行安全に悪影響を与える可能性があります。

HackRFなどのSDR送信機と組み合わせる場合でも、以下を守ってください。

- 実際のAIS周波数では送信しない
- アンテナを接続して空中に放射しない
- ダミーロードを使う
- シールド環境または完全なソフトウェアシミュレーションで試す
- 各国の電波法規を守る

## 想定する構成

```text
virtual_ais_clock_bitstring_websocket_sender.py
        ↓ WebSocket
Mictronics ais-simulator Websocket PDU block
        ↓ PDU
bitstring_to_frame block
        ↓
GMSK modulator
        ↓
QT GUI Sink / File Sink / closed lab test path
```

## 必要なもの

- Python 3
- websocket-client
- GNU Radio
- Mictronics/ais-simulator

Python側の依存パッケージは以下でインストールします。

```bash
python3 -m pip install websocket-client
```

## 使い方

まず、Mictronics/ais-simulator のGNU Radioフローグラフを起動し、Websocket PDU block が待ち受けている状態にします。

デフォルトでは以下に接続します。

```text
ws://127.0.0.1:52002
```

その後、このスクリプトを実行します。

```bash
python3 virtual_ais_clock_bitstring_websocket_sender.py
```

正常に接続できると、仮想AISターゲットのbitstringが順番に送信されます。

## 送信間隔

現在の設定では、各仮想船の情報を約200 ms間隔で順番に送信します。

秒針なしの構成では、全ターゲットを1周送信するのに数秒程度かかります。

```python
POSITION_MESSAGE_GAP = 0.2
STATIC_MESSAGE_GAP = 0.2
```

## ファイル

```text
virtual_ais_clock_bitstring_websocket_sender.py
```

AISのNMEA文ではなく、AIS payload bitstringをWebSocketへ送るスクリプトです。

## 元になったアイデア

もともとは、OpenCPNなどにNMEA 0183 AIS文を送り、仮想船でアナログ時計を描画する実験から始まりました。

このリポジトリでは、その発展として、NMEA文ではなくAIS payload bitstringを生成し、GNU Radio / SDR系の実験フローへ接続する形にしています。

## ライセンス

MIT License
