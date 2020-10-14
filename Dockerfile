# Base Dockerfile for Python projects; recent Git, pandas/jupyter/sqlalchemy, and dotfiles for working in-container
ARG PYTHON=3.9.0
FROM python:${PYTHON}-slim

# Disable pip upgrade warning, add default system-level gitignore, and configs for setting git user.{email,name} at run-time
COPY etc/pip.conf etc/.gitignore etc/gitconfig /etc/

RUN echo "deb http://ftp.us.debian.org/debian testing main" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y \
      curl \
      gcc g++ \
      git \
      nano \
      && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists

# Basic pip dependencies: Jupyter, pandas
RUN pip install --upgrade --no-cache \
  pip wheel \
  jupyter==1.0.0 nbdime==2.1.0 \
  pandas==1.1.3 \
  pyyaml==5.3.1 \
  utz==0.0.17 utz[setup]==0.0.17

# Install dotfiles + bash helpers and Jupyter configs
WORKDIR /root
RUN curl -L https://j.mp/_rc > _rc && chmod u+x _rc && ./_rc -b server runsascoded/.rc
COPY usr/local/etc/jupyter/nbconfig/notebook.json /usr/local/etc/jupyter/nbconfig/

WORKDIR /

# Create an open directory for pointing anonymouse users' $HOME at (e.g. `-e HOME=/home -u `id -u`:`id -g` `)
RUN chmod ugo+rwx /home
# Simple .bashrc for anonymous users that just sources /root/.bashrc
COPY home/.bashrc /home/.bashrc
# Make sure /root/.bashrc is world-accessible
RUN chmod o+rx /root

ENTRYPOINT [ "python3.7", "/gsmo/run_module.py", "/src" ]
