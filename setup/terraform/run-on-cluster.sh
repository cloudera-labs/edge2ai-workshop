#!/bin/bash
set -o errexit
set -o nounset
BASE_DIR=$(cd $(dirname $0); pwd -L)
source $BASE_DIR/lib/common-basics.sh

if [ $# -lt 3 ]; then
  echo "Syntax: $0 <namespace> <cluster_number> command"
  show_namespaces
  exit 1
fi
NAMESPACE=$1
CLUSTER_ID=$2

source $BASE_DIR/lib/common.sh

LOG_DIR=$BASE_DIR/logs
LOG_FILE=$LOG_DIR/command.${NAMESPACE}.$(date +%s).log

PUBLIC_DNS=$(public_dns $CLUSTER_ID)

if [[ $CLUSTER_ID == "web" ]]; then
  SSH_KEY=$TF_VAR_web_ssh_private_key
else
  SSH_KEY=$TF_VAR_ssh_private_key
fi

shift 2
cmd=("$@")
ssh -o StrictHostKeyChecking=no -i $SSH_KEY $TF_VAR_ssh_username@$PUBLIC_DNS "${cmd[@]}" | tee $LOG_FILE
echo "Log file: $LOG_FILE"
