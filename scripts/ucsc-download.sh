#!/bin/bash

#
# Usage: icgc-download.sh object-id output-dir
#


# setup
base_url=$1
accessToken=`cat $2`
object=$3
download=$4

# perform download
java -Djavax.net.ssl.trustStore=ssl/cacerts -Djavax.net.ssl.trustStorePassword=changeit -Dmetadata.url=${base_url}:8444 -Dmetadata.ssl.enabled=true -Dclient.ssl.custom=false -Dstorage.url=${base_url}:5431 -DaccessToken=${accessToken} -jar icgc-storage-client-1.0.14-SNAPSHOT/lib/icgc-storage-client.jar download --output-dir ${download} --object-id ${object} --output-layout bundle
