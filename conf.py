from pathlib import Path

FMT= '%Y-%m-%dT%H:%M:%S'

RUN_SCRIPT = 'run.sh'
RUNS_DIR = 'runs'
STATE_FILE = 'STATE'

STATE_BRANCH_PREFIX = 'state-'
RUNS_BRANCH_PREFIX = 'runs-'
DEFAULT_UPSTREAM_BRANCH = 'master'

SUCCESS_PATH = 'SUCCESS'
FAILURE_PATH = 'FAILURE'

LOGS_DIR = Path('logs')
OUT_PATH = LOGS_DIR / 'out'
ERR_PATH = LOGS_DIR / 'err'

LOCK_FILE_NAME = '.LOCK'

CRON_MODULE_RC = '.cron-module-rc'
CRON_MODULE_RC_ENV = 'CRON_MODULE_RC'
