#!/bin/bash 

. $HOME/.profile

cmd="/home/ubuntu/jenkins-to-graphite/jenkins-to-graphite.py --jenkins-url=https://prod-pipeline.fictiv.com/jenkins/ --jenkins-user=jim@fictiv.com --jenkins-password=ebec5039c7f6dec7a9e0d79d311376fc --region=us-west-2 --job=pipeline-model-v4"

exec $cmd ${@:+"$@"}
