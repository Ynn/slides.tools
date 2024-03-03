import docker
import logging
import sys
import os 
import lzma
import time
import subprocess
import argparse

IMAGE_NAME = "nnynn/slidev"
IMAGE_FILENAME = "slidev"

def base_path():
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return base_path

def build_image(docker_context_path, tag):
    print("Building the image from the Dockerfile...")
    with open(base_path() + "/Dockerfile", "r") as f:   
        print(f.read())
    client = docker.from_env()
    image, build_logs = client.images.build(path=docker_context_path, tag=tag)
    for log in build_logs:
        print(log)
    return image

def build_and_store_image():
    build_image(base_path(), "nnynn/slidev")
    client = docker.from_env()
    image = client.images.get("nnynn/slidev")
    image_xz_path = "slidev.tar.xz"

    print("Compressing the image...")
    # Utiliser lzma pour compresser directement le flux de données en .xz
    with lzma.open(image_xz_path, 'wb', preset=lzma.PRESET_EXTREME) as lzma_file:
        for chunk in image.save(named=True):
            lzma_file.write(chunk)

    print(f"L'image Docker a été compressée avec succès en {image_xz_path}")


          
def load_image(client):
    start = time.time()
    print("Loading container image...")
    with open(f"{base_path()}/{IMAGE_FILENAME}.tar.xz", "rb") as f:
        images = client.images.load(f.read())    
    stop = time.time()
    print("Image loaded in ", stop-start, " seconds")
    
    for image in images:
        print(image.tags)
        return image

def attach(container_id):
    command = ['docker', 'attach', container_id]
    process = subprocess.Popen(command, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    process.wait()

def remove_container(container_name):
    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        container.remove()
    except docker.errors.NotFound:
        pass
    except docker.errors.APIError as e:
        pass

def slidev(dirname, command) :
    print("Running slidev...")
    client = docker.from_env()
    image = load_image(client=client)

    try :
        print("Running container...")
        remove_container("slidev-container")
        container = client.containers.run(image = image, 
			                    stdin_open = True,
                                stdout=True,
                                stderr=True,
                                tty=True, 
                                name="slidev-container",
                                ports={'3030/tcp': 3030},
                                environment = {"CHOKIDAR_USEPOLLING":"true"},
                                volumes={dirname:{'bind': '/slidev/slides', 'mode': 'rw'}},
                                command=command,
                                remove=True,
                                detach=True)
        attach(container.id)   
    
    finally :
        remove_container("slidev-container")

def get_dirname_filename(filename):
    if not os.path.isfile(filename):
        print(f"File {filename} does not exist")
        sys.exit(1) 
    if not filename.endswith(".md"):
        print(f"File {filename} is not a .md file")
        sys.exit(1)
            
    dirname = os.path.dirname(os.path.abspath(filename))
    filename = os.path.basename(filename)
    print(f"Running on {filename} in {dirname}")
    return (dirname, filename)

def slidev_run(filename) :
    dirname,filename = get_dirname_filename(filename)
    command = ["npx","slidev", "slides/"+filename, "--remote"]
    slidev(dirname, command)

def slidev_export(filename) :
    dirname,filename = get_dirname_filename(filename)
    command = ["npx","slidev", "export", "slides/"+filename, "--format", "pdf", "--output", f"slides/{os.path.splitext(filename)[0]}"]
    slidev(dirname, command)

def slidev_spa(filename) :
    dirname,filename = get_dirname_filename(filename)
    command = ["npx","slidev", "build", "slides/"+filename]
    slidev(dirname, command)


def main() :
    parser = argparse.ArgumentParser(description="Build and optionally run a Docker image")
    parser.add_argument("-b", "--build", action="store_true", help="Build the Docker image")
    parser.add_argument("-r", "--run", help="File to compile")
    parser.add_argument("-e", "--export", help="Export the file to pdf")
    parser.add_argument("-s", "--spa", help="Export the file to pdf")
    parser.add_argument("--makebin", action="store_true", help="Make a binary of this docker script")
    
    args = parser.parse_args()

    docker_context_path = base_path()
    tag = IMAGE_NAME

    if args.build:
        build_and_store_image()
        sys.exit(0)

    if not os.path.isfile(base_path()+"/slidev.tar.xz"):
        print("You must run build with -b before running makebin")
        sys.exit(1)

    if args.makebin:
        import PyInstaller.__main__
        PyInstaller.__main__.run([
            os.getcwd() + "/"+sys.argv[0],
            '--onefile',
            '--add-data', 'Dockerfile:.',
            '--add-data', f'{IMAGE_FILENAME}.tar.xz:.'
        ])
        sys.exit(0)
        
    if args.run :
        slidev_run(args.run)
        sys.exit(0)
    if args.export :
        slidev_export(args.export)
        sys.exit(0)
    if args.spa :
        slidev_spa(args.spa)
        sys.exit(0)
if __name__ == "__main__":
    main()


        

  