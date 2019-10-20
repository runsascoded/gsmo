from pathlib import Path

FMT= '%Y-%m-%dT%H:%M:%S'

RUN_SCRIPT = 'run.sh'
RUNS_DIR = 'runs'
STATE_FILE = 'STATE'
OUT_FILE = 'OUT'

DEFAULT_UPSTREAM_BRANCH = 'master'
RUNS_REMOTE = 'runs'
RUNS_BRANCH = 'runs'

SUCCESS_PATH = 'SUCCESS'
FAILURE_PATH = 'FAILURE'

LOGS_DIR = Path('logs')
OUT_PATH = LOGS_DIR / 'out'
ERR_PATH = LOGS_DIR / 'err'

CRON_MODULE_RC = '.cron-module-rc'
CRON_MODULE_RC_ENV = 'CRON_MODULE_RC'
