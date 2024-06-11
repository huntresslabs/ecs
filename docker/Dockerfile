FROM ubuntu:latest
ARG BRANCH=main
RUN mkdir /ecs && apt update && apt install -y git python3-pip && apt clean
WORKDIR /ecs
RUN git clone https://github.com/huntresslabs/ecs . && git checkout ${BRANCH} && python3 -m pip install --break-system-packages -r scripts/requirements.txt
COPY scripts/entry_point.sh entry_point.sh
ENTRYPOINT ["/bin/bash", "/ecs/entry_point.sh"]
