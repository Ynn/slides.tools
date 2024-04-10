package main

import (
	"bytes"
	"context"
	"embed"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"strings"
	"time"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/archive"
	"github.com/docker/go-connections/nat"
	"github.com/klauspost/compress/zstd"
	"github.com/spf13/cobra"
)

const (
	ImageFilename = "slidev"
	ContainerName = "slidev-container"
	ImageName     = "nnynn/slidev"
)

var (
	Version         = readVersion()
	TaggedImageName = fmt.Sprintf("%s:%s", ImageName, Version)
	rootCmd         = &cobra.Command{
		Use:   "slidev-dkr",
		Short: "Slidev in a container",
	}
)

//go:embed package.json Dockerfile
var embeddedFiles embed.FS

//go:embed image/*
var slidevImage embed.FS

func readVersion() string {
	file, err := embeddedFiles.Open("package.json")
	if err != nil {
		log.Fatal(err)
	}
	defer file.Close()

	byteValue, _ := io.ReadAll(file)
	var packageJSON map[string]interface{}
	json.Unmarshal([]byte(byteValue), &packageJSON)

	version := packageJSON["version"].(string)
	slidevCliVersion := packageJSON["dependencies"].(map[string]interface{})["@slidev/cli"].(string)
	return version + "-" + slidevCliVersion
}

func compress(cli *client.Client, imageName string, outputPath string) {
	fmt.Println("Compressing the image...")
	ctx := context.Background()

	fmt.Println("Save the image to a tar...")
	// Save the image to a tar
	rc, err := cli.ImageSave(ctx, []string{imageName})
	if err != nil {
		log.Fatal(err)
	}
	defer rc.Close()

	// Open a file for writing
	file, err := os.Create(outputPath)
	if err != nil {
		log.Fatal(err)
	}
	defer file.Close()

	fmt.Println("Create a new zstd writer ...")

	// Create a new zstd writer
	w, err := zstd.NewWriter(file, zstd.WithEncoderLevel(zstd.SpeedBestCompression))
	if err != nil {
		log.Fatal(err)
	}

	// Copy the image tar to the zstd writer
	if _, err := io.Copy(w, rc); err != nil {
		log.Fatal(err)
	}

	// Close the zstd writer
	if err := w.Close(); err != nil {
		log.Fatal(err)
	}

	fmt.Println("Image has been successfully compressed", outputPath)
}

func buildImage(cli *client.Client) {
	fmt.Println("Building the image from the Dockerfile...")

	ctx := context.Background()

	dockerfilePath, err := os.Getwd()
	if err != nil {
		log.Fatal(err)
	}
	dockerfilePath = filepath.ToSlash(filepath.Join(dockerfilePath, "Dockerfile"))

	dockerfile, err := os.ReadFile(dockerfilePath)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println(string(dockerfile))

	buildContext, err := os.Getwd()
	if err != nil {
		log.Fatal(err)
	}

	fmt.Println("Creating context archive...")
	tar, err := archive.TarWithOptions(buildContext, &archive.TarOptions{})
	if err != nil {
		log.Fatal(err)
	}

	buildOptions := types.ImageBuildOptions{
		Tags:       []string{TaggedImageName},
		Dockerfile: "Dockerfile",
	}

	fmt.Println("Building the image...")
	response, err := cli.ImageBuild(ctx, tar, buildOptions)
	if err != nil {
		log.Fatal(err)
	}
	defer response.Body.Close()

	fmt.Println("Reading the response...")
	output, err := io.ReadAll(response.Body)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println(string(output))
}

func imageEmbedded() bool {
	file, err := slidevImage.Open("image/slidev.tar.zst")
	if err != nil {
		return false
	}
	defer file.Close()
	return true
}

func loadImage(cli *client.Client) (string, error) {
	fmt.Printf("Loading container image %s...\n", TaggedImageName)

	images, err := cli.ImageList(context.Background(), image.ListOptions{})
	if err != nil {
		return "", err
	}

	for _, image := range images {
		for _, tag := range image.RepoTags {
			if tag == TaggedImageName {
				return tag, nil
			}
		}
	}

	if imageEmbedded() {
		fmt.Println("Image not found, loading it from file, will take at least 30s ...")
		start := time.Now()

		imageData, err := slidevImage.ReadFile("image/slidev.tar.zst")
		if err != nil {
			return "", err
		}

		loadResponse, err := cli.ImageLoad(context.Background(), bytes.NewReader(imageData), false)
		if err != nil {
			return "", err
		}
		defer loadResponse.Body.Close()

		body, err := io.ReadAll(loadResponse.Body)
		fmt.Println(string(body))
		if err != nil {
			return "", err
		}

		stop := time.Now()
		fmt.Printf("Image loaded in %v seconds\n", stop.Sub(start).Seconds())

		return TaggedImageName, nil
	} else {
		fmt.Printf("Image %s not found locally. Attempting to pull from registry...\n", TaggedImageName)

		out, err := cli.ImagePull(context.Background(), TaggedImageName, image.PullOptions{})
		if err != nil {
			return "", err
		}
		defer out.Close()
		io.Copy(io.Discard, out)
		fmt.Println("Image pulled successfully from registry.")
		return TaggedImageName, nil
	}
}

func attach(containerID string) error {
	var command []string
	if _, err := exec.LookPath("podman"); err == nil {
		command = []string{"podman", "attach", containerID}
	} else {
		command = []string{"docker", "attach", containerID}
	}

	cmd := exec.Command(command[0], command[1:]...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return err
	}

	return nil
}

func removeContainer(cli *client.Client) {
	fmt.Printf("Removing the container %s \n", ContainerName)
	containers, err := cli.ContainerList(context.Background(), container.ListOptions{All: true})
	if err != nil {
		log.Fatal(err)
	}

	for _, cont := range containers {
		if cont.Names[0] == "/"+ContainerName {
			err := cli.ContainerRemove(context.Background(), cont.ID, container.RemoveOptions{Force: true})
			if err != nil {
				log.Fatal(err)
			}
			break
		}
	}
}

func createFileIfNeeded(path, content string) bool {
	if _, err := os.Stat(path); os.IsNotExist(err) {
		file, err := os.Create(path)
		if err != nil {
			log.Fatal(err)
		}
		defer file.Close()

		_, err = file.WriteString(content)
		if err != nil {
			log.Fatal(err)
			return false
		}
		return true
	} else {
		return false
	}
}

func removeFileIfNeeded(path string) {
	fmt.Printf("Remove temporary %s \n", path)
	if err := os.Remove(path); err != nil {
		fmt.Printf("Error removing temporary %s: %v\n", path, err)
	}
}

func slidev(cli *client.Client, dirname string, command []string) error {

	imageName, err := loadImage(cli)
	if err != nil {
		log.Fatal(err)
	}

	defer removeContainer(cli)

	packageJsonPath := filepath.Join(dirname, "package.json")
	if createFileIfNeeded(packageJsonPath, `{ "name": "slides", "version": "0.0.0" }`) {
		fmt.Println("Temporary package.json created.")
		defer removeFileIfNeeded(packageJsonPath)
	}

	viteConfigPath := filepath.Join(dirname, "vite.config.js")
	if createFileIfNeeded(viteConfigPath, `export default { server: { fs: { strict: false } } }`) {
		fmt.Println("Temporary vite.config.js created.")
		defer removeFileIfNeeded(viteConfigPath)
	}

	removeContainer(cli)

	fmt.Printf("Creating the container %s \n", ContainerName)
	fmt.Println("Command:", command)

	ctx := context.Background()

	cont, err := cli.ContainerCreate(ctx, &container.Config{
		Image:        imageName,
		AttachStderr: true,
		AttachStdin:  true,
		Tty:          true,
		AttachStdout: true,
		OpenStdin:    true,
		Env:          []string{"CHOKIDAR_USEPOLLING=true"},
		Cmd:          command,
		ExposedPorts: nat.PortSet{
			"3030/tcp": struct{}{},
		},
	}, &container.HostConfig{
		Binds: []string{fmt.Sprintf("%s:/slidev/slides:rw", dirname)},
		PortBindings: nat.PortMap{
			"3030/tcp": []nat.PortBinding{
				{
					HostIP:   "0.0.0.0",
					HostPort: "3030",
				},
			},
		},
	}, nil, nil, ContainerName)

	if err != nil {
		return err
	}

	if err := cli.ContainerStart(ctx, cont.ID, container.StartOptions{}); err != nil {
		return err
	}

	attach(cont.ID)
	//cli.ContainerWait(ctx, cont.ID)

	fmt.Println("Exiting: please note that the docker image will not be removed, remove it manually with docker rmi nnynn/slidev if space is an issue.")
	return nil
}

func ExpandTilde(path string) (string, error) {
	if !strings.HasPrefix(path, "~") {
		return path, nil
	}

	usr, err := user.Current()
	if err != nil {
		return "", err
	}

	return filepath.Join(usr.HomeDir, path[1:]), nil
}

func getDirnameFilename(filename string) (string, string) {
	filename, _ = ExpandTilde(filename)
	if !fileExists(filename) {
		fmt.Printf("File %s does not exist\n", filename)
		os.Exit(1)
	}
	if !strings.HasSuffix(filename, ".md") {
		fmt.Printf("File %s is not a .md file\n", filename)
		os.Exit(1)
	}

	dirname, _ := filepath.Abs(filepath.Dir(filename))
	filename = filepath.Base(filename)

	fmt.Printf("Running on %s in %s\n", filename, dirname)
	return dirname, filename
}

func fileExists(filename string) bool {
	info, err := os.Stat(filename)
	if os.IsNotExist(err) {
		return false
	}
	return !info.IsDir()
}

func run(cli *client.Client, filename string) error {
	dirname, filename := getDirnameFilename(filename)
	fmt.Println("Running slidev in the container...")
	return slidev(cli, dirname, []string{"npx", "slidev", filename, "--remote"})
}

func slidevExport(cli *client.Client, filename string, withClicks, withToc bool, timeout string, compress bool) error {
	dirname, filename := getDirnameFilename(filename)
	command := []string{"npx", "slidev", "export", filename, "--format", "pdf", "--output", strings.TrimSuffix(filename, filepath.Ext(filename)) + ".pdf"}
	if withClicks {
		command = append(command, "--with-clicks")
	}
	if withToc {
		command = append(command, "--with-toc")
	}
	if timeout != "" {
		command = append(command, "--timeout", timeout)
	}
	err := slidev(cli, dirname, command)
	if err != nil {
		return err
	}
	if compress {
		command = []string{"gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4", "-dPDFSETTINGS=/printer", "-dNOPAUSE", "-dQUIET", "-dBATCH", "-sOutputFile=" + strings.TrimSuffix(filename, filepath.Ext(filename)) + "-compressed.pdf", strings.TrimSuffix(filename, filepath.Ext(filename)) + ".pdf"}
		err = slidev(cli, dirname, command)
		if err != nil {
			return err
		}
	}
	return nil
}

func slidevSpa(cli *client.Client, filename string, base string, download bool) error {
	dirname, filename := getDirnameFilename(filename)
	command := []string{"npx", "slidev", "build", filename}
	if download {
		command = append(command, "--with-toc")
		command = append(command, "--with-toc")
		command = append(command, "--download")
	}

	if base != "/" {
		command = append(command, "--base", base)
	}

	return slidev(cli, dirname, command)
}

func main() {
	cli, err := client.NewClientWithOpts(client.WithVersion("1.43"))
	if err != nil {
		log.Fatal(err)
	}

	var cmdRun = &cobra.Command{
		Use:   "run [md file]",
		Short: "Run slidev on the current file",
		Args:  cobra.ExactArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			filename := args[0]
			err := run(cli, filename)
			if err != nil {
				log.Fatal(err)
			}
			os.Exit(0)
		},
	}

	var cmdBuild = &cobra.Command{
		Use:   "build_docker",
		Short: "Build the docker image",
		Run: func(cmd *cobra.Command, args []string) {
			compression, _ := cmd.Flags().GetBool("compress")
			buildImage(cli)
			if compression {
				compress(cli, TaggedImageName, "image/slidev.tar.zst")
			}
			os.Exit(0)
		},
	}

	cmdBuild.Flags().BoolP("compress", "c", false, "Compress the image after building and store it in image/slidev.tar.zst to be embedded in the binary when building")

	var cmdCompress = &cobra.Command{
		Use:   "compress_docker",
		Short: "Compress the image and store it in image/slidev.tar.xst to be embedded in the binary when building",
		Run: func(cmd *cobra.Command, args []string) {
			compress(cli, TaggedImageName, "image/slidev.tar.zst")
			os.Exit(0)
		},
	}

	var cmdVersion = &cobra.Command{
		Use:   "version",
		Short: "Current version of the script and slidev",
		Run: func(cmd *cobra.Command, args []string) {
			dockerFlag, _ := cmd.Flags().GetBool("docker")
			scriptFlag, _ := cmd.Flags().GetBool("script")
			slidevFlag, _ := cmd.Flags().GetBool("slidev")

			if dockerFlag {
				fmt.Printf(TaggedImageName)
				os.Exit(0)
			}

			versionParts := strings.Split(Version, "-")

			if scriptFlag {
				fmt.Printf(versionParts[0])
				os.Exit(0)
			}

			if slidevFlag {
				fmt.Printf(versionParts[1])
				os.Exit(0)
			}

			fmt.Printf("script version: %s slidev version: %s\n", versionParts[0], versionParts[1])
			fmt.Printf("Docker image : %s\n", TaggedImageName)
			os.Exit(0)
		},
	}
	cmdVersion.Flags().BoolP("scripts", "", false, "Show the script version")
	cmdVersion.Flags().BoolP("docker", "", false, "Show the docker image version")
	cmdVersion.Flags().BoolP("slidev", "", false, "Show the slidev version")

	var cmdExport = &cobra.Command{
		Use:   "export [md file]",
		Short: "Export the slidev presentation to a pdf",
		Run: func(cmd *cobra.Command, args []string) {
			filename := args[0]
			withClicksFlag, _ := cmd.Flags().GetBool("with-clicks")
			withTocFlag, _ := cmd.Flags().GetBool("with-toc")
			compressFlag, _ := cmd.Flags().GetBool("compress")
			timeoutFlag, _ := cmd.Flags().GetString("timeout")
			err = slidevExport(cli, filename, withClicksFlag, withTocFlag, timeoutFlag, compressFlag)
			os.Exit(0)
		},
	}

	cmdExport.Flags().BoolP("with-clicks", "c", false, "Export pages for every clicks")
	cmdExport.Flags().BoolP("with-toc", "t", false, "Export pages with outline")
	cmdExport.Flags().BoolP("compress", "g", false, "Compress the pdf with ghostscript")
	cmdExport.Flags().StringP("timeout", "", "60000", "timeout for the export")

	var cmdSPA = &cobra.Command{
		Use:     "spa [md file]",
		Aliases: []string{"build"},
		Short:   "Export the slidev presentation to a Single Page Application",
		Run: func(cmd *cobra.Command, args []string) {
			filename := args[0]
			base, _ := cmd.Flags().GetString("base")
			download, _ := cmd.Flags().GetBool("download")
			err = slidevSpa(cli, filename, base, download)
			os.Exit(0)
		},
	}
	cmdSPA.Flags().BoolP("download", "d", false, "Provide Downloadable PDF")
	cmdSPA.Flags().StringP("base", "b", "/", "To deploy your slides under sub-routes, you will need to pass the --base option. The --base path must begin and end with a slash /")

	rootCmd.AddCommand(cmdRun, cmdBuild, cmdVersion, cmdExport, cmdSPA, cmdCompress)
	rootCmd.Execute()

}
