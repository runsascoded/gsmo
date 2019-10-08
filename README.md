# cron
Runner for simple directory-based "modules", suitable for crontab, that tracks runs in git

It's not necessarily a good idea to use this instead of e.g. Docker containers; the main thing it provides is a particular way of storing/tracking runs (and changes between runs) in `git`. It's also much lighter-weight than Docker (though more brittle as a result).

## "Modules"
A "module" is a git repository containing a `run.sh` script that is designed to be run regularly / on an interval (e.g. in a user's `crontab`).

### Example 
Demonstrate single runs of the [test/echo_module](test/echo_module) example modules:

```bash
python run_modules.py test/echo_module
```

This will:
- clone the module `test/echo_module` into a temporary directory
- run its `run.sh` in that directory, capturing stdout and stderr
- `git commit` the state of the directory after `run.sh` completes
- apply that `commit` to the `runs/` directory in the original module path (`test/echo_module`)
  - this directory is an additional clone of the containing module repo, used for storing the output of runs of that module
  - each run's status and logs are appended to a branch that hangs off of the commit in the outer module repo that the run was run from
  - for example, here's an example state of the `runs/` directory in the `test/echo_module` module:
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
