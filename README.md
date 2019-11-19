# gismo
Directory-based "module" system that tracks module-runs in Git.

## "Modules"
A *module* is a Git repository containing a `run.sh` script (or `run.ipynb` notebook) that is designed to be run regularly / on an interval (e.g. in a user's `crontab`), or as part of pipelines of *modules*.

### Running modules
This library runs a module by:
- git-cloning it into a temporary directory
- mounting that directory into a Docker container (which can be customized by the module)
- running the module's "run script" (`run.ipynb` or `run.sh`) there (and recording stdout/stderr in the `logs/` directory)
- git-committing the post-run state of this temporary module clone (i.e. any changes to the module's files, as well as the `logs/` dir)
- merging that commit upstream to a dedicated "runs" clone of the module (typically placed under `runs/` in the module itself, and left untracked by the module's git repository)
- optionally merging changes to specific files into the module's git repository itself, so that subsequent runs will build off of those changes 

### Configuring modules
A `config.yaml` allows for configuring how the module is run, state is tracked across runs, etc.

Notable fields:
- `name` (required): name of the module (also used in `user.name` and `user.email` git configs)
- `state`: path (or list of paths) to merge upstream after each run (if any changes to them have occurred), for use in subsequent runs
- `docker`: configs for the Docker container that the module is run in:
    - `as_user`: run the Docker container as the current user
    - `add_groups`: group(s) to additionally make the Docker-container user be a member of
    - `pip`: `pip` packages to install
    - `apt`: `apt` packages to install
    - `mount`/`mounts`: directories to mount into the docker container
        - relative paths allowed (will be resolved before passing to Docker)
        - `<src>` will be mapped to `<src>:<basename <src>>`, for convenience
        - by default, the module is mounted under `/src`, and this module is under `/gismo`

## Examples

### stateless `run.sh`
[The `echo` module](example/echo) simply prints timestamped test messages to stdout and stderr.

To run it (from this repo's root):

```bash
./run.py example/echo
```

The first time you runs this, a `runs/` subdirectory will be created under `example/echo`; `runs/` is itself a full clone of `example/echo`, but gets a commit for each run of the module:

[![git graph output showing a "success" commit on the "runs" branch](https://p199.p4.n0.cdn.getcloudapp.com/items/nOuW16mK/Screen+Shot+2019-11-04+at+9.04.01+AM.png?v=b7a880e17055821f3073be25781575d6)](https://gist.github.com/ryan-williams/79d5833e6fedba060ba5a385cc4e511f)

*(pretty formatting courtesy of [`git graph`](https://github.com/ryan-williams/git-helpers/blob/f45ab500ba3b0f195aca92e74716927a54d61931/graph/git-graph))*

Inspecting the commit:

```bash
pushd example/echo/runs
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

Running the module two more times adds further commits to the `runs` branch (in the `runs/` sub-clone of `example/echo`):

```bash
popd  # return to the root of this module
./run.py example/echo
./run.py example/echo
```
[![git graph output, showing 2 more successful runs after the first](https://p199.p4.n0.cdn.getcloudapp.com/items/7Kuxj4wO/Screen+Shot+2019-11-04+at+9.18.37+AM.png?v=790c8d5cd361abc92d75fc449b9698df)](https://gist.github.com/ryan-williams/8dcf3e4bec61d28d51d5336bb85d1200)

The two new commits reflect changes in the stdout/stderr across runs (due to the runs' differing timestamps):

[![git commit log -p output, showing two recent commits with updated timestamps in stdout/stderr](https://p199.p4.n0.cdn.getcloudapp.com/items/E0uPRGm8/Screen+Shot+2019-11-04+at+9.15.37+AM.png?v=75931988fce7449faa8968a2159a52f5)](https://gist.github.com/ryan-williams/42dfe6825d460705dea29e062722e491)

#### Merging upstream source changes, existing runs

Having run this module 3x, suppose we change its source to print the date before the other output:

```bash
pushd example/echo
cat <<EOF >run.sh
#!/usr/bin/env bash
echo "\$(date +"%Y-%m-%d %H:%M:%S"): test stdout; yay!"
echo "\$(date +"%Y-%m-%d %H:%M:%S"): test stderr; 🤷" >&2
EOF
git commit -am "clean up output msgs"
popd
```

Running it again:
```bash
./run.py example/echo
```

…we see a new "successful run" commit in the `runs/` dir, with two parents: the previous run, and the upstream source change:

[![git commit graph showing new commit descending from previous run and new source](https://gist.githubusercontent.com/ryan-williams/1dedfdf50c0f7e9455225ba71742795c/raw/e10fe3825d0fbbd197d3b1c0e2b9a132c23a89a2/00.png)](https://gist.github.com/ryan-williams/1dedfdf50c0f7e9455225ba71742795c)

The new commits contents reflect the expected output changes (and the new source that caused them) when diffed against the previous run:

[![git diff showing log output with date preceding message](https://gist.githubusercontent.com/ryan-williams/2eb2c44d600c3f2aa9d822b55a1c5b2a/raw/fca0f4f8aafe8b6d9a639b8866606759f0131e3f/00.png)](https://gist.github.com/ryan-williams/2eb2c44d600c3f2aa9d822b55a1c5b2a)

And it reflects the presence of the `logs/` directory and `SUCCESS` file when diffed against its upstream source parent:

[![git diff showing addition of logs dir and SUCCESS msg](https://gist.githubusercontent.com/ryan-williams/ecaf30b390bf9a9d39849b193befb9b6/raw/5d5df8577cf84b8b0922d5c055b820247f2ebc30/00.png)](https://gist.github.com/ryan-williams/ecaf30b390bf9a9d39849b193befb9b6)

### stateful, Jupyter-notebook-based module
[The `hailstone` module](example/hailstone) demonstrates propagating state between runs as well as defining a module in a [Jupyter](https://jupyter.org/) notebook.

[Its `run.ipynb` notebook](./example/hailstone/run.ipynb) documents itself, and is worth a read.

Running it from the root of this repo:

```bash
./run.py example/hailstone
```

We see not only a "run" commit under `example/hailstone/runs/`:

[![git graph showing initial commit and child "run" commit](https://gist.githubusercontent.com/ryan-williams/124eb0a11eb67affaf9ff88b8c1a4775/raw/aafb7c7982974aa7a546aa13a60110f81619f4c6/00.png)](https://gist.github.com/ryan-williams/124eb0a11eb67affaf9ff88b8c1a4775)

but also a merge of that "run" into the containing module, `example/hailstone`:

[![graph showing initial commit, run commit, and "update state" merge of both](https://gist.githubusercontent.com/ryan-williams/14c5d01b240e3520ab6757883d6fa620/raw/14cdfb9251b3580fec9ad6e41c83d1262544ad7d/00.png)](https://gist.github.com/ryan-williams/14c5d01b240e3520ab6757883d6fa620)

Running several more times:

```bash
for _ in `seq 8`; do
    ./run.py example/hailstone
done
```

We see a series of "run" commits (with custom messages describing updates to the "value" state), and a merge into the containing repo of each change:

[![git graph history showing 8 iterations fo the hailstone sequence starting from 6](https://gist.githubusercontent.com/ryan-williams/6ce4d3ac317c0a8b4fdd90485a0771a9/raw/ac87afd2dacffcee0db9c763ae344983b9c9800a/00.png)](https://gist.github.com/ryan-williams/6ce4d3ac317c0a8b4fdd90485a0771a9)

Note that there are only 8 hailstone iterations represented, though we've triggered 9 runs. In the `runs/` directory, we can see a generic successful "run" commit after the run that brought `value` to `1`:

[![git graph showing the last 2 hailstone iterations + merge commits, and one successful run after that with no merge](https://gist.githubusercontent.com/ryan-williams/ce2f6cc361eba187e55d702b3a568e6f/raw/bf3505784b74b3c40d1085d4bcc537ba7ad7dd87/00.png)](https://gist.github.com/ryan-williams/ce2f6cc361eba187e55d702b3a568e6f) 

We can inspect the `run.ipynb` notebook from that most recent commit, and see that it detected that the value was already `1`, and raised an `Exception` beginning with `OK: `, which tells the runner machinery that it exited early but successfully:

![Screenshot of cells 2 and 3 of example/hailstone/run.ipynb Jupyter notebook, showing a thrown Exception and early termination of the notebook](https://p199.p4.n0.cdn.getcloudapp.com/items/JruwZ0KX/Screen+Shot+2019-11-12+at+9.44.56+PM.png?v=beed774d346ee753fd237baf9f3a0940)
