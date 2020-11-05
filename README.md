# gsmo
Commonsense Jupyter/Docker/Git integrations.

`gsmo` streamlines mounting and working with Git repositories in Docker containers.

A purpose-built Docker image+container are created (see [`gsmo.yml`] for configuration options), and Git configs are embedded so that commits inside the Docker container exist outside it (with correct permissions, authorship info, etc.).

Local notebooks or scripts can be executed [non-interactively](#non-interactive) (with results automatically committed to Git), or a [Jupyter server](#jupyter-server) or [Bash shell](#bash-shell) can be booted for interactive work.

## Usage

### `gsmo run`: execute notebooks non-interactively <a id="non-interactive"></a>
`gsmo` helps run notebooks and scripts in a reproducible fashion (inside Docker containers), and pass-through changes (especially Git commits) to the host machine:

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

### Interactive <a id="interactive"></a>

#### Jupyter Server <a id="jupyter-server"></a>
Build a Docker image from the current directory, and launch a Jupyter server with the current directory mounted (and various Git- and OS-level configs set, so that changes/commits are reflected on the host machine):
```bash
gsmo jupyter  # or: gsmo j
```
- runs at a "random" but stable port (derived from a hash of the module name)
- easily configure Python/Linux environment using [`gsmo.yml`]

#### Bash shell <a id="bash-shell"></a>
Build a Docker image from the current directory, and launch a Bash shell with it mounted (and various Git- and OS-level configs set, so that changes/commits are reflected on the host machine):
```bash
gsmo sh
```

## Module configuration: 

### `gsmo.yml` <a id="gsmo-yml"></a>
When you run `gsmo` in a directory, it will look for a `gsmo.yml` file in the current directory with any of the following fields and build a corresponding Docker image:

#### Docker configs
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

#### `gsmo jupyter` configs

### `Dockerfile`
When building the Docker image (in any of the above modes), if a `Dockerfile` is present in the repository, it will be built and used as the base image (and any `gsmo.yml` configs applied on top of it).

[`gsmo.yml`]: #gsmo-yml
