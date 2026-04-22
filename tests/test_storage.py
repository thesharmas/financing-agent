"""Unit tests for financing_api.storage (GCS PDF dedup)."""

from __future__ import annotations

import base64
import hashlib
from unittest.mock import MagicMock, patch

from financing_api.storage import store_pdf


def _b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode()


class TestStorePdf:
    def test_uploads_new_pdf(self):
        data = b"%PDF-1.4 fake"
        expected_hash = hashlib.sha256(data).hexdigest()

        blob = MagicMock()
        blob.exists.return_value = False
        bucket = MagicMock(blob=MagicMock(return_value=blob))
        client = MagicMock(bucket=MagicMock(return_value=bucket))

        with patch("financing_api.storage._get_client", return_value=client):
            result = store_pdf(
                project="test-project",
                bucket_name="test-bucket",
                pdf_base64=_b64(data),
            )

        assert result.content_hash == expected_hash
        assert result.gcs_uri == f"gs://test-bucket/{expected_hash}.pdf"
        assert result.is_new is True
        blob.upload_from_string.assert_called_once_with(data, content_type="application/pdf")

    def test_dedupes_existing_pdf(self):
        data = b"%PDF-1.4 fake"
        blob = MagicMock()
        blob.exists.return_value = True
        bucket = MagicMock(blob=MagicMock(return_value=blob))
        client = MagicMock(bucket=MagicMock(return_value=bucket))

        with patch("financing_api.storage._get_client", return_value=client):
            result = store_pdf(
                project="test-project",
                bucket_name="test-bucket",
                pdf_base64=_b64(data),
            )

        assert result.is_new is False
        blob.upload_from_string.assert_not_called()
