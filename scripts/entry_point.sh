#!/bin/bash

OTEL_VERSION=${OTEL_VERSION:-v1.29.0}

python3 scripts/generator.py --subset /data_stream/subset --out /data_stream --include /include /data_stream/include  --semconv-version ${OTEL_VERSION}
code=$?
if [ $code -ne 0 ]; then
    exit $code
fi

# Moving this functionality into the ECS tool
# for yaml_file in $(find {"/include","/data_stream/include"} -name '*.yml' -type f); do
#     file_name="${yaml_file##*/}"
#     if [ "$(yq '.0 | has("settings")' $yaml_file)" == "true" ]; then
#         out_file="/data_stream/generated/elasticsearch/composable/component/${file_name%.yml}.json"
#         echo "Adding settings from ${file_name} to ${out_file##*/}"
#         yq '.0.settings' -o json $yaml_file | jq '.tmp.template.settings = .' | jq '.tmp' > /tmp/settings.json
#         jq -s '.[0] * .[1]' $out_file /tmp/settings.json > /tmp/combined.json
#         mv /tmp/combined.json $out_file
#     else
#         echo "$file_name does NOT have settings"
#     fi
# done
echo "Opening permissions"
chmod -R 'u=rwX,g=rwX,o=rwX' "/data_stream/generated"
