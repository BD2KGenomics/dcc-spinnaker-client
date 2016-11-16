build:
	docker build -t spinnaker-client .

upload:
	sudo rm -rf output_metadata
	docker run -it --rm \
		-v `pwd`/sample_upload_files:/sample_upload_files \
		-v `pwd`/output_metadata:/output_metadata \
		-v `pwd`/schemas:/schemas \
		-v `pwd`/sample_tsv:/sample_tsv \
		--link spinnaker:spinnaker \
		spinnaker-client python /scripts/spinnaker.py \
		--input-metadata-schema /schemas/input_metadata.json \
		--metadata-schema /schemas/metadata_schema.json \
		--output-dir /output_metadata \
		--receipt-file receipt.tsv \
		--storage-access-token $(UCSC_DCC_TOKEN) \
		--metadata-server-url https://storage2.ucsc-cgl.org:8444 \
		--storage-server-url https://storage2.ucsc-cgl.org:5431 \
		--submission-server-url http://spinnaker:5000 \
		--force-upload \
		/sample_tsv/two_files.tsv

debug:
	docker run -it --rm spinnaker-client /bin/bash
