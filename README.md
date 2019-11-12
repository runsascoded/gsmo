# cron
Runner for simple directory-based "modules", suitable for calling from crontab, that tracks runs in git.

## "Modules"
A "module" is a git repository containing a `run.sh` script that is designed to be run regularly / on an interval (e.g. in a user's `crontab`).

Running a module consists of:
 - mounting it into a Docker container (which can be customized by the module) under `/src`
 - cloning that `/src` into a temporary directory in the container
 - running the module's `run.sh` there.
 
 The state of the working tree is then committed to `git` and pushed upstream to a `runs` subdirectory of the original module, allowing all changes (and output; stdout/stderr are written to `logs/{out,err}` paths) to be viewed/tracked in the upstream git repository. 

### State
Modules can optionally specify certain paths as "state"; changes to these paths are merged upstream into the module repo itself each run, and thus are available for subsequent runs of the module.

If a file called `_STATE` is present in the top level of the module, it is interpreted as containing a list of paths that should be carried over from run to run.

## Examples

### [echo_module](test/echo_module)
This module simply `echo`s test messages and a timestamp to stdout and stderr.

To run, from this repo:

```bash
./run.sh test/echo_module
```

The first time you runs this, a `runs/` subdirectory will be created under `test/echo_module`; `runs/` is itself a full clone of `test/echo_module`, but gets a commit for each run of the module:

[![git graph output showing a "success" commit on the "runs" branch](https://p199.p4.n0.cdn.getcloudapp.com/items/nOuW16mK/Screen+Shot+2019-11-04+at+9.04.01+AM.png?v=b7a880e17055821f3073be25781575d6)](https://gist.github.com/ryan-williams/79d5833e6fedba060ba5a385cc4e511f)

*(pretty formatting courtesy of [`git graph`](https://github.com/ryan-williams/git-helpers/blob/f45ab500ba3b0f195aca92e74716927a54d61931/graph/git-graph))*

Inspecting the commit:

```bash
pushd test/echo_module/runs
git checkout runs
git show
```

[![git show output, showing a successful commit that adds logs/out, logs/err, and SUCCESS files](https://p199.p4.n0.cdn.getcloudapp.com/items/jkuyO2En/Screen+Shot+2019-11-04+at+9.10.58+AM.png?v=72733b3b3f91d7653e27d874ac410334)](https://gist.github.com/24c6470083e894a7dcd5ca2f38139df8)

The `logs/` directory contains output from the run:

```bash
cat logs/out
# yay; test stdout: Mon Nov  4 14:02:54 UTC 2019
cat logs/err
# test stderr: Mon Nov  4 14:02:54 UTC 2019
```

There is also an empty file named `SUCCESS` in the commit, denoting that the module's `run.sh` exited `0` (`FAILURE`, containing the non-zero exit-code, would be present otherwise).

Running the module two more times adds further commits to the `runs` branch (in the `runs/` sub-clone of `test/echo_module`):

```bash
popd  # return to the root of this module
./run.sh test/echo_module
./run.sh test/echo_module
```
[![git graph output, showing 2 more successful runs after the first](https://p199.p4.n0.cdn.getcloudapp.com/items/7Kuxj4wO/Screen+Shot+2019-11-04+at+9.18.37+AM.png?v=790c8d5cd361abc92d75fc449b9698df)](https://gist.github.com/ryan-williams/8dcf3e4bec61d28d51d5336bb85d1200)

The two new commits reflect changes in the stdout/stderr across runs (due to the runs' differing timestamps):

[![git commit log -p output, showing two recent commits with updated timestamps in stdout/stderr](https://p199.p4.n0.cdn.getcloudapp.com/items/E0uPRGm8/Screen+Shot+2019-11-04+at+9.15.37+AM.png?v=75931988fce7449faa8968a2159a52f5)](https://gist.github.com/ryan-williams/42dfe6825d460705dea29e062722e491)

Suppose we make a change to the module's source, to print the date before the other output:

```bash
cat <<EOF >test/echo_module/run.sh
#!/usr/bin/env bash
echo "\$(date +"%Y-%m-%d %H:%M:%S"): test stdout; yay!"
echo "\$(date +"%Y-%m-%d %H:%M:%S"): test stderr; 🤷" >&2
EOF
git --git-dir=test/echo_module/.git commit -am "clean up output msgs"
```

If you navigate to `test/echo_module/runs` directory

Each run will create a commit in a `runs/` subdirectory of the `test/echo_module` module; here's an example state of the `runs/` directory after a few runs:
This will:
- build and run the `cron:latest` docker image ([defined in this repo](./Dockerfile)), with `test/echo_module` mounted as `/src`
- the Docker entrypoint is [`run_module.py`](./src/run_module.py), which:
  - clones the module (at `/src`) into a temporary directory (inside the container)
  - runs the module's `run.sh` in that directory, directing stdout and stderr to `logs/{out/err}`
  - `git commit`s the state of that directory after `run.sh` completes, picking up any changes to the module's files, output in the `logs/` dir, and paths explicitly labeled as `_STATE` (in this case, only the `logs` dir will have relevant new content)
  - pushes that new commit to a `runs` branch in a `runs/` subdirectory of the module source repo
    - this sub-repo is created if it doesn't already exist
    - it is not a `git submodule` or subtree of the outer repo, but just an untracked directory there
 
Here's an example state of the `runs/` directory in the `test/echo_module` module, after a few runs:
    ```bash
    git log --graph --decorate --color --oneline `git branch --list 'runs-*' | cut -c 3-`
    ```
    ```
    * a35df7e (HEAD -> runs-305982f) 2019-10-08T21:27:24: success
    * c533949 2019-10-08T21:26:58: success
    * 6d62b7c 2019-10-08T21:26:55: success
    * 01a6a99 2019-10-08T21:16:00: success
    * 80885e0 2019-10-08T21:15:23: success
    * 305982f link readme
    | * 967ba43 (runs-d297f09) 2019-10-08T21:14:08: success
    | * 299c54b 2019-10-08T20:37:00: success
    |/
    * d297f09 (upstream/master, upstream/HEAD, master) chmod
    * 1882888 add simple run.sh
    * 4791a4b Initial commit
    ```
    Note the two runs hanging off of commit `d297f09` (with the `runs-d297f09` branch pointing to the most recent one), and 5 more recent runs on branch `runs-305982f`.
    ![colorized screenshot of the preformatted git-graph block above](https://cl.ly/a07305701715/Screen%20Shot%202019-10-08%20at%205.57.28%20PM.png)
