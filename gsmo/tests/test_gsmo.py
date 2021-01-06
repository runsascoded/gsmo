from git import Repo
import json
import pytest

from gsmo import gsmo
from utz import b62, CalledProcessError, cd, contextmanager, dirname, env, exists, getcwd, git, join, lines, match, mkdir, now, o, run


@contextmanager
def example(name, ref=None, *args, **kwargs,):
    repo = Repo(search_parent_directories=True)
    gsmo_dir = repo.working_dir
    example_dir = join(gsmo_dir, 'example', name)
    tmp_dir = join(gsmo_dir, '.test')
    mkdir(tmp_dir)
    with git.clone.tmp(example_dir, *args, ref=ref, dir=tmp_dir, **kwargs) as wd:
        yield wd


def run_gsmo(*args, dind=False):
    tag = env.get('GSMO_IMAGE_TAG')
    if tag:
        if dind:
            img_tag = f':dind_{tag}'
        else:
            img_tag = tag
    else:
        if dind:
            img_tag = ':dind'
        else:
            img_tag = ':'
    flags = ['-I','-i',img_tag]
    gsmo.main(*flags,'run',*args)


def test_dind():
    with example('dind',ref='c60d0fa'):
        run_gsmo('-x','docker-hello-world.ipynb', dind=True)
        with open('nbs/docker-hello-world.ipynb','r') as f:
            nb = json.load(f)
        cells = nb['cells']
        assert len(cells) == 6
        assert cells[0]['outputs'] == []
        out = cells[-1]['outputs']
        assert all(o['name'] == 'stdout' for o in out)
        assert ''.join([ ln for o in out for ln in o['text'] ]) == '''Running: docker run --rm hello-world

Hello from Docker!
This message shows that your installation appears to be working correctly.

To generate this message, Docker took the following steps:
 1. The Docker client contacted the Docker daemon.
 2. The Docker daemon pulled the \"hello-world\" image from the Docker Hub.
    (amd64)
 3. The Docker daemon created a new container from that image which runs the
    executable that produces the output you are currently reading.
 4. The Docker daemon streamed that output to the Docker client, which sent it
    to your terminal.

To try something more ambitious, you can run an Ubuntu container with:
 $ docker run -it ubuntu bash

Share images, automate workflows, and more with a free Docker ID:
 https://hub.docker.com/

For more examples and ideas, visit:
 https://docs.docker.com/get-started/


'''


def test_hailstone():
    with example('hailstone'):
        def step(value):
            run_gsmo()
            if value == 1:
                return
            if value % 2 == 0:
                value /= 2
            else:
                value = 3*value + 1
            step(value)

        step(6)
        expected = [
            'value is already 1; exiting early',
            '2 → 1',
            '4 → 2',
            '8 → 4',
            '16 → 8',
            '5 → 16',
            '10 → 5',
            '3 → 10',
            '6 → 3',
        ]
        actual = lines('git','log',f'-n{len(expected)}','--format=%s')
        assert actual == expected


def test_factors():
    with example('factors', ref='876c95c'):
        run_gsmo()
        tree = Repo().commit().tree
        assert tree['graph.png'].hexsha == '1ed114e1dd88d516ca749e516d24ef1d28fdb0de'
        assert tree['primes.png'].hexsha == '5189952fe9bcfb9f196b55bde9f6cc119b842017'
        assert tree['ints.parquet'].hexsha == '859a019cfa004fd4bf6d93789e47c85f167a1d5d'

        run_gsmo('-y','limit: 50')
        tree = Repo().commit().tree
        assert tree['graph.png'].hexsha == '6e432cd84a537648ec6559719c74e1b3021c707c'
        assert tree['primes.png'].hexsha == '107debbdfe8ae9c146d99ca97a5563201e0f8f22'
        assert tree['ints.parquet'].hexsha == '79ea92b9788a7424afc84674179db1b39c371111'

        run_gsmo('-y','limit: 50')
        tree = Repo().commit().tree
        assert tree['graph.png'].hexsha == '6e432cd84a537648ec6559719c74e1b3021c707c'
        assert tree['primes.png'].hexsha == '107debbdfe8ae9c146d99ca97a5563201e0f8f22'
        assert tree['ints.parquet'].hexsha == '79ea92b9788a7424afc84674179db1b39c371111'


def get_submodule_commit(sm_path):
    parent_tree = Repo().commit().tree
    sm_hexsha = parent_tree[sm_path].hexsha
    return Repo(sm_path).commit(sm_hexsha)


def test_submodules():
    with example('submodules', ref='885b6c2') as wd:
        run_gsmo()

        sm_commit = get_submodule_commit('generate-random-ints')
        lns = sm_commit.tree['out/ints.txt'].data_stream.read().decode().split('\n')
        assert [ int(l) for l in lns if l ] == [ 6, 34, 11, 98, 52, 34, 13, 4, 48, 68, ]

        sm_commit = get_submodule_commit('sort')
        lns = sm_commit.tree['out/ints.txt'].data_stream.read().decode().split('\n')
        assert [ int(l) for l in lns if l ] == [ 4, 6, 11, 13, 34, 48, 52, 68, 98, ]

        branch = git.branch.current()
        assert lines('git','log','--graph','--format=%d %s', 'HEAD~2..HEAD') == [
            f'*    (HEAD -> {branch}) run',
            r'|\  ',
            r'| *  sort',
            r'| *  generate-random-ints',
            r'|/  ',
            r'*  (origin/master, origin/HEAD, master) support recursive generate-random-ints',
        ]

        run_gsmo('-y','conf:\n  generate-random-ints:\n    n: 1,3,6')

        sm_commit = get_submodule_commit('generate-random-ints')
        lns = sm_commit.tree['out/ints.txt'].data_stream.read().decode().split('\n')
        assert [ int(l) for l in lns if l ] == [ 6, 34, 11, 98, 52, 34, 13, 4, 48, 68, ]

        sm_commit = get_submodule_commit('sort')
        lns = sm_commit.tree['out/ints.txt'].data_stream.read().decode().split('\n')
        assert [ int(l) for l in lns if l ] == [ 4, 6, 11, 13, 34, 48, 52, 68, 98, ]

        assert lines('git','log','--graph','--format=%d %s', 'HEAD~3..HEAD') == [
            f'*    (HEAD -> {branch}) run',
            r'|\  ',
            r'| *  sort',
            r'| *  generate-random-ints',
            r'|/| ',
            r'| *  generate random ints 2 of 3 (6)',
            r'| *  generate random ints 1 of 3 (3)',
            r'| *  generate random ints 0 of 3 (1)',
            r'|/  ',
            r'*    run',
            r'|\  ',
            r'| *  sort',
            r'| *  generate-random-ints',
            r'|/  ',
            r'*  (origin/master, origin/HEAD, master) support recursive generate-random-ints',
        ]

def test_clone_local():
    cwd = getcwd()
    working_branch = 'gsmo-test'
    sha = 'e0add3d'
    gsmo_dir = dirname(dirname(gsmo.__file__))
    hailstone_dir = join(gsmo_dir, 'example/hailstone')
    with git.clone.tmp(
        hailstone_dir,
        branch=working_branch,
        ref=sha,
    ) as tmpdir:
        # Use this temporary clone of the example/hailstone module as a "base" from which to demonstrate running `gsmo`
        # in further temporary Git clone directories and upstreaming changes back to the "base" directory.

        branch = git.branch.current()
        assert working_branch == branch
        sha0 = git.sha(branch)
        assert sha0 == sha
        assert not exists('value')

        flags = ['-I','-i',':',]

        # move back to gsmo dir, and run hailstone "remotely" (against a different directory on the same host, namely
        # the tmpdir created above)
        with cd(cwd):
            gsmo.main(*flags,tmpdir,'run','--clone')

        assert lines('git','show',f'{branch}:value') == ['3']
        assert git.branch.current() == branch

        sha1 = git.sha('HEAD')
        assert sha1 == git.sha(branch)

        assert git.sha(f'{branch}^') == sha0
        assert not lines('git','status','--short')

        # run again
        with cd(cwd):
            gsmo.main(*flags,tmpdir,'run','--clone')

        assert lines('git','show',f'{branch}:value') == ['10']
        assert git.branch.current() == branch

        sha2 = git.sha('HEAD')
        assert sha2 == git.sha(branch)

        assert git.sha(f'{branch}^') == sha1
        assert git.sha(f'{branch}~2') == sha0
        status = lines('git','status','--short')
        assert not status


def test_clone_remote():
    # set this HAILSTONE_SSH_URL to a different fork or repo if developing without access to this one
    url = env.get('HAILSTONE_SSH_URL', 'git@gitlab.com:gsmo/examples/hailstone.git')
    branch = f'gsmo-test-{b62(now().ms)}'
    sha0 = 'e0add3d'
    sha0_full = 'e0add3d2805fc8999dab650697a22f1939fd5396'
    with git.clone.tmp(
        url,
        branch=branch,
        ref=sha0,
    ):
        run('git','push',url,branch)
        try:
            remote_branch_sha = git.ls_remote(url, head=branch, sha=sha0)
            assert remote_branch_sha == sha0_full
            flags = ['-I','-i',':']

            gsmo.main(*flags,url,'run','-b',branch)
            run('git','fetch','origin',branch)
            sha1 = git.sha(f'origin/{branch}')
            assert git.sha(f'origin/{branch}^') == sha0
            assert Repo().commit(sha1).tree['value'].data_stream.read().decode().strip() == '3'

            # run again, with `branch` embedded in the URL
            gsmo.main(*flags,f'{url}@{branch}','run')
            run('git','fetch','origin',branch)
            sha2 = git.sha(f'origin/{branch}')
            assert git.sha(f'origin/{branch}^') == sha1
            assert Repo().commit(sha2).tree['value'].data_stream.read().decode().strip() == '10'
        finally:
            run('git','push','--delete',url,branch)


def test_post_run_push_bare():
    branch = 'gsmo-test'
    sha0 = 'e0add3d'
    gsmo_dir = dirname(dirname(gsmo.__file__))
    hailstone_dir = join(gsmo_dir, 'example/hailstone')
    with git.clone.tmp(
        hailstone_dir,
        bare=True,
        branch=branch,
        ref=sha0,
    ) as origin:
        flags = ['-I','-i',':','-v',origin]
        with git.clone.tmp(origin, branch=branch):
            gsmo.main(*flags,'run','--push','origin')
            sha1 = git.sha()
            assert git.sha(f'origin/{branch}') == sha1
            assert lines('cat','value') == ['3']

        with cd(origin):
            assert git.sha(branch) == sha1
            assert git.sha(f'{branch}^') == sha0
            assert lines('git','show','HEAD:value') == ['3']

        with git.clone.tmp(origin, branch=branch):
            gsmo.main(*flags,'run','--push','origin')
            sha2 = git.sha()
            assert git.sha(f'origin/{branch}') == sha2
            assert lines('cat','value') == ['10']

        with cd(origin):
            assert git.sha(branch) == sha2
            assert git.sha(f'{branch}^') == sha1
            assert lines('git','show','HEAD:value') == ['10']


def shas(kvs):
    for expected_sha, refs in kvs.items():
        if isinstance(refs, str): refs = [refs]
        for ref in refs:
            if ref is None:
                actual_sha = git.sha()
            else:
                actual_sha = git.sha(ref)
            assert actual_sha == expected_sha, f'{ref} (from {refs}): {actual_sha} != {expected_sha}'


def test_post_run_pull():
    '''Test several cases related to gsmo merging changes into a non-bare upstream repo

    The `origin` of a gsmo working clone may have uncommitted changes at the time of cloning (which are not carried over
    into the clone), or it may accrue uncommitted or committed changes while the working clone is running. Additionally,
    such upstream changes may conflict with updates made by the working clone, or may not.

    `gsmo run`'s default approach to "push refs" (e.g. `--push origin`) is to run `git push origin` at the end of a
    `gsmo run` invocation (e.g. to send changes to the `origin` remote). This is generally sufficient for "bare" remotes
    (like most Git servers expose, e.g. GitHub, GitLab, etc.).

    However, sometimes the logical `origin` may itself be a non-bare clone (on a local or remote server) where changes
    are sometimes made directly in the work tree. In this case, more complicated merge/"push" logic can be enabled by
    appending an "!" to the "push ref" (e.g. `--push 'origin!'`):

    - if the `origin` branch being pushed to is not origin/HEAD (i.e. it is not currently checked out on the origin),
      normal `git push` is performed
    - otherwise:
      - working-clone changes are pushed to a temporary branch (named like `origin/tmp-bTRRyRg`, where the nonce is a
        base62 serialization of the current time in milliseconds)
      - gsmo moves into `origin`'s work-tree (either via `cd` or `ssh`), and attempts to `git merge` the temporary
        branch into the desired destination branch:
        - if this succeeds, the temporary branch is deleted, and all is considered to be well
        - otherwise:
          - if the merge failed due to a merge conflict, the merge is aborted, leaving `origin`'s worktree in its
            previous, unconflicted state
          - if it failed due to local, uncommitted changes that would be overwritten, no additional action is taken
          - in both cases, the dangling tmp-branch is left pointing to the unmerged changes (which should be resolved
            later / manually)
    '''
    branch = 'gsmo-test'
    sha0 = 'e0add3d'
    gsmo_dir = dirname(dirname(gsmo.__file__))
    hailstone_dir = join(gsmo_dir, 'example/hailstone')
    with git.clone.tmp(
        hailstone_dir,
        branch=branch,
        ref=sha0,
    ) as origin:
        flags = ['-I','-i',':','-v',origin]

        def step(
            expected_value,
            parent,
            status=None,
            origin_commit=False,
            expect_fail=False,
            wd_shas=None,
            origin_shas=None,
        ):
            if isinstance(expected_value, dict):
                tmpclone_value = expected_value['tmpclone']
                worktree_value = expected_value['worktree']
                head_value = expected_value['head']
            else:
                tmpclone_value = worktree_value = head_value = expected_value

            # collect output values here
            r = o()
            r.parent = parent

            with git.clone.tmp(origin, branch=branch):

                # optionally create a commit upstream, "underneath" this temporary clone
                if origin_commit:
                    with cd(origin):
                        run('git','commit','-am','concurrent origin commit')
                        r.l_sha = git.sha()

                # run gsmo, optionally catching a failure
                if expect_fail:
                    with pytest.raises(CalledProcessError) as e:
                        gsmo.main(*flags,'run','--push','origin!')
                    e.match('Command .* returned non-zero exit status 1')
                else:
                    gsmo.main(*flags,'run','--push','origin!')

                sha = git.sha()
                if origin_commit:
                    r.r_sha = sha
                    r.merge_sha = git.sha(f'origin/{branch}')
                else:
                    r.sha = sha

                remote_refs = lines('git','for-each-ref','--format=%(refname:short)','refs/remotes/origin')
                if expect_fail:
                    # A failed merge will leave a temporary branch on origin, named like `tmp-bTMnva7` (the nonce corresponds
                    # to epoch milliseconds); back out its name here by verifying+discarding expected origin branches
                    remote_branches = set([ match('origin/(.*)', ref)[1] for ref in remote_refs ])
                    expected = {'master', 'HEAD', branch}
                    assert remote_branches.issuperset(expected)
                    extra_branches = remote_branches.difference(expected)
                    assert len(extra_branches) == 1, str(extra_branches)
                    [tmp_branch] = extra_branches
                    r.tmp_branch = tmp_branch

                if wd_shas:
                    shas(wd_shas(r))
                else:
                    assert git.sha(f'origin/{branch}') == sha

                assert lines('cat','value') == [str(tmpclone_value)]

            origin_sha = git.sha()
            r.origin_sha = origin_sha
            if origin_shas:
                shas(origin_shas(r))
            else:
                assert git.sha(branch) == origin_sha
                assert git.sha(f'{branch}^') == parent

            assert lines('cat','value') == [str(worktree_value)]
            assert lines('git','show','HEAD:value') == [str(head_value)]
            assert lines('git','status','--short') == (status or [])

            expected_branches = {branch, 'master'}
            if expect_fail:
                expected_branches.add(tmp_branch)

            assert set(git.branch.ls()) == expected_branches

            if expect_fail:
                run('git','branch','-D',tmp_branch)

            return origin_sha

        # Run twice, pulling results into `origin` from transient clones
        sha1 = step(3, sha0)
        sha2 = step(10, sha1)

        # simulate some uncommitted, unrelated changes laying around in `origin`'s work-tree:
        with open('README.md','a') as f:
            f.write('example staged change\n')
            run('git','add','README.md')
            f.write('example unstaged change\n')

        # `gsmo` runs successfully from origin's HEAD (which is cloned without origin's uncommitted worktree changes to
        # README.md). The changes remain in origin's worktree (⚠️ NOTE: previously staged changes become unstaged ⚠️).
        sha3 = step(5, sha2, status=[' M README.md'])
        assert lines('git','diff')[-2:] == [
            '+example staged change',
            '+example unstaged change',
        ]
        assert lines('git','diff','--cached') == []

        # Run again, but after the tmp clone is created, `origin` commits changes to `README.md`; when tmp clone
        # finishes, it pushes to a tmp branch on origin and triggers a merge into origin/branch, resulting in a commit
        # diamond.
        sha4 = step(
            16, sha3,
            origin_commit=True,
            wd_shas=lambda r: {
                # tmp clone doesn't know abt merge performed on origin as part of pulling from tmp clone
                r.merge_sha: (f'origin/{branch}', 'origin/HEAD'),
                r.l_sha: (f'origin/{branch}^'),
                r.r_sha: (None, branch, f'origin/{branch}^2'),
                r.parent: (f'origin/{branch}^^', f'{branch}^')
            },
            origin_shas=lambda r: {
                r.origin_sha: branch,
                r.l_sha: f'{branch}^',
                r.r_sha: f'{branch}^2',
                r.parent: f'{branch}^^',
            },
        )

        # simulate an uncommitted worktree change that will conflict with the next gsmo run
        with open('value','w') as f:
            f.write('-16\n')

        step(
            o(tmpclone=8, worktree=-16, head=16),
            parent=sha4,
            expect_fail=True,
            wd_shas=lambda r: {
                r.sha: ('HEAD', branch, f'origin/{r.tmp_branch}',),
                r.parent: (f'origin/{branch}', 'origin/HEAD',),
            },
            origin_shas=lambda r: {
                r.sha: r.tmp_branch,
                r.parent: ('HEAD', branch, f'{r.tmp_branch}^'),
            },
            status=[' M value'],
        )

        step(
            o(tmpclone=8, worktree=-16, head=-16),
            parent=sha4,
            wd_shas=lambda r: {
                r.r_sha: ('HEAD', branch, f'origin/{r.tmp_branch}',),
                r.parent: (f'origin/{branch}', 'origin/HEAD',),
            },
            origin_shas=lambda r: {
                r.l_sha: ('HEAD', branch),
                r.r_sha: r.tmp_branch,
                r.parent: (f'{branch}^', f'{r.tmp_branch}^'),
            },
            origin_commit=True,
            expect_fail=True,
        )
