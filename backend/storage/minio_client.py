import io
import uuid
import json
from datetime import timedelta
from minio import Minio
from minio.error import S3Error

from core.config import settings


class MinIOClient:
    def __init__(self):
        self.client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure
        )
        self._ensure_buckets()

    def _set_private_policy(self, bucket: str):
        policy = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [
                    f"arn:aws:s3:::{bucket}",
                    f"arn:aws:s3:::{bucket}/*"
                ]
            }]
        })
        self.client.set_bucket_policy(bucket, policy)

    def _ensure_buckets(self):
        for bucket in [
            settings.minio_bucket_raw,
            settings.minio_bucket_processed,
            settings.minio_bucket_images
        ]:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
                self._set_private_policy(bucket)

    def upload_file(self, bucket: str, object_name: str, data: bytes, content_type: str) -> str:
        self.client.put_object(
            bucket_name=bucket,
            object_name=object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type
        )
        return f"{bucket}/{object_name}"

    def download_file(self, bucket: str, object_name: str) -> bytes:
        response = self.client.get_object(bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def get_presigned_url(self, bucket: str, object_name: str, expires_hours: int = 1) -> str:
        return self.client.presigned_get_object(
            bucket_name=bucket,
            object_name=object_name,
            expires=timedelta(hours=expires_hours)
        )

    def delete_object(self, bucket: str, object_name: str):
        try:
            self.client.remove_object(bucket, object_name)
        except S3Error:
            pass

    def build_object_name(self, user_id: int, subject: str, doc_type: str, filename: str) -> str:
        subject_clean = subject.replace(" ", "_") if subject else "Autre"
        type_clean = doc_type.replace(" ", "_") if doc_type else "Autre"
        unique = uuid.uuid4().hex[:8]
        return f"{user_id}/{subject_clean}/{type_clean}/{unique}_{filename}"

    def save_text(self, bucket: str, object_name: str, text: str) -> str:
        data = text.encode("utf-8")
        return self.upload_file(bucket, object_name, data, "text/plain")


minio_client = MinIOClient()
