# gsmo
Commonsense Git, Docker, and Jupyter integrations.

- mount local Git clones into purpose-built Docker containers
- easily configure dependencies, set useful default Git configs, and mirror host user/group so that Git commits in container transparently exist on the host
- run scripts [non-interactively](#non-interactive), automatically Git-commit updated files
- run "remotely" against Git repositories, pushing changes upstream for static, serverless workflows
- easily boot a [Jupyter server](#jupyter-server) or [Bash shell](#bash-shell) from a clone and its corresponding Docker image, for interactive work.

See [`gsmo.yml`] for configuration options

## Usage

### Run notebooks non-interactively <a id="non-interactive"></a>
`gsmo` helps run notebooks and scripts in a reproducible fashion (inside Docker containers), and pass-through changes (Git commits) to the host machine:

Running:
```bash
gsmo run
```
in a project directory will:
- load configs ([`gsmo.yml`])
- build a Docker image
- run a container from that image
- run the project's `run.ipynb` notebook inside that container
- Git-commit results  

### Run interactively <a id="interactive"></a>

#### Jupyter Server <a id="jupyter-server"></a>
Build a Docker image from the current directory, configured by [`gsmo.yml`], and launch a Jupyter server with the current directory mounted (and various Git- and OS-level configs set, so that changes/commits transparently pass through to the host machine):
```bash
gsmo jupyter  # or: gsmo j
```
- runs at a "random" but stable port (derived from a hash of the module name)
- easily configure Python/Linux environment using [`gsmo.yml`]

#### Bash shell <a id="bash-shell"></a>
Build a Docker image from the current directory, configured by [`gsmo.yml`], and launch a Bash shell with it mounted (and various Git- and OS-level configs set, so that changes/commits transparently pass through to the host machine):
```bash
gsmo sh
```

## Module configuration: 

### `gsmo.yml` <a id="gsmo-yml"></a>
When you run `gsmo` in a directory, it will look for a `gsmo.yml` file in the current directory with any of the following fields and build a corresponding Docker image:

#### General configs
(see `gsmo -h` for full/authoritative list):

- `name` (`str`; default: project directory's basename): module name; also used as repository for built Docker image
- `pip` (`str` or `List[str]`): `pip` libraries to install
- `apt` (`str` or `List[str]`): `apt` libraries to install
- `env` (`str` or `List[str]`): environment variables to set
- `env_file` (`str`): file with environment variables
- `group` (`str` or `List[str]`): OS groups to add to the user inside the container
  - paths are accepted, in which case the group that owns that path will be used
- `tag` (`str` or `List[str]`): additional Docker tags within `name` repository
- `mount` (`str` or `List[str]`): Docker mounts, in several convenient formats:
  - `<path>`: equivalent to `<path>:/<path>`; easily pass local project subdirectories into Docker container, e.g. `home/.bashrc`, `etc/pip.conf`, etc.
  - standard Docker `<src>:<dst>` syntax is also supported
  - in all cases, `~` and env vars are expanded 
- `image` (`str`; default: `runsascoded/gsmo:<gsmo version>`): base Docker image to build from; `<gsmo version>` will be the pip version of `gsmo` that was installed
- `root` (`bool`; default `False`)
  - when set, run as `root` inside container
  - by default, host-machine uid+gid are used
- `dst` (`str`: default `/src`): path inside container to mount current directory to  

#### `gsmo run` configs
These configs are passed into the Docker container / pertain to the running of a script or notebook inside the container (see [non-interactive mode](#non-interactive)):
- `run` (`str`; default: `run.ipynb`): notebook to run
- `dir` (`str`; default: current directory): resolve paths (incl. mounts) relative to this directory
- `yaml` (`str` or `List[str]`): YAML string(s) with configuration settings for the module being run
- `yaml_path` (`str` or `List[str]`): YAML file(s) with configuration settings for the module being run
- `commit` (`str` or `List[str]`; default: `out` config dir): paths to Git commit after a run (in non-interactive mode)
- `out` (`str`; default `nbs`): directory to write executed notebooks to

```bash
gsmo run -h
```
```
usage: gsmo [input] run [-h] [-b BRANCH] [--clone] [--commit COMMIT] [-C DIR] [-o OUT] [--push PUSH] [-x RUN] [-y YAML] [-Y YAML_PATH]

optional arguments:
  -h, --help            show this help message and exit
  -b BRANCH, --branch BRANCH
                        Branch to clone, work in, and push results back to. Can also be passed as a trailing '@<branch>' slug on directory path or remote Git
                        repo URL. For local repositories, implies --clone
  --clone               Clone local directory into a temporary dir for duration of the run
  --commit COMMIT       Paths to `git add` and commit after running
  -C DIR, --dir DIR     Resolve paths (incl. mounts) relative to this directory (default: current directory)
  -o OUT, --out OUT     Path or directory to write output notebook to (relative to `--dir` directory; default: "nbs")
  --push PUSH           Push to this remote spec when done running
  -x RUN, --run RUN, --execute RUN
                        Notebook to run (default: run.ipynb)
  -y YAML, --yaml YAML  YAML string(s) with configuration settings for the module being run
  -Y YAML_PATH, --yaml-path YAML_PATH
                        YAML file(s) with configuration settings for the module being run
```

#### `gsmo jupyter` configs
```bash
gsmo jupyter -h
```
```
usage: gsmo [input] jupyter [-h] [-d] [-D] [-O] [-s] [--dir DIR]

optional arguments:
  -h, --help       show this help message and exit
  -d, --detach     When booting into Jupyter server mode, detach the container
  -D, --no-docker  Run in the current shell instead of in Docker
  -O, --no-open    Skip opening Jupyter notebook server in browser
  -s, --shell      Open a /bin/bash shell in the container (instead of running a jupyter server)
  --dir DIR        Root dir for jupyter notebook server (default: --dst / `/src`
```

### `Dockerfile`
When building the Docker image (in any of the above modes), if a `Dockerfile` is present in the repository, it will be built and used as the base image (and any `gsmo.yml` configs applied on top of it).

[`gsmo.yml`]: #gsmo-yml
