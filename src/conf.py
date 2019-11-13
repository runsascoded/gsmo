from pathlib import Path

FMT= '%Y-%m-%dT%H:%M:%S'

RUN_SCRIPT_NAME = 'run'
RUNS_DIR = 'runs'
MSG_PATH = Path('_MSG')

DEFAULT_UPSTREAM_BRANCH = 'master'
RUNS_REMOTE = 'runs'
RUNS_BRANCH = 'runs'

CONFIG_PATH = Path('config.yaml')

SUCCESS_PATH = 'SUCCESS'
FAILURE_PATH = 'FAILURE'

LOGS_DIR = Path('logs')
OUT_PATH = LOGS_DIR / 'out'
ERR_PATH = LOGS_DIR / 'err'

EARLY_EXIT_EXCEPTION_MSG_PREFIX = 'OK: '

CRON_MODULE_RC = '.cron-module-rc'
CRON_MODULE_RC_ENV = 'CRON_MODULE_RC'

JUPYTER_KERNEL_NAME = '3.7.4'
