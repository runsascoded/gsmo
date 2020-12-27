from inspect import getfullargspec
import json
from jupyter_client import kernelspec
from os import getcwd, makedirs, remove
from os.path import abspath, basename, dirname, exists, join, splitext
from pathlib import Path
from re import match
from shutil import move
from sys import executable
from tempfile import NamedTemporaryFile
from traceback import format_exception
from typing import Iterable

from gsmo.git import Spec, GIT_SSH_URL_REGEX
from papermill import execute_notebook, PapermillExecutionError
from utz import b62, CalledProcessError, cd, git, line, lines, now, nullcontext, run, singleton, stderr


EARLY_EXIT_EXCEPTION_MSG_PREFIX = 'OK: '

def current_kernel():
    kernels = kernelspec.find_kernel_specs()
    kernel = singleton(
        [ 
            name
            for name, kernel_dir
            in kernels.items()
            if json.load(open(f'{kernel_dir}/kernel.json','r'))['argv'][0] == executable
        ], empty_ok=True
    )
    if kernel: return kernel
    return singleton(kernels.keys())


def execute(
    input,
    output=None,
    # Papermill execute_notebook kwargs that we may override defaults for
    nest_asyncio=True,
    cwd=False,
    inject_paths=False,
    progress_bar=False,
    # Aliases for papermill kwargs
    kernel=None,
    params=None,
    # Configs for committing run notebook + specifying output paths to include
    commit=True,
    msg=None,
    start_sha=None,
    msg_path='_MSG',
    tmp_output=True,
    push=None,
    *args,
    **kwargs
):
    '''Run a jupyter notebook using papermill, and git commit the output
    '''
    if not exists(input) and not input.endswith('.ipynb'):
        input += '.ipynb'
    if not exists(input):
        raise ValueError(f"Nonexistent input notebook: {input} (cwd: {cwd}/{getcwd()})")

    if commit:
        if not start_sha:
            start_sha = git.head.sha()
        commit_ctx = git.txn(start=start_sha)
    else:
        commit_ctx = nullcontext()

    name = splitext(input)[0]
    if output:
        if not output.endswith('.ipynb'):
            output = join(output, basename(input))
        out_dir = dirname(abspath(output))
        makedirs(out_dir, exist_ok=True)
    else:
        output = input

    # Parse execute_notebook() kwargs names
    spec = getfullargspec(execute_notebook)
    exec_kwarg_names = spec.args[-len(spec.defaults):]

    # Separate out execute_notebook kwargs
    exec_kwargs = { 
        name: kwargs.pop(name)
        for name in exec_kwarg_names
        if name in kwargs
    }

    # Merge "kernel" and "kernel_name" kwargs; default to current kernel
    if kernel:
        if 'kernel_name' in exec_kwargs:
            if exec_kwargs['kernel_name'] != kernel:
                raise ValueError(f'Conflicting kernel_name values: {exec_kwargs["kernel_name"]} vs. {kernel}')
        else:
            exec_kwargs['kernel_name'] = kernel
    else:
        if 'kernel_name' not in exec_kwargs:
            kernel_name = current_kernel()
            exec_kwargs['kernel_name'] = kernel_name

    # Support "params" and "parameters" aliases for execute_notebooks' "parameters" kwarg; pick whichever one is present here (and merge them if they both are, raising on conflicting values for the same key)
    if params is not None:
        if 'parameters' in exec_kwargs:
            parameters = exec_kwargs['parameters']
            for k,v in params.items():
                if k in parameters and parameters[k] != v:
                    raise ValueError(
                        f'Conflicting kwargs: params %s vs parameters %s' % (
                            str(v),
                            str(parameters[k])
                        )
                    )
            if exec_kwargs['kernel_name'] != kernel:
                raise ValueError(f'Conflicting kernel_name values: {exec_kwargs["kernel_name"]} vs. {kernel}')
        else:
            exec_kwargs['parameters'] = params

    parameters = exec_kwargs.get('parameters')
    if parameters:
        if kwargs:
            raise ValueError(f'Passing `parameters` arg to papermill, but found dangling kwargs: {kwargs}')
    else:
        parameters = kwargs
        exec_kwargs['parameters'] = parameters

    # Convert Path objects to strings, as a courtesy/convenience (they will fail to serialize in execute_notebook() otherwise)
    exec_kwargs['parameters'] = {
        k: str(v) if isinstance(v, Path) else v
        for k,v in exec_kwargs['parameters'].items()
    }

    # We take "cwd=True" to mean "run in the current directory" (papermill's default); our default is otherwise to run papermill from the directory containing the notebook being executed
    if cwd:
        if cwd is True:
            cwd = None
    else:
        cwd = dirname(abspath(input))

    if tmp_output:
        prefix, _ = splitext(basename(output))
        staging_output = NamedTemporaryFile(prefix=prefix, suffix='.ipynb').name
    else:
        staging_output = output

    with commit_ctx as commit_txn:
        exc = None
        success_msg = None
        try:
            execute_notebook(
                str(input),
                str(staging_output),
                *args,
                nest_asyncio=nest_asyncio,  # allow papermill-in-papermill
                cwd=cwd,
                inject_paths=inject_paths,  # normally unused, but allow notebook to reflect on its own path
                progress_bar=progress_bar,
                **exec_kwargs,
            )
        except PapermillExecutionError as e:
            print(f'Caught exception {e}, name {e.ename}, value {e.evalue}')
            # Allow notebooks to short-circuit execution by raising an Exception whose message begins with the string "OK: "
            if e.ename == 'Exception' and e.evalue.startswith(EARLY_EXIT_EXCEPTION_MSG_PREFIX):
                success_msg = e.evalue[len(EARLY_EXIT_EXCEPTION_MSG_PREFIX):]
                print('Run notebook %s exited early with "OK" msg: %s' % (str(input), success_msg))
            elif e.ename == 'OK':
                success_msg = e.evalue
                print('Run notebook %s exited early with "OK" exception, msg: %s' % (str(input), success_msg))
            else:
                exc = e
                success_msg = None
        finally:
            if tmp_output:
                print(f'moving run notebook from {staging_output} to {output}')
                move(staging_output, output)


        if commit or exc:
            if exc:
                msg = '\n'.join(
                    [
                        f'Failed: {repr(exc)}',
                        '',
                        ''.join(
                            format_exception(
                                etype=type(exc),
                                value=exc,
                                tb=exc.__traceback__,
                            )
                        ),
                    ]
                )
            # Commit results:
            # - by default, just the notebook output path
            # - pass a list of paths to "commit" (or a single path as a str or Path) to include them in the commit
            # - if a file named '_MSG' is written by the notebook, use its contents as the commit message
            if commit is True:
                commit = []
            elif isinstance(commit, str):
                commit = [commit]
            elif isinstance(commit, Path):
                commit = [str(commit)]
            commit += [output]
            if not msg:
                if exists(msg_path):
                    with open(msg_path,'r') as f:
                        msg = f.read()
                    remove(msg_path)
                elif success_msg:
                    msg = success_msg
                else:
                    msg = name

            commit_txn.msg = msg
            commit_txn.add = commit

    if commit or exc:
        if isinstance(push, str):
            pushes = [Spec(push)]
        elif isinstance(push, Iterable):
            pushes = [ Spec(spec) for spec in push ]
        else:
            pushes = []
        for push in pushes:
            if push.pull:
                remote = push.remote
                url = line('git','remote','get-url',remote)
                tmp_branch = f'tmp-{b62(now().ms)}'
                src = push.src or 'HEAD'
                if (m := match(GIT_SSH_URL_REGEX, url)):
                    host = m['host']
                    path = m['path']
                    remote_head = line('ssh',host,f'cd {path} && git symbolic-ref -q --short HEAD', err_ok=True)
                    if remote_head and push.dst and remote_head != push.dst:
                        print(f'Remote head {remote_head} != push dst {push.dst}; pushing {src} directly…')
                        run('git','push',remote,f'{src}:{push.dst}')
                    else:
                        print(f"Avoiding direct push of {src} to remote HEAD {remote_head}; pushing to {tmp_branch} then merging…")
                        run('git','push',remote,f'{src}:{tmp_branch}')
                        run('ssh',host,f'cd {path} && (git merge {tmp_branch} && git branch -d {tmp_branch} || (git merge --abort; exit 1))')
                        run('git','fetch','--prune',remote,)
                else:
                    if not exists(url):
                        raise RuntimeError(f"Remote {remote} URL {url} doesn't appear to be an SSH URL or extant local directory")
                    with cd(url):
                        remote_head = git.branch.current(sha_ok=None)
                    if remote_head and push.dst and remote_head != push.dst:
                        print(f'Remote head {remote_head} != push dst {push.dst}; pushing {src} directly…')
                        run('git','push',remote,f'{src}:{push.dst}')
                    else:
                        print(f"Avoiding direct push of {src} to remote HEAD {remote_head}; pushing to {tmp_branch} then merging…")
                        run('git','push',remote,f'{src}:{tmp_branch}')
                        with cd(url):
                            try:
                                run('git','merge',f'{tmp_branch}')
                            except CalledProcessError as e:
                                conflicts = lines('git','diff','--name-only','--diff-filter=U')
                                if conflicts:
                                    stderr.write('Found conflicting files:\n\t%s' % '\n\t'.join(conflicts))
                                    run('git','merge','--abort')
                                else:
                                    stderr.write('Merge failed, presumably due to uncommitted changes:\n\t%s\n' % '\n\t'.join(lines('git','status','--short','-uno')))
                                raise e
                            run('git','branch','-d',tmp_branch)
                        run('git','fetch','--prune',remote,)
            else:
                run('git','push',*push)

        if exc:
            raise exc
