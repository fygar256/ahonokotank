#!/usr/bin/env python3
"""
AHONOKO TANK - Network Battle Edition (完全統合・単一ファイル版)

これまで tank.py / tank_common.py / ahotan.map の3ファイルに分かれていたものを
すべて1つのファイルにまとめたものです。マップデータもコードの中に埋め込んで
いるので、このファイル1つだけで動作します（外部ファイルは不要）。

起動するとまずメニュー画面が表示され、マウスクリックで役割を選びます。
  SERVER をクリック            : 接続を待つ側 = LEFT（水色）として起動
  CLIENT をクリック            : 接続先IPアドレスを入力して接続しにいく側 = RIGHT（黄色）として起動
  PLAY IN ONE CONSOLE をクリック : ネットワークを使わず、1台のPC・1つの画面の中で
                                 LEFT/RIGHTの両方をキーボードだけで操作して対戦する
                                 （マウスは同時に2つの戦車を操作できないため使いません）
（コマンドライン引数は使いません）

■ 対称設計のポイント（当たり判定＝被害者側が権威を持つ方式）
  ・自分の戦車の移動・向き・弾の発射と飛翔は「自分」が計算する
  ・相手の戦車の情報（位置・向き・弾）はネットワークから受け取って表示するだけ
  ・「自分の戦車に弾が当たったかどうか」は必ず自分自身が判定する
      - 自分の弾が自分に当たった（自爆）→ 自分で判定
      - 相手の弾が自分に当たった         → これも自分で判定
        （相手の戦車の位置は自分が一番正確に知っているため）
    どちらの場合も「被弾＝相手に1点」というルールなので、
    自分が被弾を検出した時点で「相手の得点」を自分が計算し、相手に送信する。
  ・自分の得点（＝相手から見た「相手の被弾」）は、相手から送られてくる
    数値をそのまま信頼して表示する。
  これにより、LEFT側／RIGHT側で処理内容に偏りのない対称な設計になっている。
  違うのは「TCP接続をどちらが待ち受けるか」だけ。

操作:
  移動   : マウスで行き先を指して左ボタンを押している間だけ、その点へ向かって移動します
           （上下左右4方向に量子化。左ボタンを離すとその場で停止します）。
           押したままマウスを動かせば、行き先もそれに追従します。
           キーボードでも操作可能で、押している間はキー入力が優先されます。
           移動キーを離すとその場で必ず停止します（マウス左ボタンを押したままキーを
           使った場合も、キーを離した時点で止まります。マウスでの移動を再開するには
           左ボタンを押し直してください）。
             SERVER(LEFT)側  : S/F/E/C キー（左/右/上/下）
             CLIENT(RIGHT)側 : テンキー 4/6/8/2（左/右/上/下）
  照準   : 移動方向がそのまま砲台・弾の向きになる
  発砲   : マウス右クリック、または
             SERVER(LEFT)側  : Z キー
             CLIENT(RIGHT)側 : テンキー 0
  次ラウンド : 自動（ラウンド終了後10秒でキー入力なしに次のラウンドへ進みます。
              待ちきれない場合はENTERで即座に進めることもできます）
  終了   : Q キー、またはウィンドウを閉じる

起動方法:
  python3 tank.py
  起動したら画面上の SERVER / CLIENT ボタンをクリックしてください。
  CLIENT を選んだ場合は、続けて画面に接続先IPアドレスを入力し、
  ENTERキーか CONNECT ボタンで接続します
  （同じPCで2つ起動して試す場合は 127.0.0.1 のままでOKです）。
"""

import math
import json
import socket
import time
import threading
import sys

import pygame

pygame.init()

# ============================================================================
# 定数
# ============================================================================

WIDTH, HEIGHT = 840, 620
CELL_SIZE = 20
MAP_WIDTH = 40
SCREEN_OFFSET_X = 20
SCREEN_OFFSET_Y = 80

BLACK = (0, 0, 0)
GREEN = (0, 255, 100)
CYAN = (0, 255, 255)
YELLOW = (255, 255, 100)
WHITE = (255, 255, 255)
DARK_GREEN = (0, 100, 50)
RED = (255, 50, 50)
ORANGE = (255, 165, 0)

MOVE_SPEED = 0.17
BULLET_SPEED = 0.25
FIRE_COOLDOWN_FRAMES = 10
HIT_DIST = 1.15
PORT = 8001
ROUND_END_WAIT_SECONDS = 10.0  # ラウンド終了後、キー入力なしで自動的に次のラウンドが始まるまでの待ち時間
GAME_OVER_WAIT_SECONDS = 50.0  # ゲームセット（勝敗確定）後、キー入力なしで自動終了するまでの待ち時間
ROUND_RESTART_GRACE_SECONDS = 0.5  # 次のラウンドへ進んだ直後、相手からの古い round_end 情報を無視する猶予時間
MOUSE_TARGET_REACHED_DIST = 0.3  # 行き先までの残り距離がこれ未満の軸は「着いた」とみなす（マス単位）

# ============================================================================
# マップデータ（元 ahotan.map の内容をそのまま埋め込み）
# ============================================================================

MAP_ROWS = (
    "＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃",
    "＃　　　　　　　　　　　　　　　　　＃　　＃　　　　　　　　　　　　　　　　　＃",
    "＃　　　　　　　　　　　　　　　　　＃　　＃　　　　　　　　　　　　　　　　　＃",
    "＃　　　　　　　　　　　　　　　　　＃　　＃　　　　　　　　　　　　　　　　　＃",
    "＃　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　＃",
    "＃　　　　　　　　＃＃＃＃＃＃＃　　　　　　　　＃＃＃＃＃＃＃　　　　　　　　＃",
    "＃　　＃＃　　　　＃　　　　　　　　　　　　　　　　　　　　＃　　　　＃＃　　＃",
    "＃　　　＃　　　　＃　　　　　　　　　　　　　　　　　　　　＃　　　　＃　　　＃",
    "＃　　　＃　　　　＃　　　　　　　　　　　　　　　　　　　　＃　　　　＃　　　＃",
    "＃　　　＃　　　　＃　　　　　　　　＃　　＃　　　　　　　　＃　　　　＃　　　＃",
    "＃　　　＃　　　　　　　　　　＃＃＃＃　　＃＃＃＃　　　　　　　　　　＃　　　＃",
    "＃　　　＃　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　＃　　　＃",
    "＃　　　＃　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　＃　　　＃",
    "＃　　　＃　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　＃　　　＃",
    "＃　　　＃　　　　　　　　　　＃＃＃＃　　＃＃＃＃　　　　　　　　　　＃　　　＃",
    "＃　　　＃　　　　＃　　　　　　　　＃　　＃　　　　　　　　＃　　　　＃　　　＃",
    "＃　　　＃　　　　＃　　　　　　　　　　　　　　　　　　　　＃　　　　＃　　　＃",
    "＃　　　＃　　　　＃　　　　　　　　　　　　　　　　　　　　＃　　　　＃　　　＃",
    "＃　　＃＃　　　　＃　　　　　　　　　　　　　　　　　　　　＃　　　　＃＃　　＃",
    "＃　　　　　　　　＃＃＃＃＃＃＃　　　　　　　　＃＃＃＃＃＃＃　　　　　　　　＃",
    "＃　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　＃",
    "＃　　　　　　　　　　　　　　　　　＃　　＃　　　　　　　　　　　　　　　　　＃",
    "＃　　　　　　　　　　　　　　　　　＃　　＃　　　　　　　　　　　　　　　　　＃",
    "＃　　　　　　　　　　　　　　　　　＃　　＃　　　　　　　　　　　　　　　　　＃",
    "＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃＃",
)


def load_map():
    walls = []
    for y, line in enumerate(MAP_ROWS):
        for x in range(min(MAP_WIDTH, len(line))):
            if line[x] == "＃":
                walls.append(pygame.Rect(
                    SCREEN_OFFSET_X + x * CELL_SIZE,
                    SCREEN_OFFSET_Y + y * CELL_SIZE,
                    CELL_SIZE, CELL_SIZE
                ))
    return walls


WALLS = load_map()


# ============================================================================
# 座標・当たり判定まわり
# ============================================================================

def tank_screen_pos(pos):
    """マップ座標 [x, y] を画面ピクセル座標 (中心) に変換"""
    return (
        SCREEN_OFFSET_X + pos[0] * CELL_SIZE + CELL_SIZE // 2,
        SCREEN_OFFSET_Y + pos[1] * CELL_SIZE + CELL_SIZE // 2,
    )


def screen_to_map_pos(screen_pos):
    """画面ピクセル座標をマップ座標 [x, y] に変換（tank_screen_pos の逆変換）"""
    return [
        (screen_pos[0] - SCREEN_OFFSET_X - CELL_SIZE // 2) / CELL_SIZE,
        (screen_pos[1] - SCREEN_OFFSET_Y - CELL_SIZE // 2) / CELL_SIZE,
    ]


def collides(pos, other_pos=None):
    """指定位置に戦車を置いたときに、壁または相手の戦車とぶつかるか判定"""
    if other_pos is not None:
        dx = pos[0] - other_pos[0]
        dy = pos[1] - other_pos[1]
        if math.hypot(dx, dy) < 0.9:
            return True

    offsets = [(0.15, 0.15), (0.85, 0.15), (0.15, 0.85), (0.85, 0.85)]
    for ox, oy in offsets:
        cx = pos[0] + ox
        cy = pos[1] + oy
        rect = pygame.Rect(
            SCREEN_OFFSET_X + int(cx) * CELL_SIZE,
            SCREEN_OFFSET_Y + int(cy) * CELL_SIZE,
            int(CELL_SIZE * 0.7), int(CELL_SIZE * 0.7)
        )
        for wall in WALLS:
            if rect.colliderect(wall):
                return True
    return False


def bullet_hits_target(bullet_pos, target_pos):
    return math.hypot(bullet_pos[0] - target_pos[0], bullet_pos[1] - target_pos[1]) < HIT_DIST


# ============================================================================
# 自分の戦車のシミュレーション（LEFT/RIGHTどちらも全く同じ関数を使う）
# ============================================================================

def new_tank_state(x, y):
    return {
        "pos": [float(x), float(y)],
        "angle": 0.0,
        "bullet": None,
        "bullet_timer": 0,
        "explosion": None,
    }


def apply_move(tank, dx, dy, other_pos=None):
    """戦車を (dx, dy) 方向へ1フレーム分動かす。実際に動けたかどうかを返す"""
    if dx == 0 and dy == 0:
        return False
    new_pos = [tank["pos"][0] + dx * MOVE_SPEED, tank["pos"][1] + dy * MOVE_SPEED]
    if collides(new_pos, other_pos):
        return False
    tank["pos"] = new_pos
    return True


def handle_fire(tank, fire_flag):
    if fire_flag and (not tank["bullet"] or not tank["bullet"]["active"]):
        angle = tank["angle"]
        bx = tank["pos"][0] + math.cos(angle) * 1.0
        by = tank["pos"][1] + math.sin(angle) * 1.0
        tank["bullet"] = {"pos": [bx, by], "active": True}
        tank["bullet_timer"] = FIRE_COOLDOWN_FRAMES


def update_bullet(tank):
    bullet = tank["bullet"]
    if not bullet or not bullet["active"]:
        return
    angle = tank["angle"]
    bullet["pos"][0] += math.cos(angle) * BULLET_SPEED
    bullet["pos"][1] += math.sin(angle) * BULLET_SPEED

    if tank["bullet_timer"] > 0:
        tank["bullet_timer"] -= 1

    px, py = tank_screen_pos(bullet["pos"])
    for wall in WALLS:
        if wall.collidepoint(px, py):
            bullet["active"] = False
            return


def tick_explosion(tank):
    if tank["explosion"] and tank["explosion"]["time"] > 0:
        tank["explosion"]["time"] -= 1
        if tank["explosion"]["time"] <= 0:
            tank["explosion"] = None


def mouse_target_directions_4way(pos, target):
    """
    現在位置 pos から、マウスで指している行き先 target へ向かう方向を上下左右4方向に
    量子化し、優先度の高い順の候補リストとして返す。

    残りの距離が大きい軸を先に試す。その方向が壁でふさがれていたときのために
    もう一方の軸も候補に入れてあり、壁沿いに回り込めるようになっている。
    どちらの軸も着いていれば空リスト（＝その場で停止）。
    """
    dx = target[0] - pos[0]
    dy = target[1] - pos[1]

    candidates = []
    if abs(dx) >= MOUSE_TARGET_REACHED_DIST:
        candidates.append((1, 0) if dx > 0 else (-1, 0))
    if abs(dy) >= MOUSE_TARGET_REACHED_DIST:
        candidates.append((0, 1) if dy > 0 else (0, -1))

    # 縦の残り距離の方が大きければ、縦を先に試す
    if len(candidates) == 2 and abs(dy) > abs(dx):
        candidates.reverse()
    return candidates


def dir_to_angle(dx, dy):
    """4方向ベクトル (dx, dy) を、描画・弾の飛翔に使うラジアン角度に変換する"""
    if dx > 0:
        return 0.0
    if dx < 0:
        return math.pi
    if dy > 0:
        return math.pi / 2
    return -math.pi / 2


# ---- キーボード操作（マウスと併用可能。役割(LEFT/RIGHT)ごとに割り当てが異なる） ----
KEY_BINDINGS = {
    "left": {
        "UP": [pygame.K_e],
        "DOWN": [pygame.K_c],
        "LEFT": [pygame.K_s],
        "RIGHT": [pygame.K_f],
        "FIRE": [pygame.K_z],
    },
    "right": {
        # NumLockがオフでも動くよう、テンキーと通常の数字キーの両方を受け付ける
        "UP": [pygame.K_8, pygame.K_KP8],
        "DOWN": [pygame.K_2, pygame.K_KP2],
        "LEFT": [pygame.K_4, pygame.K_KP4],
        "RIGHT": [pygame.K_6, pygame.K_KP6],
        "FIRE": [pygame.K_0, pygame.K_KP0],
    },
}


def _any_pressed(keys, key_list):
    return any(keys[k] for k in key_list)


def keyboard_direction_4way(keys, bindings):
    """
    押されている方向キーから (dx, dy) を返す。4方向のうちいずれか、
    何も押されていなければ (0, 0)。左右を上下より優先する。
    """
    if _any_pressed(keys, bindings["LEFT"]):
        return -1, 0
    if _any_pressed(keys, bindings["RIGHT"]):
        return 1, 0
    if _any_pressed(keys, bindings["UP"]):
        return 0, -1
    if _any_pressed(keys, bindings["DOWN"]):
        return 0, 1
    return 0, 0


def resolve_movement_and_fire(my_tank, keys, my_keys, mouse_target, fire_button_down, opp_pos):
    """
    キーボードとマウス、両方からの入力を使って移動・向き・発射を決定し、実際に適用する。

    移動: 方向キーを押している「間だけ」その方向へ動き、離した瞬間にその場で止まる。
          キーを押していない間は、マウス左ボタンを押している「間だけ」、マウスが
          指している点へ向かって上下左右4方向に量子化して進む。左ボタンを離せば停止する。
          どちらも操作していなければ、その場で停止する（＝勝手には動かない）。
    発射: マウス右クリック、または割り当てられた発射キーのどちらでも発射できる。
          押し続けている間は、前の弾が消えるたびに自動で再発射される。

    mouse_target: 左ボタンを押している間はマウスが指すマップ座標 [x, y]、離していれば None。

    戻り値: (このフレームで発射すべきか, このフレームはキーボードで動かしたか) の2要素タプル。
            2つめは、キー操作をした時点でマウス追従をやめさせる（＝キーを離せば確実に
            止まる）ために呼び出し側が使う。
    """
    dx4, dy4 = keyboard_direction_4way(keys, my_keys)
    keyboard_moving = dx4 != 0 or dy4 != 0

    if keyboard_moving:
        # キーボード操作を優先する
        my_tank["angle"] = dir_to_angle(dx4, dy4)
        apply_move(my_tank, dx4, dy4, opp_pos)
    elif mouse_target is not None:
        for dx4, dy4 in mouse_target_directions_4way(my_tank["pos"], mouse_target):
            if apply_move(my_tank, dx4, dy4, opp_pos):
                my_tank["angle"] = dir_to_angle(dx4, dy4)
                break

    fire = bool(fire_button_down) or _any_pressed(keys, my_keys["FIRE"])
    return fire, keyboard_moving



# ============================================================================
# 描画
# ============================================================================

def draw_walls(surface):
    for wall in WALLS:
        pygame.draw.rect(surface, GREEN, wall, 3)
        inner = wall.inflate(-6, -6)
        pygame.draw.rect(surface, DARK_GREEN, inner, 1)


def _rotate(px, py, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    return (px * c - py * s, px * s + py * c)


def draw_tank(surface, pos, angle, color, bullet, explosion):
    cx, cy = tank_screen_pos(pos)

    size = CELL_SIZE * 0.85
    points = [(-size / 2, -size / 2), (size / 2, -size / 2),
              (size / 2, size / 2), (-size / 2, size / 2)]
    poly = []
    for px, py in points:
        rx, ry = _rotate(px, py, angle)
        poly.append((cx + rx, cy + ry))
    pygame.draw.polygon(surface, color, poly, 3)

    turret_len = CELL_SIZE * 0.95
    tx = cx + math.cos(angle) * turret_len
    ty = cy + math.sin(angle) * turret_len
    pygame.draw.line(surface, CYAN, (cx, cy), (tx, ty), 5)

    if bullet and bullet.get("active"):
        bx = SCREEN_OFFSET_X + bullet["pos"][0] * CELL_SIZE + CELL_SIZE // 2
        by = SCREEN_OFFSET_Y + bullet["pos"][1] * CELL_SIZE + CELL_SIZE // 2
        pygame.draw.circle(surface, YELLOW, (int(bx), int(by)), 7)

    if explosion and explosion.get("time", 0) > 0:
        ex = SCREEN_OFFSET_X + explosion["pos"][0] * CELL_SIZE + CELL_SIZE // 2
        ey = SCREEN_OFFSET_Y + explosion["pos"][1] * CELL_SIZE + CELL_SIZE // 2
        radius = int(15 * (explosion["time"] / 15))
        pygame.draw.circle(surface, ORANGE, (int(ex), int(ey)), max(radius, 0))
        pygame.draw.circle(surface, RED, (int(ex), int(ey)), max(radius - 4, 0))


def draw_ui(surface, font, big_font, left_score, right_score):
    left_text = font.render(f"LEFT: {left_score}", True, CYAN)
    right_text = font.render(f"RIGHT: {right_score}", True, CYAN)
    surface.blit(left_text, (40, 25))
    surface.blit(right_text, (WIDTH - 180, 25))
    title = big_font.render("AHONOKO TANK-net", True, GREEN)
    surface.blit(title, (WIDTH // 2 - title.get_width() // 2, 15))


def draw_game_state_message(surface, big_font, font, game_state, round_end_remaining=None, game_over_remaining=None):
    if game_state == "round_end":
        msg = big_font.render(" ROUND END! ", True, YELLOW)
        surface.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - 60))
        seconds = int(math.ceil(round_end_remaining)) if round_end_remaining is not None else 0
        seconds = max(seconds, 0)
        sub = font.render(f" NEXT ROUND IN {seconds}s ", True, WHITE)
        surface.blit(sub, (WIDTH // 2 - sub.get_width() // 2, HEIGHT // 2 + 10))
    elif game_state in ("left_win", "right_win"):
        label = " LEFT WINS! " if game_state == "left_win" else " RIGHT WINS! "
        msg = big_font.render(label, True, CYAN)
        surface.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - 50))
        seconds = int(math.ceil(game_over_remaining)) if game_over_remaining is not None else 0
        seconds = max(seconds, 0)
        sub = font.render(f" QUITTING IN {seconds}s (or press ENTER) ", True, WHITE)
        surface.blit(sub, (WIDTH // 2 - sub.get_width() // 2, HEIGHT // 2 + 10))


# ============================================================================
# 対称なメインループ本体（LEFT側・RIGHT側どちらもこれを呼ぶだけ）
# ============================================================================

def run_peer(sock, my_side):
    """
    sock    : 接続済みのTCPソケット（listen側／connect側どちらでもよい）
    my_side : "left" または "right"（自分がどちらの戦車を操作するか）
    """
    assert my_side in ("left", "right")

    if my_side == "left":
        my_start = (2, 12)
        opp_start = (37, 12)
        my_color, opp_color = CYAN, YELLOW
    else:
        my_start = (37, 12)
        opp_start = (2, 12)
        my_color, opp_color = YELLOW, CYAN

    my_keys = KEY_BINDINGS[my_side]

    pygame.display.set_caption(f"AHONOKO TANK - {my_side.upper()} (YOU)")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 24)
    big_font = pygame.font.SysFont("monospace", 48)

    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass

    lock = threading.Lock()
    net = {
        "pos": list(opp_start),
        "angle": 0.0,
        "bullet": None,
        "explosion": None,
        "reported_score": 0,   # 相手が計算した「自分(my_side)の得点」
        "remote_game_state": None,
        "enter": False,
        "ack_hit": False,
    }
    connected = [True]

    def recv_loop():
        buf = b""
        try:
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line:
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue
                    with lock:
                        if "pos" in msg:
                            net["pos"] = msg["pos"]
                        if "angle" in msg:
                            net["angle"] = msg["angle"]
                        if "bullet" in msg:
                            net["bullet"] = msg["bullet"]
                        if "explosion" in msg:
                            net["explosion"] = msg["explosion"]
                        if "score" in msg:
                            net["reported_score"] = msg["score"]
                        if "game_state" in msg:
                            net["remote_game_state"] = msg["game_state"]
                        if msg.get("enter"):
                            net["enter"] = True
                        if msg.get("ack_hit"):
                            net["ack_hit"] = True
        except (ConnectionResetError, OSError):
            pass
        finally:
            connected[0] = False

    threading.Thread(target=recv_loop, daemon=True).start()

    my_tank = new_tank_state(*my_start)
    my_score = 0     # 自分の得点（相手が被弾を検出して知らせてくれた数）
    opp_score = 0    # 相手の得点（自分が被弾を検出して自分で数える数）
    game_state = "playing"
    round_end_deadline = None  # ラウンド終了後、自動で次に進む時刻（time.time()基準）
    game_over_deadline = None  # ゲームセット後、自動で終了する時刻（time.time()基準）
    ignore_remote_round_end_until = 0.0  # この時刻までは、相手からのround_end通知を(古い情報として)無視する

    def quit_game():
        try:
            sock.close()
        except OSError:
            pass
        pygame.quit()
        sys.exit()

    def reset_to_playing():
        """次のラウンドへ進む（ENTER・タイムアウト・相手からの合図、いずれの場合も共通の処理）"""
        nonlocal my_tank, game_state, round_end_deadline, ignore_remote_round_end_until
        my_tank = new_tank_state(*my_start)
        game_state = "playing"
        round_end_deadline = None
        # 相手がまだ古い「round_end」を送ってきていても、それに引き戻されないようにする
        ignore_remote_round_end_until = time.time() + ROUND_RESTART_GRACE_SECONDS

    # マウスのボタンは「押されているか」をポーリングするだけだと、ウィンドウの外で
    # 離したときなどに離したことを取りこぼし、押しっぱなし扱いのまま戦車が走り続けて
    # しまうことがある。そこで押下／解放のイベントでも状態を持ち、両方を突き合わせる。
    mouse_follow = False       # 左ボタン: 押している間だけマウスの指す点へ移動
    mouse_fire_down = False    # 右ボタン: 押している間だけ発射

    while True:
        enter_flag_out = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                quit_game()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mouse_follow = True
                elif event.button == 3:
                    mouse_fire_down = True
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    mouse_follow = False
                elif event.button == 3:
                    mouse_fire_down = False
            if event.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
                # ウィンドウからフォーカスが外れたら、押しっぱなし扱いを解除して停止する
                mouse_follow = False
                mouse_fire_down = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                if game_state in ("left_win", "right_win"):
                    # Do not need to wait; ENTER can quit immediately
                    quit_game()
                elif game_state == "round_end":
                    # Do not need to wait; ENTER can advance to the next round immediately
                    reset_to_playing()
                    enter_flag_out = True

        with lock:
            opp_pos = net["pos"]
            opp_angle = net["angle"]
            opp_bullet = net["bullet"]
            opp_explosion = net["explosion"]
            my_score = net["reported_score"]
            remote_game_state = net["remote_game_state"]
            remote_enter = net["enter"]
            net["enter"] = False
            remote_ack_hit = net["ack_hit"]
            net["ack_hit"] = False

        if remote_enter and game_state not in ("left_win", "right_win"):
            reset_to_playing()

        if remote_ack_hit and my_tank["bullet"]:
            # 自分の弾が相手に命中したと相手から知らされたので、自分の画面でも消す
            my_tank["bullet"]["active"] = False

        if (
            remote_game_state in ("round_end", "left_win", "right_win")
            and game_state == "playing"
            and time.time() >= ignore_remote_round_end_until
        ):
            game_state = remote_game_state

        # ラウンド終了状態になったら、キー入力なしで ROUND_END_WAIT_SECONDS 秒後に
        # 自動的に次のラウンドへ進む
        if game_state == "round_end":
            if round_end_deadline is None:
                round_end_deadline = time.time() + ROUND_END_WAIT_SECONDS
            round_end_remaining = round_end_deadline - time.time()
            if round_end_remaining <= 0:
                reset_to_playing()
                enter_flag_out = True
        else:
            round_end_deadline = None
            round_end_remaining = None

        # ゲームセット（勝敗確定）になったら、キー入力なしで GAME_OVER_WAIT_SECONDS 秒後に
        # 自動的に終了する
        if game_state in ("left_win", "right_win"):
            if game_over_deadline is None:
                game_over_deadline = time.time() + GAME_OVER_WAIT_SECONDS
            game_over_remaining = game_over_deadline - time.time()
            if game_over_remaining <= 0:
                quit_game()
        else:
            game_over_deadline = None
            game_over_remaining = None

        ack_hit_out = False


        if game_state == "playing":
            keys = pygame.key.get_pressed()
            mouse_buttons = pygame.mouse.get_pressed()
            # イベントとポーリングのどちらかが「離した」と言えば離したものとして扱う
            mouse_follow = mouse_follow and mouse_buttons[0]
            mouse_fire_down = mouse_fire_down and mouse_buttons[2]

            # 左ボタンを押している「間だけ」、いま指している点へ向かって進む
            mouse_target = screen_to_map_pos(pygame.mouse.get_pos()) if mouse_follow else None
            fire_button_down = mouse_fire_down  # 右クリックで発射

            fire, keyboard_moving = resolve_movement_and_fire(
                my_tank, keys, my_keys, mouse_target, fire_button_down, opp_pos
            )
            if keyboard_moving:
                # キーで動かしたら、マウスの行き先追従は解除する。
                # こうしておかないと、左ボタンを押したままキーを離したときに
                # マウス追従へ戻って動き続けてしまう（キーを離したら必ず止まる）。
                mouse_follow = False

            handle_fire(my_tank, fire)
            update_bullet(my_tank)

            hit_self = False

            # (1) 自爆判定：自分の弾が自分自身に当たったか
            b = my_tank["bullet"]
            if b and b["active"] and my_tank["bullet_timer"] <= 0:
                if bullet_hits_target(b["pos"], my_tank["pos"]):
                    b["active"] = False
                    hit_self = True

            # (2) 相手の弾が自分に当たったか（自分の戦車位置は自分が一番正確に知っている）
            if (not hit_self) and opp_bullet and opp_bullet.get("active"):
                if bullet_hits_target(opp_bullet["pos"], my_tank["pos"]):
                    hit_self = True
                    ack_hit_out = True  # 相手へ「あなたの弾は当たりました」と伝える

            if hit_self:
                my_tank["explosion"] = {"pos": list(my_tank["pos"]), "time": 15}
                opp_score += 1
                game_state = "round_end"
                if opp_score >= 3:
                    game_state = "right_win" if my_side == "left" else "left_win"

        tick_explosion(my_tank)

        if not connected[0]:
            screen.fill(BLACK)
            msg = big_font.render("DISCONNECTED", True, RED)
            screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - 30))
            sub = font.render("PRESS Q TO QUIT", True, WHITE)
            screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, HEIGHT // 2 + 30))
            pygame.display.flip()
            clock.tick(30)
            continue

        # ---- 送信（自分の情報だけを相手に伝える） ----
        payload = {
            "pos": my_tank["pos"],
            "angle": my_tank["angle"],
            "bullet": my_tank["bullet"],
            "explosion": my_tank["explosion"],
            "score": opp_score,
            "game_state": game_state,
        }
        if enter_flag_out:
            payload["enter"] = True
        if ack_hit_out:
            payload["ack_hit"] = True

        try:
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        except OSError:
            pass

        # ---- 描画 ----
        screen.fill(BLACK)
        draw_walls(screen)
        if my_side == "left":
            draw_tank(screen, my_tank["pos"], my_tank["angle"], my_color, my_tank["bullet"], my_tank["explosion"])
            draw_tank(screen, opp_pos, opp_angle, opp_color, opp_bullet, opp_explosion)
            draw_ui(screen, font, big_font, my_score, opp_score)
        else:
            draw_tank(screen, opp_pos, opp_angle, opp_color, opp_bullet, opp_explosion)
            draw_tank(screen, my_tank["pos"], my_tank["angle"], my_color, my_tank["bullet"], my_tank["explosion"])
            draw_ui(screen, font, big_font, opp_score, my_score)
        draw_game_state_message(screen, big_font, font, game_state, round_end_remaining, game_over_remaining)

        pygame.display.flip()
        clock.tick(60)


# ============================================================================
# 起動処理（LEFT側は接続を待ち、RIGHT側は接続しにいく）
# ============================================================================

def wait_for_guest():
    """LEFT側（接続を待つ役）: 接続を待つ。待っている間も画面を更新し続ける。"""
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 24)
    big_font = pygame.font.SysFont("monospace", 48)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(1)
    srv.setblocking(False)
    print(f"[LEFT] Waiting for connection on TCP port {PORT} ...")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                pygame.quit()
                sys.exit()
        try:
            conn, addr = srv.accept()
            print(f"[LEFT] Connected: {addr}")
            srv.close()
            return conn
        except BlockingIOError:
            pass

        screen.fill(BLACK)
        msg = big_font.render("WAITING...", True, GREEN)
        screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2 - 60))
        sub = font.render(f"Listening on TCP :{PORT}  (You are LEFT / CYAN)", True, WHITE)
        screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, HEIGHT // 2 + 10))
        pygame.display.flip()
        clock.tick(30)


def connect_to_host(host):
    """RIGHT側（接続しにいく役）: 指定したホストへ接続する。"""
    print(f"[RIGHT] Connecting to {host}:{PORT} ...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, PORT))
    return sock


def check_hit_local(attacker, attacker_is_left, target, scores):
    """
    ローカル対戦用の命中判定（ネットワーク版と違い、両者の情報を1つのプロセスが
    直接知っているので、被害者権威方式にする必要はなく、素直に判定できる）。
    """
    bullet = attacker["bullet"]
    if not bullet or not bullet["active"]:
        return False
    if not bullet_hits_target(bullet["pos"], target["pos"]):
        return False
    if attacker is target and attacker["bullet_timer"] > 0:
        return False  # 発射直後の自爆すり抜け猶予

    bullet["active"] = False
    target["explosion"] = {"pos": list(target["pos"]), "time": 15}

    if attacker is target:
        # 自爆 → 相手に得点
        scores["right" if attacker_is_left else "left"] += 1
    else:
        # 通常命中 → 自分に得点
        scores["left" if attacker_is_left else "right"] += 1
    return True


def run_local_two_player():
    """
    1台のPC・1つのウィンドウだけで対戦するローカルモード。
    ネットワーク通信は一切使わず、LEFT/RIGHTの両方の戦車をこのプロセスだけで
    計算する（＝ネットワーク版のような「被害者側が権威を持つ」工夫は不要で、
    素直に両者の当たり判定ができる）。
    マウスは同時に2つの戦車を操作できないため、このモードでは両プレイヤーとも
    キーボードのみで操作する（LEFT=S/F/E/C+Z、RIGHT=テンキー4/6/8/2+0）。
    """
    pygame.display.set_caption("AHONOKO TANK - LOCAL (One Console)")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 24)
    big_font = pygame.font.SysFont("monospace", 48)

    left_tank = new_tank_state(2, 12)
    right_tank = new_tank_state(37, 12)
    scores = {"left": 0, "right": 0}
    game_state = "playing"
    round_end_deadline = None
    game_over_deadline = None

    def reset_round():
        nonlocal left_tank, right_tank, game_state, round_end_deadline
        left_tank = new_tank_state(2, 12)
        right_tank = new_tank_state(37, 12)
        game_state = "playing"
        round_end_deadline = None

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                if game_state in ("left_win", "right_win"):
                    pygame.quit()
                    sys.exit()
                elif game_state == "round_end":
                    reset_round()

        if game_state == "playing":
            keys = pygame.key.get_pressed()

            dx4, dy4 = keyboard_direction_4way(keys, KEY_BINDINGS["left"])
            if dx4 != 0 or dy4 != 0:
                left_tank["angle"] = dir_to_angle(dx4, dy4)
                apply_move(left_tank, dx4, dy4, right_tank["pos"])
            handle_fire(left_tank, _any_pressed(keys, KEY_BINDINGS["left"]["FIRE"]))
            update_bullet(left_tank)

            dx4, dy4 = keyboard_direction_4way(keys, KEY_BINDINGS["right"])
            if dx4 != 0 or dy4 != 0:
                right_tank["angle"] = dir_to_angle(dx4, dy4)
                apply_move(right_tank, dx4, dy4, left_tank["pos"])
            handle_fire(right_tank, _any_pressed(keys, KEY_BINDINGS["right"]["FIRE"]))
            update_bullet(right_tank)

            hit_any = False
            for attacker, attacker_is_left in ((left_tank, True), (right_tank, False)):
                for target in (left_tank, right_tank):
                    if check_hit_local(attacker, attacker_is_left, target, scores):
                        hit_any = True

            if hit_any:
                game_state = "round_end"
            if scores["left"] >= 3:
                game_state = "left_win"
            elif scores["right"] >= 3:
                game_state = "right_win"

        tick_explosion(left_tank)
        tick_explosion(right_tank)

        if game_state == "round_end":
            if round_end_deadline is None:
                round_end_deadline = time.time() + ROUND_END_WAIT_SECONDS
            round_end_remaining = round_end_deadline - time.time()
            if round_end_remaining <= 0:
                reset_round()
        else:
            round_end_deadline = None
            round_end_remaining = None

        if game_state in ("left_win", "right_win"):
            if game_over_deadline is None:
                game_over_deadline = time.time() + GAME_OVER_WAIT_SECONDS
            game_over_remaining = game_over_deadline - time.time()
            if game_over_remaining <= 0:
                pygame.quit()
                sys.exit()
        else:
            game_over_deadline = None
            game_over_remaining = None

        screen.fill(BLACK)
        draw_walls(screen)
        draw_tank(screen, left_tank["pos"], left_tank["angle"], CYAN, left_tank["bullet"], left_tank["explosion"])
        draw_tank(screen, right_tank["pos"], right_tank["angle"], YELLOW, right_tank["bullet"], right_tank["explosion"])
        draw_ui(screen, font, big_font, scores["left"], scores["right"])
        draw_game_state_message(screen, big_font, font, game_state, round_end_remaining, game_over_remaining)

        pygame.display.flip()
        clock.tick(60)


IP_ALLOWED_CHARS = "0123456789.-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def draw_button(surface, rect, text, font, color, mouse_pos):
    """ボタンを描画する。マウスが乗っていればハイライトする。戻り値はホバー中かどうか"""
    hovered = rect.collidepoint(mouse_pos)
    draw_color = YELLOW if hovered else color
    pygame.draw.rect(surface, draw_color, rect, 3)
    label = font.render(text, True, draw_color)
    surface.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))
    return hovered


def run_start_menu():
    """
    起動直後のメニュー画面。
    マウスクリックで SERVER（接続を待つ役・LEFT）、CLIENT（接続しにいく役・RIGHT）、
    PLAY IN ONE CONSOLE（1画面ローカル対戦）のいずれかを選ぶ。
    CLIENTを選んだ場合は、続けて接続先のIPアドレスをその場で入力する。
    選択が終わると run_peer() または run_local_two_player() に進む
    （この関数はそこで戻ってこない）。
    """
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("AHONOKO TANK - Select Mode")
    clock = pygame.time.Clock()
    title_font = pygame.font.SysFont("monospace", 48)
    label_font = pygame.font.SysFont("monospace", 26)
    small_font = pygame.font.SysFont("monospace", 18)

    # ボタンの幅は、表示する中で一番長いラベルが収まるように実際の描画幅から
    # 計算し、すべてのボタンで揃える
    button_labels = ["SERVER (LEFT / CYAN)", "CLIENT (RIGHT / YELLOW)", "PLAY IN ONE CONSOLE"]
    content_width = max(label_font.size(text)[0] for text in button_labels)
    button_width = content_width + 40  # 左右の余白

    server_button = pygame.Rect(WIDTH // 2 - button_width // 2, 230, button_width, 60)
    client_button = pygame.Rect(WIDTH // 2 - button_width // 2, 310, button_width, 60)
    local_button = pygame.Rect(WIDTH // 2 - button_width // 2, 390, button_width, 60)
    ip_box = pygame.Rect(WIDTH // 2 - button_width // 2, 260, button_width, 50)
    connect_button = pygame.Rect(WIDTH // 2 - button_width // 2, 330, button_width, 55)
    back_button = pygame.Rect(WIDTH // 2 - button_width // 2, 400, button_width, 45)

    mode = "menu"  # "menu" -> クリックで役割を選ぶ画面 / "client_ip" -> IP入力画面
    ip_text = "127.0.0.1"
    error_message = ""

    while True:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                pygame.quit()
                sys.exit()

            if mode == "menu":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if server_button.collidepoint(event.pos):
                        conn = wait_for_guest()
                        run_peer(conn, "left")
                        return
                    if client_button.collidepoint(event.pos):
                        mode = "client_ip"
                        error_message = ""
                    if local_button.collidepoint(event.pos):
                        run_local_two_player()
                        return

            elif mode == "client_ip":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        host = ip_text.strip() or "127.0.0.1"
                        try:
                            sock = connect_to_host(host)
                        except OSError as e:
                            error_message = f"Connection failed: {e}"
                        else:
                            run_peer(sock, "right")
                            return
                    elif event.key == pygame.K_BACKSPACE:
                        ip_text = ip_text[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        mode = "menu"
                        error_message = ""
                    elif event.unicode in IP_ALLOWED_CHARS and len(ip_text) < 40:
                        ip_text += event.unicode

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if connect_button.collidepoint(event.pos):
                        host = ip_text.strip() or "127.0.0.1"
                        try:
                            sock = connect_to_host(host)
                        except OSError as e:
                            error_message = f"Connection failed: {e}"
                        else:
                            run_peer(sock, "right")
                            return
                    if back_button.collidepoint(event.pos):
                        mode = "menu"
                        error_message = ""

        # ---- 描画 ----
        screen.fill(BLACK)
        title = title_font.render("AHONOKO TANK", True, GREEN)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 100))

        if mode == "menu":
            sub = small_font.render("Click to choose your role", True, WHITE)
            screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 190))
            draw_button(screen, server_button, "SERVER (LEFT / CYAN)", label_font, CYAN, mouse_pos)
            draw_button(screen, client_button, "CLIENT (RIGHT / YELLOW)", label_font, YELLOW, mouse_pos)
            draw_button(screen, local_button, "PLAY IN ONE CONSOLE", label_font, GREEN, mouse_pos)
            hint = small_font.render("(one console: both players use the keyboard, no mouse)", True, WHITE)
            screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, local_button.bottom + 10))
        else:
            sub = small_font.render("Enter the SERVER's IP address, then click CONNECT (or press ENTER)", True, WHITE)
            screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 200))
            pygame.draw.rect(screen, WHITE, ip_box, 2)
            ip_surface = label_font.render(ip_text, True, WHITE)
            screen.blit(ip_surface, (ip_box.x + 10, ip_box.y + ip_box.height // 2 - ip_surface.get_height() // 2))
            draw_button(screen, connect_button, "CONNECT", label_font, GREEN, mouse_pos)
            draw_button(screen, back_button, "BACK", small_font, WHITE, mouse_pos)
            if error_message:
                err = small_font.render(error_message, True, RED)
                screen.blit(err, (WIDTH // 2 - err.get_width() // 2, 460))

        pygame.display.flip()
        clock.tick(30)


def main():
    run_start_menu()


if __name__ == "__main__":
    main()
