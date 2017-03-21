FROM quay.io/ucsc_cgl/redwood-client:1.1.1

RUN apt-get update && apt-get install -y  python python-pip
RUN pip install --upgrade pip

ENV SPINNAKER_CLIENT_HOME /dcc/dcc-spinnaker-client

ADD . ${SPINNAKER_CLIENT_HOME}
RUN pip install -r ${SPINNAKER_CLIENT_HOME}/requirements.txt

ENV PATH ${SPINNAKER_CLIENT_HOME}/bin:${PATH}

# hack to show icgc logs in output dir
RUN mkdir -p /outputs \
 && mkdir -p ${DCC_HOME:-/dcc}/icgc-storage-client/logs \
 && mkdir -p ${DCC_HOME:-/dcc}/dcc-metadata-client/logs \
 && touch ${DCC_HOME:-/dcc}/icgc-storage-client/logs/client.log \
 && touch ${DCC_HOME:-/dcc}/dcc-metadata-client/logs/dcc-metadata-client.log \
 && ln -s ${DCC_HOME:-/dcc}/icgc-storage-client/logs/client.log /outputs/icgc-storage-client.log \
 && ln -s ${DCC_HOME:-/dcc}/dcc-metadata-client/logs/dcc-metadata-client.log /outputs/dcc-metadata-client.log

WORKDIR ${SPINNAKER_CLIENT_HOME}
ENTRYPOINT ["spinnaker-upload"]
