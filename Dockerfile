FROM python:3.7.4

RUN pip3 install -U jupyter papermill pip pyyaml
RUN python -m ipykernel install --name 3.7.4

RUN apt-get update
RUN apt-get upgrade -y git

ADD src /gismo

# mount a "module" git repo into /src
WORKDIR /src

ENTRYPOINT [ "python3.7", "/gismo/run_module.py", "/src" ]
