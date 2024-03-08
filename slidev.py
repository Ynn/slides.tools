import docker
from docker import DockerClient
from docker.models.images import Image
import logging
import sys
import os 
import lzma
import time
import subprocess
import argparse
import os

VERSION = "1-0.48.0-beta.24"
IMAGE_NAME = "nnynn/slidev"
TAGGED_IMAGE_NAME = f"nnynn/slidev:{VERSION}"
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
    build_image(base_path(), TAGGED_IMAGE_NAME)
    client:DockerClient = docker.from_env()
    image:Image = client.images.get(TAGGED_IMAGE_NAME)
    image_xz_path = "slidev.tar.xz"

    print("Compressing the image...")
    # Utiliser lzma pour compresser directement le flux de données en .xz
    with lzma.open(image_xz_path, 'wb', preset=6) as lzma_file:
        for chunk in image.save(named=True):
            lzma_file.write(chunk)

    print(f"Image has been successfully compressed {image_xz_path}")

def load_image(client: DockerClient):
    print(f"Loading container image {TAGGED_IMAGE_NAME}...")
    try :
        return client.images.get(TAGGED_IMAGE_NAME)
    except docker.errors.ImageNotFound:
        print("Image not found, loading it from file, will take at least 30s ...")
        start = time.time()
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

def slidev_run(filename, args) :
    dirname,filename = get_dirname_filename(filename)
    command = ["npx","slidev", "slides/"+filename, "--remote"]
    slidev(dirname, command)

def slidev_export(filename, args) :
    dirname,filename = get_dirname_filename(filename)
    command = ["npx","slidev", "export", "slides/"+filename, "--format", "pdf", "--output", f"slides/{os.path.splitext(filename)[0]}.pdf"]
    if args.with_clicks :
        command.append("--with-clicks")
    if args.with_toc :
        command.append("--with-toc")
    if args.timeout :
        command.append("--timeout")
        command.append(args.timeout)
    slidev(dirname, command)
    if args.compress :
        command = ["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4", "-dPDFSETTINGS=/printer", "-dNOPAUSE", "-dQUIET", "-dBATCH", "-sOutputFile=slides/"+os.path.splitext(filename)[0]+"-compressed.pdf", "slides/"+os.path.splitext(filename)[0]+".pdf"]
        slidev(dirname,command)

def slidev_spa(filename, args) :
    dirname,filename = get_dirname_filename(filename)
    command = ["npx","slidev", "build", "slides/"+filename]
    if args.with_clicks :
        command.append("--with-clicks")
    if args.with_toc :
        command.append("--with-toc")
    slidev(dirname, command)


def main() :
    parser = argparse.ArgumentParser(description="Build and optionally run a Docker image")
    parser.add_argument("-v", "--version", action="store_true", help="Show version of the script")
    parser.add_argument("-b", "--build", action="store_true", help="Build the Docker image")
    parser.add_argument("-r", "--run", help="File to compile")
    parser.add_argument("-e", "--export", help="Export the file to pdf")
    parser.add_argument("-c", "--with-clicks",action="store_true", help="Export pages for every clicks")
    parser.add_argument("-t", "--timeout", help="timeout for the export")
    parser.add_argument("-s", "--spa", help="Export the file to single web application")
    parser.add_argument("--with-toc",action="store_true", help="Export pages with outline ")
    parser.add_argument("--makebin", action="store_true", help="Make a binary of this docker script and image")
    parser.add_argument("--compress", action="store_true", help="Compress the pdf with ghostscript")

    args = parser.parse_args()

    docker_context_path = base_path()
    tag = IMAGE_NAME

    if args.version:
        print(f"script version :{VERSION.split('-')[0]} slidev version : {VERSION.split('-')[1]}")
        sys.exit(0)

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
        slidev_run(args.run, args)
        sys.exit(0)
    if args.export :
        slidev_export(args.export, args)
        sys.exit(0)
    if args.spa :
        slidev_spa(args.spa, args)
        sys.exit(0)
if __name__ == "__main__":
    main()