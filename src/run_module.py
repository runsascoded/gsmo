
from argparse import ArgumentParser
from shutil import copy
from subprocess import check_call, CalledProcessError

from cd import cd
from conf import *
from git import success


def run_module(name, dir):
    dir = Path(dir).absolute().resolve()
    with cd(dir):

        if not success('git', 'config', '--global', 'user.name'):
            global_git_config_template = Path('/.gitconfig')
            global_git_config_path = Path.home() / '.gitconfig'
            copy(str(global_git_config_template), str(global_git_config_path))
            if not success('git', 'config', '--global', 'user.name') or \
               not success('git', 'config', '--global', 'user.email'):
                with global_git_config_template.open('r') as f:
                    config_str = f.read()
                raise Exception("Failed to set user.name / user.email global git configs via %s or %s:\n%s" % (
                    global_git_config_template,
                    global_git_config_path,
                    config_str
                ))

        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        run_notebook_path = dir / ('%s.ipynb' % RUN_SCRIPT_NAME)
        run_script_path = dir / ('%s.sh' % RUN_SCRIPT_NAME)
        run_notebook = run_notebook_path.exists()
        run_shell_script = run_script_path.exists()

        exception = None
        with OUT_PATH.open('w') as out, ERR_PATH.open('w') as err:
            if run_notebook and run_shell_script:
                raise Exception('Found both %s and %s' % (run_notebook_path, run_script_path))
            elif run_notebook:
                from papermill import execute_notebook, PapermillExecutionError
                print('Executing notebook %s in-place' % run_notebook_path)
                try:
                    execute_notebook(
                        str(run_notebook_path),
                        str(run_notebook_path),
                        progress_bar=False,
                        stdout_file=out,
                        stderr_file=err,
                        kernel_name=JUPYTER_KERNEL_NAME,
                    )
                except PapermillExecutionError as e:
                    if e.evalue.startswith(EARLY_EXIT_EXCEPTION_MSG_PREFIX):
                        print('Run notebook %s exited with "OK" msg' % run_notebook_path)
                    else:
                        exception = e
            elif run_shell_script:
                cmd = [ str(run_script_path) ]
                print('Running: %s' % run_script_path)
                try:
                    check_call(cmd, stdout=out, stderr=err)
                except CalledProcessError as e:
                    exception = e
            else:
                raise Exception('No runner script found at %s or %s' % (run_notebook_path, run_script_path))

            if exception:
                with open(FAILURE_PATH, 'w') as f:
                    f.write('1\n')
                err.write(str(exception))
            else:
                Path(SUCCESS_PATH).touch()

    print('Module finished: %s' % name)


if __name__ == '__main__':
    parser = ArgumentParser()
    add_argument = parser.add_argument
    add_argument('dir', nargs='?', default=None, help='Local directory to clone into and work in')
    add_argument('-n', '--name', help='Module name')
    args = parser.parse_args()
    run_module(
        args.name,
        args.dir,
    )
