# This ping/pong handler creates a .pong file in response to a .ping file
# being created in subscribed S3 bucket.

import boto3


def handler(event, context):
    for record in event["Records"]:
        if "s3" in record:
            bucket_name = record["s3"]["bucket"]["name"]
            key = record["s3"]["object"]["key"]

            if key.endswith(".ping"):
                output_key = key.replace("ping", "pong")
                s3 = boto3.client("s3")
                s3.put_object(Bucket=bucket_name, Key=output_key, Body=bytes("Hello, world!", "utf-8"), ServerSideEncryption="AES256")
