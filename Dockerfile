FROM python:3.7.4
RUN pip3 install -U pip pytz
# RUN add-apt-repository ppa:git-core/ppa
RUN apt-get update
RUN apt-get upgrade -y git
RUN git --version

ADD src /cron

# mount a "module" git repo into /src
WORKDIR /src

ENTRYPOINT [ "python3.7", "/cron/run_module.py", "/src" ]
