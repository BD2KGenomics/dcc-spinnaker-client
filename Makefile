VERSION = 1.1.0-alpha

build:
	docker build -t dcc-spinnaker-client .
	docker tag dcc-spinnaker-client quay.io/ucsc_cgl/core-client:$(VERSION)

upload: clean
	docker run -it --rm \
		-v `pwd`/manifests:/manifests \
		-v `pwd`/samples:/samples \
		-v `pwd`/outputs:/outputs \
		--net redwood_internal \
		--link redwood-nginx:metadata.redwood.io \
		--link redwood-nginx:storage.redwood.io \
		-e ACCESS_TOKEN=$(REDWOOD_ACCESS_TOKEN) \
		dcc-spinnaker-client \
		--submission-server-url http://spinnaker.medbook.io:5000 \
		--force-upload \
		/manifests/two_manifest.tsv

skip_submit: clean
	docker run -it --rm \
		-v `pwd`/manifests:/manifests \
		-v `pwd`/samples:/samples \
		-v `pwd`/outputs:/outputs \
		--net redwood_internal \
		--link redwood-nginx:metadata.redwood.io \
		--link redwood-nginx:storage.redwood.io \
		-e ACCESS_TOKEN=$(REDWOOD_ACCESS_TOKEN) \
		dcc-spinnaker-client \
		--force-upload \
		--skip-submit \
		/manifests/two_manifest.tsv

debug: clean
	docker run -it --rm --entrypoint=/bin/bash \
		-v `pwd`/manifests:/manifests \
		-v `pwd`/samples:/samples \
		-v `pwd`/outputs:/outputs \
		--net redwood_internal \
		--link redwood-nginx:metadata.redwood.io \
		--link redwood-nginx:storage.redwood.io \
		-e ACCESS_TOKEN=$(REDWOOD_ACCESS_TOKEN) \
		dcc-spinnaker-client
#		--link spinnaker:spinnaker \

clean:
	rm -rf outputs
