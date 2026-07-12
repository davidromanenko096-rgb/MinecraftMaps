const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87CEEB);

const camera = new THREE.PerspectiveCamera(
    75,
    window.innerWidth / window.innerHeight,
    0.1,
    1000
);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// Свет
const light = new THREE.DirectionalLight(0xffffff, 1);
light.position.set(20, 40, 20);
scene.add(light);

scene.add(new THREE.AmbientLight(0xffffff, 0.5));

// Земля
const block = new THREE.BoxGeometry(1, 1, 1);
const grass = new THREE.MeshLambertMaterial({ color: 0x55aa55 });

for (let x = -20; x <= 20; x++) {
    for (let z = -20; z <= 20; z++) {
        const cube = new THREE.Mesh(block, grass);
        cube.position.set(x, -1, z);
        scene.add(cube);
    }
}

// Камера
camera.position.set(0, 2, 5);

// Управление
const keys = {};

document.addEventListener("keydown", e => keys[e.key.toLowerCase()] = true);
document.addEventListener("keyup", e => keys[e.key.toLowerCase()] = false);

function animate() {
    requestAnimationFrame(animate);

    const speed = 0.1;

    if (keys["w"]) camera.position.z -= speed;
    if (keys["s"]) camera.position.z += speed;
    if (keys["a"]) camera.position.x -= speed;
    if (keys["d"]) camera.position.x += speed;

    renderer.render(scene, camera);
}

animate();

window.addEventListener("resize", () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});
