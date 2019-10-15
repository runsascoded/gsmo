FROM python:3.7.4
ADD src /src/cron
ENTRYPOINT [ "python3.7", "/src/cron/run_module.py" ]
