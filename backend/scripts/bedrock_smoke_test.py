"""Bedrock connectivity smoke test.

Verifies that the configured AWS credentials can:
  1. Resolve an STS identity (creds work at all)
  2. List Bedrock foundation models in the configured region
  3. Invoke the configured embedding model with a tiny input
  4. Invoke the configured text model with a tiny prompt

Run via:
  make smoke
or:
  cd backend && uv run python scripts/bedrock_smoke_test.py

A non-zero exit status indicates failure; the failing step is printed
clearly so it's obvious whether to fix credentials, region, or model
access in the Bedrock console.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running this script directly with `python scripts/bedrock_smoke_test.py`
# without installing the package — handy when iterating locally.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boto3  # noqa: E402
from botocore.exceptions import ClientError, NoCredentialsError  # noqa: E402

from app.config import settings  # noqa: E402


def _print_step(label: str) -> None:
    print(f"\n--- {label} ---")


def check_credentials() -> bool:
    _print_step("AWS credentials")
    try:
        sts = boto3.client("sts", region_name=settings.aws_region)
        identity = sts.get_caller_identity()
        print(f"  account: {identity['Account']}")
        print(f"  arn:     {identity['Arn']}")
        return True
    except NoCredentialsError:
        print("  FAIL: no credentials. Set AWS_* env vars or run `aws configure`.")
        return False
    except ClientError as e:
        print(f"  FAIL: {e}")
        return False


def check_bedrock_list() -> bool:
    _print_step(f"Bedrock list models in {settings.aws_region}")
    try:
        client = boto3.client("bedrock", region_name=settings.aws_region)
        resp = client.list_foundation_models()
        ids = {m["modelId"] for m in resp.get("modelSummaries", [])}
        print(f"  {len(ids)} models reachable")
        for model_id in (settings.bedrock_text_model_id, settings.bedrock_embedding_model_id):
            marker = "OK  " if model_id in ids else "WARN"
            print(f"  [{marker}] {model_id}")
        return True
    except ClientError as e:
        print(f"  FAIL: {e.response['Error']['Code']}: {e.response['Error']['Message']}")
        return False


def check_embedding_invoke() -> bool:
    _print_step(f"Invoke embedding model: {settings.bedrock_embedding_model_id}")
    try:
        rt = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        body = json.dumps({"inputText": "hello bedrock"})
        resp = rt.invoke_model(modelId=settings.bedrock_embedding_model_id, body=body)
        payload = json.loads(resp["body"].read())
        dims = len(payload.get("embedding", []))
        print(f"  OK: returned vector with {dims} dimensions")
        return dims > 0
    except ClientError as e:
        print(f"  FAIL: {e.response['Error']['Code']}: {e.response['Error']['Message']}")
        return False


def check_text_invoke() -> bool:
    _print_step(f"Invoke text model: {settings.bedrock_text_model_id}")
    try:
        rt = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 32,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            }
        )
        resp = rt.invoke_model(modelId=settings.bedrock_text_model_id, body=body)
        payload = json.loads(resp["body"].read())
        text = payload["content"][0]["text"]
        print(f"  OK: model responded with {text!r}")
        return True
    except ClientError as e:
        print(f"  FAIL: {e.response['Error']['Code']}: {e.response['Error']['Message']}")
        return False


def main() -> int:
    print(f"Region:           {settings.aws_region}")
    print(f"Text model:       {settings.bedrock_text_model_id}")
    print(f"Embedding model:  {settings.bedrock_embedding_model_id}")

    if not check_credentials():
        return 1
    if not check_bedrock_list():
        return 1
    ok = True
    ok &= check_embedding_invoke()
    ok &= check_text_invoke()
    print()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
