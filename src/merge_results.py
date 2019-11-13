
from cd import cd
from conf import *
from process import run, success
from src import git


def merge_results(path, runs_path, config, base_sha, run_sha, msg, original_upstream_sha, remote, upstream_branch):
    run([ 'git', 'remote', 'add', RUNS_REMOTE, runs_path ])
    git.fetch(RUNS_REMOTE)
    runs_head = '%s/%s' % (RUNS_REMOTE, RUNS_BRANCH)
    runs_sha = git.sha(runs_head, missing_ok=True)

    if not git.exists(RUNS_BRANCH):
        run([ 'git', 'branch', RUNS_BRANCH, run_sha ])
    git.checkout(RUNS_BRANCH)

    if not runs_sha:
        print('%s branch doesn\'t exist on remote %s; created locally with current run SHA: %s' % (RUNS_BRANCH, RUNS_REMOTE, run_sha))
    elif git.is_ancestor(runs_sha, base_sha):
        print('Base SHA %s descends from %s/%s SHA %s; using existing run SHA %s' % (base_sha, RUNS_REMOTE, RUNS_BRANCH, runs_sha, run_sha))
    else:
        if git.is_ancestor(base_sha, runs_sha):
            new_run_sha = git.commit_tree(msg, runs_sha, sha=run_sha)
            print("Changing latest run %s parent from base SHA %s to %s/%s SHA %s; now %s" % (run_sha, base_sha, RUNS_REMOTE, RUNS_BRANCH, runs_sha, new_run_sha))
        else:
            new_run_sha = git.commit_tree(msg, base_sha, runs_sha, sha=run_sha)
            print('Giving latest run %s two parents: base SHA %s and %s/%s SHA %s; now %s' % (run_sha, base_sha, RUNS_REMOTE, RUNS_BRANCH, runs_sha, new_run_sha))

        run_sha = new_run_sha
        run([ 'git', 'reset', '-q', '--hard', run_sha ])

    with cd(runs_path):
        git.allow_pushes()

    git.push(RUNS_REMOTE, dest=RUNS_BRANCH)

    run([ 'git', 'config', 'advice.detachedHead', 'false' ])

    from config import strs
    state_paths = strs(config, 'state')
    if state_paths:
        git.checkout_and_reset(original_upstream_sha, None, run_sha, is_branch=False)
        git.add(state_paths)
        if not success('git', 'diff', '--cached', '--quiet'):
            print('Committing state updates')

            from datetime import datetime as dt
            now = dt.now()
            now_str = now.strftime(FMT)

            msg = '%s: update state' % now_str
            run([ 'git', 'commit', '-q', '-m', msg])
            print('Setting parents to base SHA %s and run SHA %s' % (base_sha, run_sha))
            sha = git.commit_tree(msg, base_sha, run_sha)
            with cd(path):
                git.allow_pushes()
            git.push(remote, src=sha, dest=upstream_branch)
        else:
            print('No state updates')
