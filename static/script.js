import * as THREE from 'three';
import { OrbitControls } from 'https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js';

// ---------- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ----------
let scene, camera, renderer, controls;
let world = {}; // { 'cx_cz': { blocks: [...] } }
let chunkMeshes = {}; // { 'cx_cz': THREE.Group }
let loadedChunks = new Set();
let currentChunkX = 0, currentChunkZ = 0;
let viewDistance = 4; // чанков в радиусе
let selectedBlock = 'grass';
let isMobile = false;
let raycaster, pointer;
let canPlace = false;

// ---------- ИНИЦИАЛИЗАЦИЯ ----------
function initGame() {
    document.getElementById('menu').style.display = 'none';
    document.getElementById('game').style.display = 'block';

    // Проверка на мобильное устройство
    if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
        isMobile = true;
    }

    // Сцена
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x87CEEB);

    // Камера (от первого лица)
    camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.1, 200);
    camera.position.set(8, 12, 8);

    // Рендер
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    document.getElementById('game').appendChild(renderer.domElement);

    // Управление (OrbitControls — для простоты, но можно заменить на свои)
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.screenSpacePanning = true;
    controls.maxPolarAngle = Math.PI / 2.2;
    controls.minDistance = 2;
    controls.maxDistance = 30;
    controls.target.set(0, 6, 0);

    // Освещение
    const ambient = new THREE.AmbientLight(0x404060);
    scene.add(ambient);
    const sun = new THREE.DirectionalLight(0xffeedd, 1.2);
    sun.position.set(40, 60, 30);
    sun.castShadow = true;
    sun.shadow.mapSize.width = 1024;
    sun.shadow.mapSize.height = 1024;
    sun.shadow.camera.near = 0.5;
    sun.shadow.camera.far = 150;
    sun.shadow.camera.left = -80;
    sun.shadow.camera.right = 80;
    sun.shadow.camera.top = 80;
    sun.shadow.camera.bottom = -80;
    scene.add(sun);
    const hemi = new THREE.HemisphereLight(0x87CEEB, 0x3a3a3a, 0.5);
    scene.add(hemi);

    // Рейкастер для выбора блоков
    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();

    // Загружаем начальные чанки вокруг игрока
    updateChunks();

    // Навешиваем события
    window.addEventListener('resize', onResize);
    renderer.domElement.addEventListener('click', onPointerDown);
    renderer.domElement.addEventListener('contextmenu', onRightClick);
    if (isMobile) {
        // Добавляем сенсорные кнопки (можно реализовать позже)
        setupMobileControls();
    }

    // Выбор блока
    document.querySelectorAll('.blockOption').forEach(el => {
        el.addEventListener('click', () => {
            document.querySelectorAll('.blockOption').forEach(e => e.classList.remove('active'));
            el.classList.add('active');
            selectedBlock = el.dataset.block;
        });
    });

    // Статус
    updateStatus();

    // Запуск анимации
    animate();
}

// ---------- ЗАГРУЗКА И ОТРИСОВКА ЧАНКОВ ----------
async function loadChunk(cx, cz) {
    const key = `${cx}_${cz}`;
    if (loadedChunks.has(key)) return;
    try {
        const resp = await fetch(`/api/chunk/${cx}/${cz}`);
        if (!resp.ok) throw new Error('Network error');
        const data = await resp.json();
        loadedChunks.add(key);
        buildChunk(data);
        world[key] = data;
        updateStatus();
    } catch (e) {
        console.warn('Ошибка загрузки чанка', e);
    }
}

function buildChunk(data) {
    const cx = data.x, cz = data.z;
    const key = `${cx}_${cz}`;
    const blocks = data.blocks;
    const group = new THREE.Group();
    const size = 16;

    // Материалы по типу блока
    const materials = {
        grass: new THREE.MeshLambertMaterial({ color: 0x7cb342 }),
        dirt: new THREE.MeshLambertMaterial({ color: 0x8d6e63 }),
        stone: new THREE.MeshLambertMaterial({ color: 0x9e9e9e }),
        wood: new THREE.MeshLambertMaterial({ color: 0x8d6e63 }),
        leaves: new THREE.MeshLambertMaterial({ color: 0x4caf50 })
    };

    const geometry = new THREE.BoxGeometry(0.98, 0.98, 0.98);

    blocks.forEach(b => {
        const mat = materials[b.type] || materials.dirt;
        const mesh = new THREE.Mesh(geometry, mat);
        mesh.position.set(
            cx * size + b.x + 0.5,
            b.y + 0.5,
            cz * size + b.z + 0.5
        );
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        // Сохраняем координаты для идентификации
        mesh.userData = { chunkX: cx, chunkZ: cz, bx: b.x, by: b.y, bz: b.z };
        group.add(mesh);
    });

    scene.add(group);
    chunkMeshes[key] = group;
}

function unloadChunk(cx, cz) {
    const key = `${cx}_${cz}`;
    if (chunkMeshes[key]) {
        scene.remove(chunkMeshes[key]);
        delete chunkMeshes[key];
        loadedChunks.delete(key);
        delete world[key];
    }
}

function updateChunks() {
    // Определяем, какой чанк сейчас загружен (по позиции камеры)
    const pos = controls.target;
    const cx = Math.floor(pos.x / 16);
    const cz = Math.floor(pos.z / 16);

    // Загружаем чанки в радиусе viewDistance
    const needed = new Set();
    for (let dx = -viewDistance; dx <= viewDistance; dx++) {
        for (let dz = -viewDistance; dz <= viewDistance; dz++) {
            const dist = Math.sqrt(dx*dx + dz*dz);
            if (dist <= viewDistance) {
                const nx = cx + dx;
                const nz = cz + dz;
                needed.add(`${nx}_${nz}`);
                loadChunk(nx, nz);
            }
        }
    }
    // Выгружаем лишние
    for (const key of loadedChunks) {
        if (!needed.has(key)) {
            const [cxStr, czStr] = key.split('_');
            unloadChunk(parseInt(cxStr), parseInt(czStr));
        }
    }
}

// ---------- ОБРАБОТЧИКИ СОБЫТИЙ ----------
function onPointerDown(event) {
    // Левый клик — разрушить блок
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const intersects = raycaster.intersectObjects(scene.children, true);
    if (intersects.length > 0) {
        const hit = intersects[0].object;
        if (hit.userData && hit.userData.bx !== undefined) {
            const { chunkX, chunkZ, bx, by, bz } = hit.userData;
            // Удаляем блок (отправляем запрос на сервер)
            setBlock(chunkX, chunkZ, bx, by, bz, 'air');
        }
    }
}

function onRightClick(event) {
    event.preventDefault();
    // Правый клик — поставить выбранный блок
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const intersects = raycaster.intersectObjects(scene.children, true);
    if (intersects.length > 0) {
        const hit = intersects[0].object;
        if (hit.userData && hit.userData.bx !== undefined) {
            // Определяем соседний блок (по нормали)
            const normal = intersects[0].face.normal;
            const { chunkX, chunkZ, bx, by, bz } = hit.userData;
            const newX = bx + Math.round(normal.x);
            const newY = by + Math.round(normal.y);
            const newZ = bz + Math.round(normal.z);
            // Проверяем, что координаты внутри чанка
            if (newX >= 0 && newX < 16 && newY >= 0 && newZ >= 0 && newZ < 16) {
                setBlock(chunkX, chunkZ, newX, newY, newZ, selectedBlock);
            }
        }
    }
}

async function setBlock(cx, cz, bx, by, bz, type) {
    try {
        const resp = await fetch('/api/setblock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chunk_x: cx, chunk_z: cz, block_x: bx, block_y: by, block_z: bz, type })
        });
        if (resp.ok) {
            // Перезагружаем чанк
            unloadChunk(cx, cz);
            loadedChunks.delete(`${cx}_${cz}`);
            loadChunk(cx, cz);
        }
    } catch (e) {
        console.warn('Ошибка установки блока', e);
    }
}

// ---------- МОБИЛЬНОЕ УПРАВЛЕНИЕ (джойстик) ----------
function setupMobileControls() {
    // Простейший джойстик — можно добавить позже, но для простоты оставлю управление OrbitControls
    // OrbitControls уже поддерживает тач-жесты (вращение, масштабирование)
    // Для движения можно добавить кнопки, но сейчас это не реализовано.
    console.log('Мобильное управление активно');
}

// ---------- ОБНОВЛЕНИЕ СТАТУСА ----------
function updateStatus() {
    document.getElementById('status').textContent = `Чанков: ${loadedChunks.size}`;
}

// ---------- АНИМАЦИЯ ----------
function animate() {
    requestAnimationFrame(animate);
    controls.update();

    // Обновляем чанки, если игрок переместился в другой чанк
    const pos = controls.target;
    const cx = Math.floor(pos.x / 16);
    const cz = Math.floor(pos.z / 16);
    if (cx !== currentChunkX || cz !== currentChunkZ) {
        currentChunkX = cx;
        currentChunkZ = cz;
        updateChunks();
    }

    renderer.render(scene, camera);
}

// ---------- ПОВОРОТ ЭКРАНА ----------
function onResize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
}

// ---------- ЗАПУСК ----------
document.getElementById('startBtn').addEventListener('click', initGame);
document.getElementById('loadBtn').addEventListener('click', () => {
    // Пока просто загружаем мир, как новый
    initGame();
});

// Для отладки
console.log('MyCraft загружен!');
