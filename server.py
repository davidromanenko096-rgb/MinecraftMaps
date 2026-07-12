import pygame
import moderngl as mgl
import numpy as np
import math
import random
import sys
from collections import deque

# ---------- НАСТРОЙКИ ----------
WIDTH, HEIGHT = 800, 600
CHUNK_SIZE = 16
VIEW_DIST = 4
GRAVITY = -25
JUMP_SPEED = 8
PLAYER_SPEED = 5
MOUSE_SENS = 0.002
FOG_DIST = 80

# ---------- ШУМ ПЕРЛИНА ----------
class PerlinNoise:
    def __init__(self, seed=0):
        self.perm = list(range(256))
        random.seed(seed)
        random.shuffle(self.perm)
        self.perm += self.perm

    def fade(self, t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    def lerp(self, a, b, t):
        return a + t * (b - a)

    def grad(self, hash, x, y):
        h = hash & 3
        u = x if h < 2 else y
        v = y if h < 2 else x
        return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)

    def noise(self, x, y):
        xi = int(x) & 255
        yi = int(y) & 255
        xf = x - int(x)
        yf = y - int(y)
        u = self.fade(xf)
        v = self.fade(yf)
        a = self.perm[xi] + yi
        b = self.perm[xi + 1] + yi
        return self.lerp(
            self.lerp(self.grad(self.perm[a], xf, yf), self.grad(self.perm[b], xf - 1, yf), u),
            self.lerp(self.grad(self.perm[a + 1], xf, yf - 1), self.grad(self.perm[b + 1], xf - 1, yf - 1), u),
            v
        )

perlin = PerlinNoise(42)

# ---------- ГЕНЕРАЦИЯ ЧАНКА ----------
def generate_chunk(cx, cz):
    blocks = []
    heights = []
    for x in range(CHUNK_SIZE):
        for z in range(CHUNK_SIZE):
            wx = cx * CHUNK_SIZE + x
            wz = cz * CHUNK_SIZE + z
            h = perlin.noise(wx * 0.05, wz * 0.05) * 5 + perlin.noise(wx * 0.1, wz * 0.1) * 2
            h = int(h + 6)
            if h < 1:
                h = 1
            if h > 18:
                h = 18
            heights.append(h)

    water_level = 4
    for x in range(CHUNK_SIZE):
        for z in range(CHUNK_SIZE):
            h = heights[x * CHUNK_SIZE + z]
            max_y = max(h, water_level)
            for y in range(max_y + 1):
                if y == h:
                    if h <= water_level:
                        typ = 'sand' if h <= water_level - 1 else 'grass'
                    else:
                        typ = 'grass'
                elif y > h:
                    if y <= water_level:
                        typ = 'water'
                    else:
                        continue
                else:
                    if y > h - 3:
                        typ = 'dirt'
                    else:
                        typ = 'stone'
                blocks.append((x, y, z, typ))

    # Деревья
    for x in range(CHUNK_SIZE):
        for z in range(CHUNK_SIZE):
            h = heights[x * CHUNK_SIZE + z]
            if h > water_level and random.random() < 0.02:
                trunk = 4 + random.randint(0, 2)
                for y in range(h + 1, h + trunk + 1):
                    blocks.append((x, y, z, 'wood'))
                for dx in range(-2, 3):
                    for dz in range(-2, 3):
                        for dy in range(-1, 2):
                            lx = x + dx
                            lz = z + dz
                            ly = h + trunk + dy
                            if not (0 <= lx < CHUNK_SIZE and 0 <= lz < CHUNK_SIZE):
                                continue
                            if abs(dx) == 2 and abs(dz) == 2:
                                continue
                            if abs(dx) == 2 or abs(dz) == 2:
                                if dy == 0 and random.random() < 0.5:
                                    continue
                            blocks.append((lx, ly, lz, 'leaves'))
    return blocks

# ---------- ЦВЕТА БЛОКОВ ----------
BLOCK_COLORS = {
    'grass': (0.48, 0.70, 0.26),
    'dirt': (0.55, 0.43, 0.39),
    'stone': (0.62, 0.62, 0.62),
    'wood': (0.43, 0.30, 0.26),
    'leaves': (0.30, 0.69, 0.31),
    'sand': (0.96, 0.87, 0.70),
    'water': (0.13, 0.59, 0.95),
    'planks': (0.84, 0.66, 0.43),
    'cobblestone': (0.46, 0.46, 0.46),
}
BLOCK_LIST = ['grass', 'dirt', 'stone', 'wood', 'planks']

# ---------- ВЕРТЕКСНЫЙ ШЕЙДЕР ----------
VS = '''
#version 330
in vec3 in_position;
in vec3 in_color;
uniform mat4 projection;
uniform mat4 view;
out vec3 v_color;
void main() {
    gl_Position = projection * view * vec4(in_position, 1.0);
    v_color = in_color;
}
'''

FS = '''
#version 330
in vec3 v_color;
out vec4 f_color;
void main() {
    f_color = vec4(v_color, 1.0);
}
'''

# ---------- КЛАСС МИРА ----------
class World:
    def __init__(self, ctx):
        self.ctx = ctx
        self.chunks = {}  # (cx, cz) -> vertex buffer
        self.loading = set()
        self.program = self.ctx.program(vertex_shader=VS, fragment_shader=FS)
        self.projection = self.ctx.uniform('projection', 'mat4')
        self.view = self.ctx.uniform('view', 'mat4')

    def build_chunk(self, cx, cz):
        blocks = generate_chunk(cx, cz)
        vertices = []
        # Простой рендеринг – каждый блок как 6 граней (12 треугольников)
        # Для упрощения используем куб из 8 вершин (индексированный)
        # Сделаем без индексов, просто 6 граней * 2 треуг = 36 вершин на блок
        for x, y, z, typ in blocks:
            if typ == 'air' or typ == 'water':
                continue
            color = BLOCK_COLORS.get(typ, (1, 1, 1))
            self._add_cube(vertices, cx * CHUNK_SIZE + x, y, cz * CHUNK_SIZE + z, color)
        if not vertices:
            return
        vertices = np.array(vertices, dtype='f4')
        vbo = self.ctx.buffer(vertices)
        vao = self.ctx.vertex_array(self.program, [(vbo, '3f 3f', 'in_position', 'in_color')])
        self.chunks[(cx, cz)] = vao

    def _add_cube(self, verts, x, y, z, color):
        # 6 граней, 2 треугольника, 3 вершины на треугольник = 36 вершин
        # Координаты куба от 0 до 1
        cx, cy, cz = x, y, z
        # Временно используем оптимизированный метод – добавляем только видимые грани (соседи)
        # Но для простоты – все 6 граней
        # Вершины куба (смещения)
        offsets = [
            (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),  # перед
            (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)   # зад
        ]
        # Индексы граней
        faces = [
            (0,1,2, 0,2,3),  # перед
            (4,6,5, 4,7,6),  # зад
            (0,4,5, 0,5,1),  # низ
            (2,6,7, 2,7,3),  # верх
            (0,3,7, 0,7,4),  # лево
            (1,5,6, 1,6,2)   # право
        ]
        for face in faces:
            for idx in face:
                ox, oy, oz = offsets[idx]
                verts.extend([cx + ox, cy + oy, cz + oz, *color])

    def render(self, projection, view):
        self.projection.write(projection)
        self.view.write(view)
        for vao in self.chunks.values():
            vao.render()

    def unload_chunk(self, cx, cz):
        if (cx, cz) in self.chunks:
            self.chunks[(cx, cz)].release()
            del self.chunks[(cx, cz)]

    def get_block(self, wx, wy, wz):
        # Проверка наличия блока в загруженных чанках
        cx = int(math.floor(wx / CHUNK_SIZE))
        cz = int(math.floor(wz / CHUNK_SIZE))
        if (cx, cz) not in self.chunks:
            return None
        # Не реализовано – для простоты возвращаем заглушку
        return None

# ---------- ИГРОК ----------
class Player:
    def __init__(self):
        self.position = np.array([8.0, 25.0, 8.0], dtype='f4')
        self.yaw = 0.0
        self.pitch = -0.3
        self.velocity = np.array([0.0, 0.0, 0.0], dtype='f4')
        self.on_ground = False

    def update(self, dt, keys, world):
        # Движение
        forward = np.array([
            -math.sin(self.yaw),
            0,
            -math.cos(self.yaw)
        ])
        right = np.array([
            math.cos(self.yaw),
            0,
            -math.sin(self.yaw)
        ])
        move = np.array([0.0, 0.0, 0.0])
        if keys['w']:
            move += forward
        if keys['s']:
            move -= forward
        if keys['a']:
            move -= right
        if keys['d']:
            move += right
        if np.linalg.norm(move) > 0:
            move = move / np.linalg.norm(move) * PLAYER_SPEED * dt
        self.position[0] += move[0]
        self.position[2] += move[2]

        # Гравитация
        if keys['space'] and self.on_ground:
            self.velocity[1] = JUMP_SPEED
            self.on_ground = False
        self.velocity[1] += GRAVITY * dt
        self.position[1] += self.velocity[1] * dt

        # Коллизия с землёй
        if self.position[1] < 0:
            self.position[1] = 0
            self.velocity[1] = 0
            self.on_ground = True

        # Грубая коллизия с блоками (только по Y)
        # Здесь нужно проверять блок под ногами – пропускаем для простоты

    def get_view_matrix(self):
        # Камера
        eye = self.position
        target = eye + np.array([
            -math.sin(self.yaw) * math.cos(self.pitch),
            math.sin(self.pitch),
            -math.cos(self.yaw) * math.cos(self.pitch)
        ])
        up = np.array([0, 1, 0])
        return self._look_at(eye, target, up)

    def _look_at(self, eye, target, up):
        f = target - eye
        f = f / np.linalg.norm(f)
        r = np.cross(f, up)
        r = r / np.linalg.norm(r)
        u = np.cross(r, f)
        m = np.eye(4)
        m[0, :3] = r
        m[1, :3] = u
        m[2, :3] = -f
        m[3, :3] = -np.array([np.dot(r, eye), np.dot(u, eye), -np.dot(f, eye)])
        return m.T

# ---------- ГЛАВНЫЙ ЦИКЛ ----------
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
    pygame.display.set_caption('MyCraft')
    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)

    ctx = mgl.create_context()
    world = World(ctx)
    player = Player()

    # Загружаем начальные чанки
    for dx in range(-VIEW_DIST, VIEW_DIST + 1):
        for dz in range(-VIEW_DIST, VIEW_DIST + 1):
            if math.sqrt(dx*dx + dz*dz) <= VIEW_DIST:
                world.build_chunk(dx, dz)

    clock = pygame.time.Clock()
    running = True
    keys = {'w': False, 'a': False, 's': False, 'd': False, 'space': False}

    projection = np.array([
        [1.0 / math.tan(math.radians(70)/2), 0, 0, 0],
        [0, 1.0 / math.tan(math.radians(70)/2), 0, 0],
        [0, 0, -2.0, -1.0],
        [0, 0, -0.1, 0]
    ], dtype='f4')

    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_w:
                    keys['w'] = True
                elif event.key == pygame.K_a:
                    keys['a'] = True
                elif event.key == pygame.K_s:
                    keys['s'] = True
                elif event.key == pygame.K_d:
                    keys['d'] = True
                elif event.key == pygame.K_SPACE:
                    keys['space'] = True
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_w:
                    keys['w'] = False
                elif event.key == pygame.K_a:
                    keys['a'] = False
                elif event.key == pygame.K_s:
                    keys['s'] = False
                elif event.key == pygame.K_d:
                    keys['d'] = False
                elif event.key == pygame.K_SPACE:
                    keys['space'] = False
            elif event.type == pygame.MOUSEMOTION:
                dx, dy = event.rel
                player.yaw -= dx * MOUSE_SENS
                player.pitch -= dy * MOUSE_SENS
                player.pitch = max(-math.pi/2 + 0.01, min(math.pi/2 - 0.01, player.pitch))
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # ЛКМ - разрушить
                    pass  # пока не реализовано
                elif event.button == 3:  # ПКМ - поставить
                    pass

        # Обновление игрока
        player.update(dt, keys, world)

        # Обновление чанков (подгрузка новых)
        cx = int(math.floor(player.position[0] / CHUNK_SIZE))
        cz = int(math.floor(player.position[2] / CHUNK_SIZE))
        needed = set()
        for dx in range(-VIEW_DIST, VIEW_DIST + 1):
            for dz in range(-VIEW_DIST, VIEW_DIST + 1):
                if math.sqrt(dx*dx + dz*dz) <= VIEW_DIST:
                    nx, nz = cx + dx, cz + dz
                    needed.add((nx, nz))
                    if (nx, nz) not in world.chunks and (nx, nz) not in world.loading:
                        world.loading.add((nx, nz))
                        world.build_chunk(nx, nz)
                        world.loading.remove((nx, nz))
        # Выгрузка
        for key in list(world.chunks.keys()):
            if key not in needed:
                world.unload_chunk(key[0], key[1])

        # Рендеринг
        ctx.clear(0.53, 0.75, 0.92, 1.0)
        view = player.get_view_matrix()
        world.render(projection, view)
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()
