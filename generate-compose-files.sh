#!/bin/bash

while read -r container_name; do
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock red5d/docker-autocompose ${container_name} > ${container_name}-compose.yml
done <<< "$(docker ps --format '{{.Names}}')"