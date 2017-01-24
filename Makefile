build:
	docker build -t dcc-spinnaker-client .

upload:
	sudo rm -rf outputs
	docker run -it --rm \
		-v `pwd`/manifests:/manifests \
		-v `pwd`/samples:/samples \
		-v `pwd`/outputs:/outputs \
		dcc-spinnaker-client \
		--storage-access-token $(UCSC_DCC_TOKEN) \
		--submission-server-url http://spinnaker.medbook.io:5000 \
		--force-upload \
		/manifests/three_manifest.tsv

skip_submit:
	sudo rm -rf outputs
	docker run -it --rm \
		-v `pwd`/manifests:/manifests \
		-v `pwd`/samples:/samples \
		-v `pwd`/outputs:/outputs \
		dcc-spinnaker-client \
		--storage-access-token $(UCSC_DCC_TOKEN) \
		--force-upload \
		--skip-submit \
		/manifests/three_manifest.tsv

debug:
	docker run -it --rm --entrypoint=/bin/sh \
		-v `pwd`/manifests:/manifests \
		-v `pwd`/samples:/samples \
		-v `pwd`/outputs:/outputs \
		--link spinnaker:spinnaker \
		dcc-spinnaker-client
