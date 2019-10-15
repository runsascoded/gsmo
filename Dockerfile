FROM python:3.7.4
ADD src /cron
ENTRYPOINT [ "python3.7", "/cron/run_module.py", "/src/run.sh" ]
