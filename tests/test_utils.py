"""Tests for lambda/utils.py."""

import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# utils is importable because conftest.py adds the lambda/ dir to sys.path
import utils


class TestCreatePresignedUrl:
    def test_happy_path(self):
        """Returns a presigned URL when S3 call succeeds."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/signed"

        with patch("boto3.client", return_value=mock_client), \
             patch.dict(os.environ, {"S3_PERSISTENCE_BUCKET": "test-bucket"}):
            result = utils.create_presigned_url("my-object-key")

        assert result == "https://s3.example.com/signed"
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "my-object-key"},
            ExpiresIn=60,
        )

    def test_client_error_returns_none(self):
        """Returns None when S3 raises ClientError."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}},
            "GeneratePresignedUrl",
        )

        with patch("boto3.client", return_value=mock_client), \
             patch.dict(os.environ, {"S3_PERSISTENCE_BUCKET": "test-bucket"}):
            result = utils.create_presigned_url("my-object-key")

        assert result is None

    def test_missing_env_var(self):
        """When S3_PERSISTENCE_BUCKET is not set, bucket_name is None."""
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/signed"

        env = os.environ.copy()
        env.pop("S3_PERSISTENCE_BUCKET", None)

        with patch("boto3.client", return_value=mock_client), \
             patch.dict(os.environ, env, clear=True):
            result = utils.create_presigned_url("my-object-key")

        # Still calls S3 with None bucket — no crash, returns URL
        assert result == "https://s3.example.com/signed"
        call_args = mock_client.generate_presigned_url.call_args
        assert call_args[1]["Params"]["Bucket"] is None
