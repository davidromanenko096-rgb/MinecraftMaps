import json
import math
import random
import os
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder='static')
WORLD_DIR = 'world_data'
os.makedirs(WORLD_DIR, exist_ok=True)

# ------------------- Шум Перлина (простая реализация) -------------------
class PerlinNoise:
    def __init__(self, seed=0):
        self.p = [i for i in range(256)]
        random.seed(seed)
        random.shuffle(self.p)
        self.p += self.p

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
        a = self.p[xi] + yi
        b = self.p[xi + 1] + yi
        return self.lerp(
            self.lerp(self.grad(self.p[a], xf, yf), self.grad(self.p[b], xf - 1, yf), u),
            self.lerp(self.grad(self.p[a + 1], xf, yf - 1), self.grad(self.p[b + 1], xf - 1, yf - 1), u),
            v
        )

perlin = PerlinNoise(seed=42)

# ------------------- Генерация мира -------------------
CHUNK_SIZE = 16
def generate_chunk(cx, cz):
    heights = []
    for x in range(CHUNK_SIZE):
        for z in range(CHUNK_SIZE):
            wx = cx * CHUNK_SIZE + x
            wz = cz * CHUNK_SIZE + z
            # Основной ландшафт
            h = perlin.noise(wx * 0.05, wz * 0.05) * 5 + perlin.noise(wx * 0.1, wz * 0.1) * 2
            h = int(h + 5)  # смещение, чтобы были и горы, и равнины
            if h < 1: h = 1
            if h > 15: h = 15
            heights.append(h)
    return heights

def get_block_type(height, y):
    if y == height:
        return 'grass'
    elif y > height - 3:
        return 'dirt'
    else:
        return 'stone'

# ------------------- Работа с чанками (сохранение/загрузка) -------------------
def get_chunk_path(cx, cz):
    return os.path.join(WORLD_DIR, f'chunk_{cx}_{cz}.json')

def save_chunk(cx, cz, blocks):
    # blocks: список словарей {x, y, z, type}
    path = get_chunk_path(cx, cz)
    with open(path, 'w') as f:
        json.dump({'x': cx, 'z': cz, 'blocks': blocks}, f)

def load_chunk(cx, cz):
    path = get_chunk_path(cx, cz)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return None

# ------------------- API -------------------
@app.route('/api/chunk/<int:cx>/<int:cz>')
def get_chunk(cx, cz):
    # Пытаемся загрузить сохранённый чанк
    data = load_chunk(cx, cz)
    if data:
        return jsonify(data)
    # Если нет — генерируем новый
    heights = generate_chunk(cx, cz)
    blocks = []
    for x in range(CHUNK_SIZE):
        for z in range(CHUNK_SIZE):
            h = heights[x * CHUNK_SIZE + z]
            for y in range(h + 1):
                block_type = get_block_type(h, y)
                blocks.append({
                    'x': x,
                    'y': y,
                    'z': z,
                    'type': block_type
                })
    # Сохраняем
    save_chunk(cx, cz, blocks)
    return jsonify({'x': cx, 'z': cz, 'blocks': blocks})

@app.route('/api/setblock', methods=['POST'])
def set_block():
    data = request.json
    cx = data['chunk_x']
    cz = data['chunk_z']
    bx = data['block_x']   # локальные координаты внутри чанка
    by = data['block_y']
    bz = data['block_z']
    block_type = data['type']
    # Загружаем чанк
    chunk = load_chunk(cx, cz)
    if chunk is None:
        return jsonify({'error': 'chunk not found'}), 404
    blocks = chunk['blocks']
    # Ищем блок с такими координатами
    found = False
    for b in blocks:
        if b['x'] == bx and b['y'] == by and b['z'] == bz:
            if block_type == 'air':
                blocks.remove(b)
            else:
                b['type'] = block_type
            found = True
            break
    if not found and block_type != 'air':
        blocks.append({'x': bx, 'y': by, 'z': bz, 'type': block_type})
    save_chunk(cx, cz, blocks)
    return jsonify({'success': True})

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)