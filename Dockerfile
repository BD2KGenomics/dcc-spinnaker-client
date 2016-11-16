FROM ubuntu:14.04
MAINTAINER Teo Fleming <mokolodi1@gmail.com>

RUN apt-get update && apt-get install -y --force-yes \
    python-dev \
    python-pip \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    lib32z1-dev \
    libffi-dev \
    libssl-dev

# RUN easy_install pip

# skip virtualenv stuff because we're in a Dockerfile
# RUN pip install virtualenv
# RUN virtualenv env
# RUN source env/bin/activate

RUN pip install pip --upgrade
RUN pip install \
    jsonschema \
    jsonmerge \
    openpyxl \
    sets \
    json-spec \
    elasticsearch \
    semver \
    luigi

# requests security per:
# http://stackoverflow.com/questions/29099404/ssl-insecureplatform-error-when-using-requests-package
RUN pip install requests[security]==2.12.1

# Install Java
# NOTE: software-properties-common allows us to do add-apt-repository
# add apt-repo per:
# http://stackoverflow.com/a/33932047/1092640
RUN apt-get update && apt-get install -y software-properties-common
RUN add-apt-repository ppa:openjdk-r/ppa
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-8-jre

ADD dcc-metadata-client-0.0.16-SNAPSHOT /dcc-metadata-client
ADD icgc-storage-client-1.0.14-SNAPSHOT /icgc-storage-client
ADD ssl /ssl
ADD schemas /schemas
ADD spinnaker.py /scripts/
