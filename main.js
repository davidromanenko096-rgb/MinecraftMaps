// ================================
// Minecraft Clone - Chunk World
// ================================

const CHUNK_SIZE = 16;
const WORLD_HEIGHT = 64;
const RENDER_DISTANCE = 4;


// хранилище чанков
let chunks = {};


// seed мира
let worldSeed = 12345;


// ================================
// ПРОСТОЙ NOISE ГЕНЕРАТОР
// ================================

function noise(x,z){

    let value = Math.sin(
        x * 0.05 +
        worldSeed
    )
    *
    Math.cos(
        z * 0.05 +
        worldSeed
    );


    return value;
}


// ================================
// КЛАСС CHUNK
// ================================

class Chunk {


    constructor(x,z){

        this.x=x;
        this.z=z;

        this.blocks=[];

        this.meshes=[];

        this.generate();

    }



    generate(){


        for(let x=0;x<CHUNK_SIZE;x++){

            this.blocks[x]=[];

            for(let z=0;z<CHUNK_SIZE;z++){


                let worldX =
                this.x*CHUNK_SIZE+x;

                let worldZ =
                this.z*CHUNK_SIZE+z;



                let height =
                Math.floor(
                    noise(
                        worldX,
                        worldZ
                    )*10
                    +20
                );



                this.blocks[x][z]=[];


                for(
                    let y=0;
                    y<WORLD_HEIGHT;
                    y++
                ){


                    let block=0;


                    if(y<height-3)
                        block=3; // камень

                    else if(y<height)
                        block=2; // земля

                    else if(y===height)
                        block=1; // трава



                    this.blocks[x][z][y]=block;

                }

            }

        }


    }



    buildMesh(){


        const geometry =
        new THREE.BoxGeometry(
            1,1,1
        );


        for(
            let x=0;
            x<CHUNK_SIZE;
            x++
        ){

            for(
                let z=0;
                z<CHUNK_SIZE;
                z++
            ){

                for(
                    let y=0;
                    y<WORLD_HEIGHT;
                    y++
                ){


                    let type =
                    this.blocks[x][z][y];


                    if(type===0)
                    continue;



                    let material;


                    if(type===1)
                    material =
                    blocks.grass;


                    if(type===2)
                    material =
                    blocks.dirt;


                    if(type===3)
                    material =
                    blocks.stone;



                    let cube =
                    new THREE.Mesh(
                        geometry,
                        material
                    );


                    cube.position.set(
                        this.x*CHUNK_SIZE+x,
                        y,
                        this.z*CHUNK_SIZE+z
                    );


                    scene.add(cube);

                    this.meshes.push(cube);


                }
            }
        }

    }



    unload(){


        for(let mesh of this.meshes){

            scene.remove(mesh);

        }


        this.meshes=[];

    }


}



// ================================
// CHUNK MANAGER
// ================================


function chunkKey(x,z){

    return x+"_"+z;

}



function loadChunk(x,z){


    let key =
    chunkKey(x,z);


    if(chunks[key])
    return;



    let chunk =
    new Chunk(
        x,z
    );


    chunk.buildMesh();


    chunks[key]=chunk;


}



function unloadFarChunks(px,pz){


    for(
        let key in chunks
    ){

        let c =
        chunks[key];


        let dx =
        Math.abs(
            c.x-px
        );


        let dz =
        Math.abs(
            c.z-pz
        );



        if(
            dx>RENDER_DISTANCE ||
            dz>RENDER_DISTANCE
        ){

            c.unload();

            delete chunks[key];

        }

    }


}




function updateChunks(playerX,playerZ){


    let cx =
    Math.floor(
        playerX/CHUNK_SIZE
    );


    let cz =
    Math.floor(
        playerZ/CHUNK_SIZE
    );



    for(
        let x=-RENDER_DISTANCE;
        x<=RENDER_DISTANCE;
        x++
    ){

        for(
            let z=-RENDER_DISTANCE;
            z<=RENDER_DISTANCE;
            z++
        ){


            loadChunk(
                cx+x,
                cz+z
            );


        }

    }



    unloadFarChunks(
        cx,
        cz
    );

}
