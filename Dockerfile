FROM quay.io/ucsc_cgl/redwood-client:1.2.2

RUN apt-get update && apt-get install -y  python python-pip
RUN pip install --upgrade pip

ENV SPINNAKER_CLIENT_HOME /dcc/dcc-spinnaker-client

ADD . ${SPINNAKER_CLIENT_HOME}
RUN pip install -r ${SPINNAKER_CLIENT_HOME}/requirements.txt

ENV PATH ${SPINNAKER_CLIENT_HOME}/bin:${PATH}

WORKDIR ${SPINNAKER_CLIENT_HOME}
