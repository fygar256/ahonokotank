# ahotan.py (AHONOKO TANK in python)

昔懐かしのPCゲームを今のパソコンに移植しようシリーズ Games in the attic その4

Pythonで書かれています。

## ファイル構成

| ファイル | 説明 | mapファイル |
| --- | --- | --- |
| `ahotan.py` | 自作のライブラリ supertext を使った版 | `ahotan.map` が必要 |
| `ahotanw.py` | supertext を使わないワイヤーフレーム版 | `ahotan.map` が必要 |
| `ahonokotank.py` | ネット対戦版（pygame） | 不要 |

`ahotan.py` と `ahotanw.py` は、`ahotan.map` をカレントディレクトリに置いて起動してください。

## ゲームの遊び方

左右のタンクを、右と左に分けて二人でプレイする対戦型ゲームです。

弾はタンクの向きに移動するので、タンクで弾を遠隔操作し、相手を砲撃してください。

先に3ポイント取ったほうが勝ちです。

### キー操作

| | 上 | 下 | 左 | 右 | 発射 |
| --- | --- | --- | --- | --- | --- |
| LEFT (Cyan) | `e` | `c` | `s` | `f` | `z` |
| RIGHT (Yellow) | `8` | `2` | `4` | `6` | `0` |

RIGHT はテンキーを使います。`q` を押したらゲームから抜けます。

## ネット対戦版 (ahonokotank.py)

`python3 ahonokotank.py` で起動してください。pythonとpygameを使うので、その二つが動く環境だったら大抵動くでしょう。

LANの２台のコンピュータでネットワーク対戦ができます。通信ポートにTCP(8001)を使います。8001というポートナンバーは往年の名機PC-8001から出ています。そのポートはファイアウォールで塞がないようにしてください。

予め、二人のうちどちらがサーバーになるか決めておかなければいけません。クライアントはサーバーのIPアドレスを知っておく必要があります。プログラムは対称で、一つのコードがサーバーとクライアントの両方になります。クライアント・サーバーの選択を省略して、完全に対称にしたかったのですが、どちらかがサーバーになってlistenしていないとTCP/IP通信は不可能なので、仕方なく。

LANで動くので、インターネットでも動きます。まあ、その場合、ルータのポートフォワーディングやら何やらの設定がややこしいですが。

起動時に「Play in one console」を選択したら、一台のコンピュータでも対戦ができます。

---

# English

# ahotan.py (AHONOKO TANK in python)

Part 4 of the "Games in the attic" series: porting nostalgic old PC games to today's computers.

Written in Python.

## Files

| File | Description | Map file |
| --- | --- | --- |
| `ahotan.py` | Uses supertext, a library I wrote myself | `ahotan.map` required |
| `ahotanw.py` | Wireframe version, without supertext | `ahotan.map` required |
| `ahonokotank.py` | Network-play version (pygame) | Not needed |

To run `ahotan.py` and `ahotanw.py`, place `ahotan.map` in the current directory first.

## How to play

It is a two-player versus game: one player takes the left tank, the other takes the right tank.

Shots travel in the direction the tank is facing, so steer your shots with your tank and blast your opponent.

The first player to score 3 points wins.

### Controls

| | Up | Down | Left | Right | Fire |
| --- | --- | --- | --- | --- | --- |
| LEFT (Cyan) | `e` | `c` | `s` | `f` | `z` |
| RIGHT (Yellow) | `8` | `2` | `4` | `6` | `0` |

RIGHT uses the numeric keypad. Press `q` to quit the game.

## Network play (ahonokotank.py)

Start it with `python3 ahonokotank.py`. It uses Python and pygame, so it should run in just about any environment where those two work.

Two computers on a LAN can play against each other. It uses TCP port 8001 for communication. The port number 8001 comes from the classic PC-8001. Make sure your firewall does not block that port.

The two players must decide in advance which of them will be the server. The client needs to know the server's IP address. The program is symmetric: a single piece of code acts as both server and client. I wanted to drop the client/server choice and make it completely symmetric, but TCP/IP communication is impossible unless one side is listening as a server, so this is how it had to be.

Since it works over a LAN, it also works over the Internet — though in that case the router port forwarding and other settings get a bit fiddly.

If you choose "Play in one console" at startup, you can also play a match on a single computer.
