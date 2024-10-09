FROM ubuntu:latest
RUN mkdir /ecs && apt update && apt install -y git python3-pip && apt clean
WORKDIR /ecs
COPY . /ecs
RUN python3 -m pip install --break-system-packages -r /ecs/scripts/requirements.txt
ENTRYPOINT ["/bin/bash", "/ecs/docker/scripts/entry_point.sh"]
