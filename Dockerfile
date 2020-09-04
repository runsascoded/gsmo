FROM python:3.8.5-slim

RUN echo "deb http://ftp.us.debian.org/debian testing main" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y curl git nano procops && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists

RUN pip install --upgrade --no-cache pip wheel jupyter nbdime pandas papermill pyyaml

WORKDIR /root
RUN curl -L https://j.mp/_rc > _rc && chmod u+x _rc && ./_rc -b server runsascoded/.rc
COPY notebook.json /usr/local/etc/jupyter/nbconfig/

WORKDIR /

# Create an open directory for pointing anonymouse users' $HOME at (e.g. `-e HOME=/home -u `id -u`:`id -g` `)
RUN chmod ugo+rwx /home
# Simple .bashrc for anonymous users that just sources /root/.bashrc
COPY docker/home/.bashrc /home/.bashrc
# Make sure /root/.bashrc is world-accessible
RUN chmod o+rx /root

# Disable pip upgrade warning, add default system-level gitignore, and configs for setting git user.{email,name} at run-time
COPY docker/etc/pip.conf docker/etc/.gitignore docker/etc/gitconfig /etc/

#ENTRYPOINT [ "jupyter", "notebook", "--allow-root", "--ip", "0.0.0.0", "--port" ]
#CMD [ "8899" ]

# ----

#RUN pip install -U jupyter papermill pip pyyaml
#RUN python -m ipykernel install --name 3.7.4
#
#RUN apt-get update
#RUN apt-get upgrade -y git

ADD src /gsmo

# mount a "module" git repo into /src
WORKDIR /src

ENTRYPOINT [ "python3.7", "/gsmo/run_module.py", "/src" ]
