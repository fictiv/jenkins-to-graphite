#!/bin/bash 

export HOME=/home/ubuntu
export PATH=/home/ubuntu/perl5/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/usr/lib/jvm/java-7-openjdk-amd64/jre/bin:/home/ubuntu/CloudWatch-1.0.20.0/bin
export JAVA_HOME=/usr/lib/jvm/java-7-openjdk-amd64/jre
export PATH=$PATH:$JAVA_HOME/bin
export AWS_CREDENTIAL_FILE=/home/ubuntu/.aws/credentials
export AWS_CLOUDWATCH_HOME=/home/ubuntu/CloudWatch-1.0.20.0
export PATH=$PATH:$AWS_CLOUDWATCH_HOME/bin
export AWS_CLOUDWATCH_URL=http://monitoring.us-west-2.amazonaws.com/

. $HOME/.profile

cmd="./jenkins-to-graphite.py --jenkins-url=https://prod-pipeline.fictiv.com/jenkins/ --jenkins-user=jim@fictiv.com --jenkins-password=ebec5039c7f6dec7a9e0d79d311376fc --job=worker-3dp-job-print-material"

exec $cmd 2>&1 | /usr/bin/logger -t worker_3dp_job_print_material_cloudwatch_data
#exec $cmd ${@:+"$@"}
