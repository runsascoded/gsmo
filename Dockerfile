FROM python:3.7.4

RUN pip3 install -U \
    jupyter papermill \
    pip \
    python-dateutil pytz
RUN python -m ipykernel install --name 3.7.4

RUN apt-get update
RUN apt-get upgrade -y git

ADD src /cron

# mount a "module" git repo into /src
WORKDIR /src

ENTRYPOINT [ "python3.7", "/cron/run_module.py", "/src" ]
