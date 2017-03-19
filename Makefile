build:
	docker build -t dcc-spinnaker-client .

upload: clean
	docker run -it --rm \
		-v `pwd`/manifests:/manifests \
		-v `pwd`/samples:/samples \
		-v `pwd`/outputs:/outputs \
		--net redwood_default \
		--link redwood-nginx:metadata.redwood.io \
		--link redwood-nginx:storage.redwood.io \
		-e ACCESS_TOKEN=$(REDWOOD_ACCESS_TOKEN) \
		dcc-spinnaker-client \
		--submission-server-url http://spinnaker.medbook.io:5000 \
		--force-upload \
		/manifests/three_manifest.tsv

skip_submit: clean
	docker run -it --rm \
		-v `pwd`/manifests:/manifests \
		-v `pwd`/samples:/samples \
		-v `pwd`/outputs:/outputs \
		--net redwood_default \
		--link redwood-nginx:metadata.redwood.io \
		--link redwood-nginx:storage.redwood.io \
		-e ACCESS_TOKEN=$(REDWOOD_ACCESS_TOKEN) \
		dcc-spinnaker-client \
		--force-upload \
		--skip-submit \
		/manifests/three_manifest.tsv

debug: clean
	docker run -it --rm --entrypoint=/bin/bash \
		-v `pwd`/manifests:/manifests \
		-v `pwd`/samples:/samples \
		-v `pwd`/outputs:/outputs \
		--net redwood_default \
		--link redwood-nginx:metadata.redwood.io \
		--link redwood-nginx:storage.redwood.io \
		-e ACCESS_TOKEN=$(REDWOOD_ACCESS_TOKEN) \
		dcc-spinnaker-client
#		--link spinnaker:spinnaker \

clean:
	rm -rf outputs
