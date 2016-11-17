# #!/bin/bash
#
# #
# # Usage: ucsc-upload.sh dataFile...
# #
#
# # setup
# uuid=`cat /proc/sys/kernel/random/uuid`
# upload=`mktemp -d 2>/dev/null || mktemp -d -t 'mytmpdir'`/upload/${uuid}
# manifest=`mktemp -d 2>/dev/null || mktemp -d -t 'mytmpdir'`/manifest/${uuid}
# mkdir -p ${upload}
# mkdir -p ${manifest}
# cp $* ${upload}
#
# # get accessToken
# accessToken=`cat /token/access_token.txt`
#
# # register upload
# echo Registering upload:
# java -Djavax.net.ssl.trustStore=ssl/cacerts -Djavax.net.ssl.trustStorePassword=changeit -Dserver.baseUrl=https://storage.ucsc-cgl.org:8444 -DaccessToken=${accessToken} -jar dcc-metadata-client-0.0.16-SNAPSHOT/lib/dcc-metadata-client.jar -i ${upload} -o ${manifest} -m manifest.txt
#
# # perform upload
# echo Performing upload:
# java -Djavax.net.ssl.trustStore=ssl/cacerts -Djavax.net.ssl.trustStorePassword=changeit -Dmetadata.url=https://storage.ucsc-cgl.org:8444 -Dmetadata.ssl.enabled=true -Dclient.ssl.custom=false -Dstorage.url=https://storage.ucsc-cgl.org:5431 -DaccessToken=${accessToken} -jar icgc-storage-client-1.0.14-SNAPSHOT/lib/icgc-storage-client.jar upload --manifest ${manifest}/manifest.txt
#
# # cleanup
# rm -r ${upload}
# rm -r ${manifest}

# docker run -it -v /home/ubuntu/spinnaker/token:/token -v /home/ubuntu/spinnaker/spinnaker-client:/spinnaker spinnaker /bin/bash

python /spinnaker/spinnaker.py \
    --input-metadata-schema /schemas/input_metadata.json \
    --metadata-schema /schemas/metadata_schema.json \
    --output-dir output_metadata \
    --receipt-file receipt.tsv \
    --storage-access-token `cat /token/access_token.txt` \
    --metadata-server-url https://storage2.ucsc-cgl.org:8444 \
    --storage-server-url  https://storage2.ucsc-cgl.org:5431 \
    --force-upload \
    /spinnaker/sample_tsv/sample.tsv
