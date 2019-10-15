from contextlib import contextmanager
from errno import EINTR
from fcntl import flock, LOCK_EX
from pathlib import Path
from signal import alarm, signal, SIGALRM

@contextmanager
def timeout(seconds):
    def timeout_handler(signum, frame):
        raise InterruptedError

    original_handler = signal(SIGALRM, timeout_handler)

    try:
        alarm(seconds)
        yield
    finally:
        alarm(0)
        signal(SIGALRM, original_handler)

@contextmanager
def lock(path, timeout_s):
    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    with timeout(timeout_s):
        with path.open("w") as f:
            try:
                flock(f, LOCK_EX)
                yield
            except InterruptedError:
                raise Exception("Failed to lock %s in %ds" % (path, timeout_s))
