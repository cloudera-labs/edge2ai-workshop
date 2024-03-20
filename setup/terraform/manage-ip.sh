#!/bin/bash
set -o errexit
set -o nounset
BASE_DIR=$(cd $(dirname $0); pwd -L)
source $BASE_DIR/lib/common-basics.sh

if [[ $# -lt 3 || ( ${2:-} != "add" && ${2:-} != "remove" ) ]]; then
  echo "Syntax: $0 <namespace> <"\""add"\""|"\""remove"\""> <ip_address>"
  show_namespaces
  exit 1
fi
NAMESPACE=$1
ACTION=$2
IP_ADDRESS=$3

NEED_CLOUD_SESSION=1
source $BASE_DIR/lib/common.sh

IP_FILE=/tmp/sync-ip-addresses.$$

function cleanup() {
  rm -f $IP_FILE
}

if [[ $(echo "$IP_ADDRESS" | tr "a-z" "A-Z") == "MYIP" ]]; then
  IP_ADDRESS=$(get_public_ip)
fi

if [[ $(expr "$IP_ADDRESS" : '.*:') -gt 0 ]]; then
  # IPv6
  cidr="${IP_ADDRESS}/128"
else
  # IPv4
  cidr="${IP_ADDRESS}/32"
fi

cluster_sg=$(security_groups cluster)
web_sg=$(security_groups web)

if [[ $ACTION == "add" ]]; then
  add_ingress "$cluster_sg" "$cidr" all all "MANUAL" force
  add_ingress "$web_sg" "$cidr" all all "MANUAL" force
elif [[ $ACTION == "remove" ]]; then
  remove_ingress "$cluster_sg" "$cidr" all all force
  remove_ingress "$web_sg" "$cidr" all all force
fi
refresh_tf_state