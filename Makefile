build:
	docker build -t dcc-uploader .

upload:
	sudo rm -rf outputs
	docker run -it --rm \
		-v `pwd`/examples:/inputs \
		-v `pwd`/outputs:/outputs \
		--link spinnaker:spinnaker \
		dcc-uploader \
		--storage-access-token $(UCSC_DCC_TOKEN) \
		--submission-server-url http://spinnaker:5000 \
		--force-upload \
		/inputs/two_manifest.tsv

debug:
	docker run -it --rm --entrypoint=/bin/sh \
		-v `pwd`/samples:/samples \
		-v `pwd`/outputs:/outputs \
		-v `pwd`/manifests:/manifests \
		--link spinnaker:spinnaker \
		dcc-uploader
