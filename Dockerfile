FROM ubuntu:latest
WORKDIR /ecs
COPY . /ecs
RUN apt update \
    && apt install -y python3-pip \
    && apt clean \
    && python3 -m pip install --break-system-packages -r scripts/requirements.txt
ENTRYPOINT ["/bin/bash", "/ecs/scripts/entry_point.sh"]
