import argparse
import docker
import logging
import lzma
import os
import shutil
import subprocess
import sys
import time
from docker import DockerClient
from docker.models.containers import Container
from docker.models.images import Image
from typing import List

VERSION = "1-0.48.0-beta.26"
IMAGE_NAME = "nnynn/slidev"
TAGGED_IMAGE_NAME = f"nnynn/slidev:{VERSION}"
IMAGE_FILENAME = "slidev"

def base_path() -> str:
    """
    Returns the base path of the application.

    If the application is running as a bundled executable, it returns the path of the executable.
    Otherwise, it returns the current working directory.

    Returns:
        str: The base path of the application.
    """
    try:
        base_path: str = getattr(sys, '_MEIPASS', os.getcwd())
    except Exception:
        base_path = os.path.abspath(".")
    return base_path

def build_image(docker_context_path: str, tag: str) -> Image:
    """
    Build a Docker image from the Dockerfile located in the specified docker_context_path.

    Args:
        docker_context_path (str): The path to the directory containing the Dockerfile.
        tag (str): The tag to assign to the built image.

    Returns:
        docker.models.images.Image: The built Docker image.

    Raises:
        docker.errors.BuildError: If the build fails.
        docker.errors.APIError: If there is an error communicating with the Docker daemon.

    """
    print("Building the image from the Dockerfile...")
    with open(base_path() + "/Dockerfile", "r") as f:   
        print(f.read())
    client: DockerClient = docker.from_env()
    image, build_logs = client.images.build(path=docker_context_path, tag=tag)
    for log in build_logs:
        print(log)
    return image

def build_and_store_image() -> None:
    """
    Builds the Docker image, compresses it using lzma, and stores it as an .xz file.

    Returns:
        None
    """
    build_image(base_path(), TAGGED_IMAGE_NAME)
    client: DockerClient = docker.from_env()
    image: Image = client.images.get(TAGGED_IMAGE_NAME)
    image_xz_path: str = "slidev.tar.xz"

    print("Compressing the image...")
    # Use lzma to build an .xz (this is terribly slow, but it works cross-platform. Reduces the image size by 70% 2Gb -> 550Mb)
    # This can be done with an external tool like 7zip
    with lzma.open(image_xz_path, 'wb', preset=6) as lzma_file:
        for chunk in image.save(named=True):
            lzma_file.write(chunk)

    print(f"Image has been successfully compressed {image_xz_path}")

def load_image(client: DockerClient) -> Image:
    """
    Load a container image from Docker or from a file.

    Args:
        client (DockerClient): The Docker client to use for loading the image.

    Returns:
        Image: The loaded container image.
    """
    print(f"Loading container image {TAGGED_IMAGE_NAME}...")
    try:
        return client.images.get(TAGGED_IMAGE_NAME)
    except docker.errors.ImageNotFound:
        print("Image not found, loading it from file, will take at least 30s ...")

        start = time.time()
        with open(f"{base_path()}/{IMAGE_FILENAME}.tar.xz", "rb") as f:
            images = client.images.load(f.read())

        stop = time.time()
        print("Image loaded in ", stop - start, " seconds")

        for image in images:
            print(image.tags)
            return image
        
    except docker.errors.APIError as e:
        print("Error loading image", e)
        print("Is docker running ?")
        sys.exit(1)


def attach(container_id: str) -> None:
    """
    Attach to a container specified by the container ID.

    Args:
        container_id (str): The ID of the container to attach to.

    Returns:
        None
    """
    command: List[str]
    if shutil.which('podman'):
        command = ['podman', 'attach', container_id]
    else:
        command = ['docker', 'attach', container_id]
    process: subprocess.Popen = subprocess.Popen(command, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    process.wait()

def remove_container(container_name: str) -> None:
    """
    Removes a Docker container with the given name.

    Args:
        container_name (str): The name of the container to be removed.

    Returns:
        None
    """
    client: DockerClient = docker.from_env()
    try:
        container: Container = client.containers.get(container_name)
        container.remove()
    except docker.errors.NotFound:
        pass
    except docker.errors.APIError as e:
        pass

def slidev(dirname: str, command: List[str]) -> None:
    """
    Run slidev container with the specified command.

    Args:
        dirname (str): The directory name containing the slides.
        command (List[str]): The command to be executed inside the container.

    Returns:
        None
    """
    print("Running slidev...")
    client: DockerClient = docker.from_env()
    image: Image = load_image(client=client)

    try:

        package_json_path:str = os.path.join(dirname, "package.json")
        create_package_json:bool = False
        if not os.path.isfile(package_json_path):
            print("Creating package.json...")
            with open(package_json_path, "w") as f:
                f.write('{ "name": "slides", "version": "0.0.0" }')
            print("temporary package.json created.")
            create_package_json=True


        print("Running container...")
        remove_container("slidev-container")
        container: Container = client.containers.run(
            image=image,
            stdin_open=True,
            stdout=True,
            stderr=True,
            tty=True,
            name="slidev-container",
            ports={'3030/tcp': 3030},
            environment={"CHOKIDAR_USEPOLLING": "true"},
            volumes={dirname: {'bind': '/slidev/slides', 'mode': 'rw'}},
            command=command,
            remove=True,
            detach=True
        )
        attach(container.id)
        print("Exiting : please note that the docker image will not be removed, remove it manually with docker rmi nnynn/slidev if space is an issue.")
        if create_package_json:
            os.remove(os.path.join(dirname, "package.json"))
            print("remove temporary package.json")
        
    finally:
        remove_container("slidev-container")

def get_dirname_filename(filename):
    """
    Get the directory name and filename from the given file path.

    Args:
        filename (str): The path to the file.

    Returns:
        tuple: A tuple containing the directory name and the filename.

    Raises:
        SystemExit: If the file does not exist or if it is not a .md file.
    """
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

def slidev_bash(filename: str, args: List[str]) -> None:
    """
    Open a bash in the slidev container with the specified file mounted.

    Args:
        filename (str): The name of the file.
        args (List[str]): The arguments to pass to the slidev command.

    Returns:
        None
    """
    dirname, filename = get_dirname_filename(filename)
    command = ["bash"]
    slidev(dirname, command)

def slidev_run(filename: str, args: List[str]) -> None:
    """
    Run the slidev container with the specified file and enable remote.

    Args:
        filename (str): The name of the file.
        args (List[str]): The arguments to pass to the slidev command.

    Returns:
        None
    """
    dirname, filename = get_dirname_filename(filename)
    command = ["npx", "slidev", filename, "--remote"]
    slidev(dirname, command)

def slidev_export(filename: str, args) -> None:
    """
    Export the Slidev presentation to PDF format.

    Args:
        filename (str): The name of the Slidev presentation file.
        args: Additional arguments for the export process.

    Returns:
        None
    """
    dirname, filename = get_dirname_filename(filename)
    command = ["npx", "slidev", "export", filename, "--format", "pdf", "--output", f"{os.path.splitext(filename)[0]}.pdf"]
    if args.with_clicks:
        command.append("--with-clicks")
    if args.with_toc:
        command.append("--with-toc")
    if args.timeout:
        command.append("--timeout")
        command.append(args.timeout)
    slidev(dirname, command)
    if args.compress:
        command = ["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4", "-dPDFSETTINGS=/printer", "-dNOPAUSE", "-dQUIET", "-dBATCH", "-sOutputFile="+os.path.splitext(filename)[0]+"-compressed.pdf", os.path.splitext(filename)[0]+".pdf"]
        slidev(dirname, command)

def slidev_spa(filename: str, args) -> None:
    """
    Build the Slidev presentation as a single web application.

    Args:
        filename (str): The name of the Slidev presentation file.
        args: Additional arguments for the build process.

    Returns:
        None
    """
    dirname, filename = get_dirname_filename(filename)
    command = ["npx", "slidev", "build", filename]
    if args.with_clicks:
        command.append("--with-clicks")
    if args.with_toc:
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
    parser.add_argument("--bash", help="Open a bash with file mounted")

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

    if args.bash :
        slidev_bash(args.bash, args)
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