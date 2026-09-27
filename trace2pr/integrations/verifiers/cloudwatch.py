"""AWS CloudWatch integration verifier."""
import logging

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .base import BaseVerifier, VerifyResult

logger = logging.getLogger(__name__)


class CloudWatchVerifier(BaseVerifier):
    async def verify(self, credentials: dict[str, str]) -> VerifyResult:
        access_key_id = credentials.get("aws_access_key_id")
        secret_access_key = credentials.get("aws_secret_access_key")
        region = credentials.get("aws_region", "us-east-1")

        if not access_key_id or not secret_access_key:
            return VerifyResult(False, "Missing AWS Access Key ID or Secret Access Key")

        try:
            # Create STS client to verify credentials
            session = boto3.Session(
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name=region,
            )
            sts = session.client("sts")
            
            # Get caller identity to verify credentials work
            response = sts.get_caller_identity()
            account_id = response.get("Account")
            arn = response.get("Arn")
            
            return VerifyResult(True, f"AWS verification successful: Account {account_id} ({arn})")
            
        except NoCredentialsError:
            return VerifyResult(False, "Invalid AWS credentials")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            return VerifyResult(False, f"AWS verification failed: {error_code}")
        except Exception as e:
            logger.error(f"AWS network error: {e}")
            return VerifyResult(False, f"Network error during AWS verification: {str(e)}")