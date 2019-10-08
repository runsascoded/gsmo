# cron
Runner for simple directory-based "modules", suitable for crontab, that tracks runs in git

## "Modules"
A "module" is a git repository containing a `run.sh` script that is designed to be run regularly / on an interval (e.g. in a user's `crontab`).

### Example 
Demonstrate single runs of the [test/echo_module](test/echo_module) example modules:

```bash
python run_modules.py test/echo_module
```
