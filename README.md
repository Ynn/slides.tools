# Slides.tools

## Overview

The Project streamlines the creation and distribution of presentations by encapsulating Slidev and its dependencies into a standalone Docker image. This Python-built application facilitates building a Docker image for Slidev presentations, along with functionalities for running and exporting slides. It alleviates the hassle of manual dependency management and ensures a consistent presentation environment across different systems.

This implementation was crafted to fulfill a personal requirement. It may not be the best fit for all Docker use cases, especially for those prioritizing a cutting-edge environment. For a more traditional Docker approach to managing Slidev presentations, the tangramor/slidev_docker project on GitHub offers a cleaner, more standardized solution.

## Prerequisites

- Docker installed on your system
- Go installed on your system

## Getting Started

### Building

### Building the Slidev Docker Image

Generate the Docker image containing Slidev and all necessary tools.


Build and compress the docker image (optionnal, only if you want to embed the image). You can change the dependencies in package.json and Dockerfile if needed (also change the version number) :

```shell
go run . build_docker -c
```

This create an archive in `./image` folder

Build the executable :

```shell
go build
```

The docker image is embed if is contained in `./image` folder

Test with :

```shell
.\slidev-dkr.exe run .\test\slides.md
```

## Usage

The `slidev-dkr` command provides a simplified interface for common Slidev operations, differing from the standard Slidev CLI.

### Running a Presentation

Serve a presentation locally on port 3030:

```shell
slidev-dkr run <path_to_your_file>/myfile.md
```

### Exporting Presentations

#### To PDF

```shell
slidev export <path_to_your_file>/myfile.md
```

Flags:
+ -g, --compress         Compress the pdf with ghostscript
+ --timeout string   timeout for the export (default "60000")
+ -c, --with-clicks      Export pages for every clicks
+ -t, --with-toc         Export pages with outline



For additional PDF options, including table of contents and compression:

```shell
slidev export <path_to_your_file>/myfile.md -gct
```



#### As a Single Page Application (SPA)

```shell
slidev-dkr spa <path_to_your_file>/myfile.md
# or
slidev-dkr build <path_to_your_file>/myfile.md
```

Flags:
+ -b, --base string   To deploy your slides under sub-routes, you will need to pass the --base option. The --base path must begin and end with a slash / (default "/")
+ -d, --download      Provide Downloadable PDF
+ -h, --help          help for spa

## Dockerfile Configuration

The Dockerfile includes:

- Slidev and a selection of themes
- Playwright for PDF exports
- Ghostscript for PDF compression

You can customize the Dockerfile and the package.json as needed. Remember to update the `version` constant in `package.sjon` to reflect changes in the Docker image.

## Référence

```shell
Slidev in a container

Usage:
  slidev-dkr [command]

Available Commands:
  build_docker    Build the docker image
  completion      Generate the autocompletion script for the specified shell
  compress_docker Compress the image and store it in image/slidev.tar.xst to be embedded in the binary when building     
  export          Export the slidev presentation to a pdf
  help            Help about any command
  run             Run slidev on the current file
  spa             Export the slidev presentation to a Single Page Application
  version         Current version of the script and slidev

Flags:
  -h, --help   help for slidev-dkr
```


## Maintenance and Updates

Please note, there are no plans to keep this project routinely updated with the latest versions of Slidev. It was developed to address a specific need at a particular point in time. As such, the project might not reflect the most recent advancements in Slidev or related technologies. Should you require an up-to-date version or wish to contribute to its development, you are encouraged to fork this project and implement any necessary updates or improvements.

