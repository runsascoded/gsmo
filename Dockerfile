FROM python:3.7.4
RUN pip3 install -U papermill pip pytz
RUN apt-get update
RUN apt-get upgrade -y git
RUN git config --global user.name 'cron'
RUN git config --global user.email 'cron@cron.com'

ADD src /cron

# mount a "module" git repo into /src
WORKDIR /src

ENTRYPOINT [ "python3.7", "/cron/run_module.py", "/src" ]
