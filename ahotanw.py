#!/usr/bin/env python3
"""
AHONOKO TANK - Pygame Wireframe Edition
修正版：壁抜け防止 ＋ 弾の中心点当たり判定（かすり許容）
"""

import pygame
import sys
from pygame import Vector2

# Pygame初期化
pygame.init()
WIDTH, HEIGHT = 840, 620
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("AHONOKO TANK - Wireframe Edition")
clock = pygame.time.Clock()
font = pygame.font.SysFont("monospace", 24)
big_font = pygame.font.SysFont("monospace", 48)

# 色
BLACK = (0, 0, 0)
GREEN = (0, 255, 100)
CYAN = (0, 255, 255)
YELLOW = (255, 255, 100)
WHITE = (255, 255, 255)
DARK_GREEN = (0, 100, 50)
RED = (255, 50, 50)
ORANGE = (255, 165, 0)

# 定数
CELL_SIZE = 20
MAP_WIDTH = 40
SCREEN_OFFSET_X = 20
SCREEN_OFFSET_Y = 80

# マップ読み込み
def load_map():
    walls = []
    with open("ahotan.map", "r", encoding="utf-8") as f:
        y = 0
        for line in f:
            line = line.rstrip('\n')
            for x in range(min(MAP_WIDTH, len(line))):
                if line[x] == '＃':
                    walls.append(pygame.Rect(
                        SCREEN_OFFSET_X + x * CELL_SIZE,
                        SCREEN_OFFSET_Y + y * CELL_SIZE,
                        CELL_SIZE, CELL_SIZE
                    ))
            y += 1
    return walls

walls = load_map()

# 方向
DIRECTIONS = {
    'UP': Vector2(0, -1),
    'DOWN': Vector2(0, 1),
    'LEFT': Vector2(-1, 0),
    'RIGHT': Vector2(1, 0)
}

class Tank:
    def __init__(self, x, y, color, controls, side):
        self.pos = Vector2(x, y)
        self.dir = Vector2(1, 0) if side == "right" else Vector2(-1, 0)
        self.color = color
        self.controls = controls
        self.side = side
        self.bullet = None
        self.explosion = None
        self.bullet_timer = 0

    def update(self, keys, other_tank=None):
        move_speed = 0.17
        
        for dname, dvec in DIRECTIONS.items():
            control = self.controls.get(dname)
            pressed = False
            if isinstance(control, list):
                for k in control:
                    if keys[k]:
                        pressed = True
                        break
            else:
                if control and keys[control]:
                    pressed = True
            
            if pressed:
                # 移動先に関わらず、入力された方向に向きを変える（壁際での弾誘導用）
                self.dir = dvec
                
                new_pos = self.pos + dvec * move_speed
                if not self.collides(new_pos, other_tank):
                    self.pos = new_pos
                break

        # 射撃
        shoot_control = self.controls.get('SHOOT')
        shoot_pressed = False
        if isinstance(shoot_control, list):
            for k in shoot_control:
                if keys[k]:
                    shoot_pressed = True
                    break
        else:
            if shoot_control and keys[shoot_control]:
                shoot_pressed = True
                
        if shoot_pressed and (not self.bullet or not self.bullet['active']):
            # 発射位置を1.0にし、壁の向こう側にスポーンしてすり抜けるのを防ぐ
            bullet_pos = self.pos + self.dir * 1.0
            self.bullet = {'pos': bullet_pos.copy(), 'dir': self.dir.copy(), 'active': True}
            self.bullet_timer = 10  # 発射後約0.16秒は自分に当たらない

    def collides(self, pos, other_tank=None):
        # 相手タンクとの衝突判定 (すり抜け防止)
        if other_tank:
            if pos.distance_to(other_tank.pos) < 0.9:
                return True

        # 壁との衝突判定
        offsets = [(0.15, 0.15), (0.85, 0.15), (0.15, 0.85), (0.85, 0.85)]
        for ox, oy in offsets:
            check_pos = Vector2(pos.x + ox, pos.y + oy)
            rect = pygame.Rect(
                SCREEN_OFFSET_X + int(check_pos.x) * CELL_SIZE,
                SCREEN_OFFSET_Y + int(check_pos.y) * CELL_SIZE,
                CELL_SIZE * 0.7, CELL_SIZE * 0.7
            )
            for wall in walls:
                if rect.colliderect(wall):
                    return True
        return False

    def update_bullet(self):
        if not self.bullet or not self.bullet['active']:
            return
        
        # 弾誘導
        self.bullet['dir'] = self.dir.copy()
        self.bullet['pos'] += self.bullet['dir'] * 0.25

        if self.bullet_timer > 0:
            self.bullet_timer -= 1

        # 弾の中心ピクセル座標を計算
        px = SCREEN_OFFSET_X + self.bullet['pos'].x * CELL_SIZE + CELL_SIZE / 2
        py = SCREEN_OFFSET_Y + self.bullet['pos'].y * CELL_SIZE + CELL_SIZE / 2
        
        # 弾の中心点のみを当たり判定に使う（少しかすってもOK）
        for wall in walls:
            if wall.collidepoint(px, py):
                self.bullet['active'] = False
                return

    def draw(self, surface):
        cx = SCREEN_OFFSET_X + self.pos.x * CELL_SIZE + CELL_SIZE // 2
        cy = SCREEN_OFFSET_Y + self.pos.y * CELL_SIZE + CELL_SIZE // 2
        
        size = CELL_SIZE * 0.85
        points = [(-size/2, -size/2), (size/2, -size/2), (size/2, size/2), (-size/2, size/2)]
        rotated = []
        for px, py in points:
            if self.dir.x > 0:   rx, ry = px, py
            elif self.dir.x < 0: rx, ry = -px, py
            elif self.dir.y < 0: rx, ry = py, -px
            else:                rx, ry = py, px
            rotated.append((cx + rx, cy + ry))
        
        pygame.draw.polygon(surface, self.color, rotated, 3)
        
        # 砲塔
        turret_len = CELL_SIZE * 0.95
        tx = cx + self.dir.x * turret_len
        ty = cy + self.dir.y * turret_len
        pygame.draw.line(surface, CYAN, (cx, cy), (tx, ty), 5)

        # 弾
        if self.bullet and self.bullet['active']:
            bx = SCREEN_OFFSET_X + self.bullet['pos'].x * CELL_SIZE + CELL_SIZE // 2
            by = SCREEN_OFFSET_Y + self.bullet['pos'].y * CELL_SIZE + CELL_SIZE // 2
            pygame.draw.circle(surface, YELLOW, (int(bx), int(by)), 7)

        # 爆発エフェクト
        if self.explosion and self.explosion['time'] > 0:
            ex = SCREEN_OFFSET_X + self.explosion['pos'].x * CELL_SIZE + CELL_SIZE // 2
            ey = SCREEN_OFFSET_Y + self.explosion['pos'].y * CELL_SIZE + CELL_SIZE // 2
            radius = int(15 * (self.explosion['time'] / 15))
            pygame.draw.circle(surface, ORANGE, (int(ex), int(ey)), radius)
            pygame.draw.circle(surface, RED, (int(ex), int(ey)), radius - 4)
            self.explosion['time'] -= 1
            if self.explosion['time'] <= 0:
                self.explosion = None

def check_hit(attacker, target, left_score, right_score):
    if not attacker.bullet or not attacker.bullet['active']:
        return False, left_score, right_score
    
    dist = attacker.bullet['pos'].distance_to(target.pos)
    if dist < 1.15:  # 当たりやすく調整
        # 自分の弾が自分に当たる場合のみタイマーチェック
        if attacker is target and attacker.bullet_timer > 0:
            return False, left_score, right_score  # まだすり抜け期間
        
        attacker.bullet['active'] = False
        target.explosion = {'pos': target.pos.copy(), 'time': 15}
        
        # 得点処理
        if attacker is target:
            # 自爆 → 相手に得点
            if attacker.side == "left":
                right_score += 1
            else:
                left_score += 1
        else:
            # 通常攻撃 → 自分に得点
            if attacker.side == "left":
                left_score += 1
            else:
                right_score += 1
        return True, left_score, right_score
    return False, left_score, right_score

def draw_walls(surface):
    for wall in walls:
        pygame.draw.rect(surface, GREEN, wall, 3)
        inner = wall.inflate(-6, -6)
        pygame.draw.rect(surface, DARK_GREEN, inner, 1)

def draw_ui(surface, left_score, right_score):
    left_text = font.render(f"LEFT: {left_score}", True, CYAN)
    right_text = font.render(f"RIGHT: {right_score}", True, CYAN)
    surface.blit(left_text, (40, 25))
    surface.blit(right_text, (WIDTH - 180, 25))

    title = big_font.render("AHONOKO TANK", True, GREEN)
    surface.blit(title, (WIDTH//2 - title.get_width()//2, 15))

def main():
    left_controls = {'UP': pygame.K_e, 'DOWN': pygame.K_c, 'LEFT': pygame.K_s, 'RIGHT': pygame.K_f, 'SHOOT': pygame.K_z}
    right_controls = {
        'UP': [pygame.K_8, pygame.K_KP8],
        'DOWN': [pygame.K_2, pygame.K_KP2],
        'LEFT': [pygame.K_4, pygame.K_KP4],
        'RIGHT': [pygame.K_6, pygame.K_KP6],
        'SHOOT': [pygame.K_0, pygame.K_KP0]
    }

    left_tank = Tank(2, 12, CYAN, left_controls, "left")
    right_tank = Tank(37, 12, YELLOW, right_controls, "right")

    left_score = 0
    right_score = 0
    game_state = "playing"

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                if game_state in ["left_win", "right_win"]:
                    pygame.quit()
                    sys.exit()
                left_tank = Tank(2, 12, CYAN, left_controls, "left")
                right_tank = Tank(37, 12, YELLOW, right_controls, "right")
                game_state = "playing"

        keys = pygame.key.get_pressed()

        if game_state == "playing":
            left_tank.update(keys, right_tank)
            right_tank.update(keys, left_tank)
            
            left_tank.update_bullet()
            right_tank.update_bullet()

            # 攻撃者とターゲットの全組み合わせをチェック (自爆含む)
            tanks = [left_tank, right_tank]
            for attacker in tanks:
                for target in tanks:
                    if game_state == "playing":
                        hit, left_score, right_score = check_hit(attacker, target, left_score, right_score)
                        if hit:
                            game_state = "round_end"

            if left_score >= 3:
                game_state = "left_win"
            elif right_score >= 3:
                game_state = "right_win"

        # 描画
        screen.fill(BLACK)
        draw_walls(screen)
        left_tank.draw(screen)
        right_tank.draw(screen)
        draw_ui(screen, left_score, right_score)

        if game_state == "round_end":
            msg = big_font.render(" ROUND END! ", True, YELLOW)
            screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2 - 60))
            sub = font.render(" ENTER to NEXT ROUND ", True, WHITE)
            screen.blit(sub, (WIDTH//2 - sub.get_width()//2, HEIGHT//2 + 10))
        elif game_state == "left_win":
            msg = big_font.render(" LEFT WINS! ", True, CYAN)
            screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2 - 50))
        elif game_state == "right_win":
            msg = big_font.render(" RIGHT WINS! ", True, CYAN)
            screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2 - 50))

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
