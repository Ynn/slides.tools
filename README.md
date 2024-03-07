# Slides.tools

## Overview

The Project streamlines the creation and distribution of presentations by encapsulating Slidev and its dependencies into a standalone Docker image. This Python-built application facilitates building a Docker image for Slidev presentations, along with functionalities for running and exporting slides. It alleviates the hassle of manual dependency management and ensures a consistent presentation environment across different systems.

This implementation was crafted to fulfill a personal requirement. It may not be the best fit for all Docker use cases, especially for those prioritizing a cutting-edge environment. For a more traditional Docker approach to managing Slidev presentations, the tangramor/slidev_docker project on GitHub offers a cleaner, more standardized solution.

## Prerequisites

- Docker installed on your system
- Python 3.x (for building the executable)

## Getting Started

### Setting Up Your Environment

First, clone the repository and set up a Python virtual environment:

```shell
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

### Building the Slidev Docker Image

Generate the Docker image containing Slidev and all necessary tools:

```shell
python slidev.py -b # builds the docker image
```

### Creating an Executable

Create a standalone executable for your operating system:

```shell
python slidev.py --makebin # generates the binary
```

Locate the generated executable within the `dist` directory. Add it to your system's PATH for easy access.

### Testing Your Setup

Run a test presentation to verify the installation:

```shell
dist/slidev test/slides.md
```

## Usage

The `slidev` command provides a simplified interface for common Slidev operations, differing from the standard Slidev CLI.

### Running a Presentation

Serve a presentation locally on port 3030:

```shell
slidev -r <path_to_your_file>/myfile.md
```

### Exporting Presentations

#### To PDF

```shell
slidev -e <path_to_your_file>/myfile.md
```

For additional PDF options, including table of contents and compression:

```shell
slidev -e <path_to_your_file>/myfile.md --with-toc -c --compress
```

#### As a Single Page Application (SPA)

```shell
slidev -s <path_to_your_file>/myfile.md
```

## Dockerfile Configuration

The Dockerfile includes:

- Slidev and a selection of themes
- Playwright for PDF exports
- Ghostscript for PDF compression

You can customize the Dockerfile as needed. Remember to update the `VERSION` constant in `slidev.py` to reflect changes in the Docker image. The `VERSION` format is `{SCRIPT_VERSION}-{SLIDEV_VERSION}`, serving as the Docker image tag.

## Command Reference

- `-v`, `--version`: Display the script version.
- `-b`, `--build`: Build the Docker image.
- `-r`, `--run`: Serve the specified Markdown file.
- `-e`, `--export`: Export to PDF.
- `-c`, `--with-clicks`: Include click-triggered pages in exports.
- `-t`, `--timeout`: Specify a timeout for exports.
- `-s`, `--spa`: Export as a Single Page Application.
- `--with-toc`: Include a table of contents in exports.
- `--makebin`: Create a standalone executable.
- `--compress`: Apply PDF compression.

## Maintenance and Updates

Please note, there are no plans to keep this project routinely updated with the latest versions of Slidev. It was developed to address a specific need at a particular point in time. As such, the project might not reflect the most recent advancements in Slidev or related technologies. Should you require an up-to-date version or wish to contribute to its development, you are encouraged to fork this project and implement any necessary updates or improvements.

## Future Enhancements

- Implement rootless execution to improve security.
