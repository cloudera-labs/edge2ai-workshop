import boto3
import json
import os
import re
import sys
from subprocess import Popen, PIPE
from tempfile import mkstemp
from botocore.exceptions import ClientError


def create_presigned_url(s3_client, bucket_name, object_name, expiration=7200):
    response = s3_client.generate_presigned_url("get_object",
                                                Params={"Bucket": bucket_name,
                                                        "Key": object_name},
                                                ExpiresIn=expiration)
    return response


def get_file(s3_client, bucket, key):
    s3 = boto3.resource('s3')
    _, tempfile_path = mkstemp()
    try:
        s3_client.download_file(bucket, key, tempfile_path)
    except ClientError as exc:
        if key.endswith("/manifest.json") and "Error" in exc.response and "Code" in exc.response["Error"] and \
                exc.response["Error"]["Code"] in ["404", "403"]:
            return None
        raise
    return open(tempfile_path, 'r').read()


def remove_file(file_path):
    try:
        os.remove(file_path)
    except OSError:
        pass


def compute_env(file_path):
    command = "bash -c 'source %s && set'" % (file_path,)
    proc = Popen(command, shell=True, stdout=PIPE)
    stdout, _ = proc.communicate()
    env = {}
    for line in stdout.decode().split("\n"):
        line = line.rstrip()
        m = re.match(r"^([A-Za-z0-9_]*)=(s3://([^/]*)/(.*))", line)
        if m:
            var_name, value, bucket, key = m.groups()
            env[var_name] = {"value": value, "bucket": bucket, "key": key}
    return env


def convert_stack_file(s3_client, file_path, output_dir=None):
    env = compute_env(file_path)
    output_stack_path = file_path + ".signed"
    output_urls_path = file_path + ".urls"
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_stack_path = os.path.join(output_dir, os.path.basename(output_stack_path))
        output_urls_path = os.path.join(output_dir, os.path.basename(output_urls_path))

    remove_file(output_stack_path)
    output_stack_file = open(output_stack_path, "w")
    url_map = {}
    converted = False
    for line in open(file_path):
        line = line.rstrip()
        m = re.match(r"(^[^=]*)=", line)
        if m:
            var_name, = m.groups()
            if var_name in env:
                converted = True
                bucket = env[var_name]["bucket"]
                key = env[var_name]["key"]
                main_presigned_url = create_presigned_url(s3_client, bucket, key)
                line = "%s=\"%s\"" % (var_name, main_presigned_url)

                # Check for manifest.json
                manifest_key = key.rstrip("/") + "/manifest.json"
                manifest = get_file(s3_client, bucket, manifest_key)
                if manifest:
                    manifest_presigned_url = create_presigned_url(s3_client, bucket, manifest_key)
                    url_map[main_presigned_url + "/manifest.json"] = manifest_presigned_url
                    j = json.loads(manifest)
                    for parcel in j["parcels"]:
                        parcel_key = key.rstrip("/") + "/" + parcel["parcelName"]
                        parcel_url = main_presigned_url + "/" + parcel["parcelName"]
                        parcel_presigned_url = create_presigned_url(s3_client, bucket, parcel_key)
                        url_map[parcel_url] = parcel_presigned_url

        output_stack_file.write(line + "\n")
    output_stack_file.close()

    remove_file(output_urls_path)
    if not converted:
        remove_file(output_stack_path)
    elif url_map:
        output_map = open(output_urls_path, "w")
        for key in url_map:
            output_map.write("%s-->%s\n" % (key, url_map[key]))
        output_map.close()


if __name__ == '__main__':
    PROFILE_NAME = os.environ.get("TF_VAR_aws_profile", "")
    SESSION = boto3.session.Session(
        profile_name=PROFILE_NAME if PROFILE_NAME else None,
        aws_access_key_id=os.environ.get("TF_VAR_aws_access_key_id", "") if not PROFILE_NAME else None,
        aws_secret_access_key=os.environ.get("TF_VAR_aws_secret_access_key", "") if not PROFILE_NAME else None,
        region_name="us-west-2")
    S3_CLIENT = SESSION.client("s3")

    FILE_PATH = sys.argv[1]
    OUTPUT_DIR = None
    if len(sys.argv) > 2 and sys.argv[2]:
        OUTPUT_DIR = sys.argv[2].rstrip('/')
    convert_stack_file(S3_CLIENT, FILE_PATH, OUTPUT_DIR)
