import logging
from pathlib import Path

from obs import ObsClient

from src.core.config import settings

logger = logging.getLogger(__name__)


class OBSService:
    """Service for interacting with Huawei Cloud OBS (Object Storage Service)"""

    def __init__(self):
        self.access_key = settings.huawei_access_key
        self.secret_key = settings.huawei_secret_key
        self.endpoint = settings.obs_endpoint
        self.bucket_name = settings.obs_bucket_name
        self.obs_client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize OBS client"""
        try:
            self.obs_client = ObsClient(
                access_key_id=self.access_key,
                secret_access_key=self.secret_key,
                server=self.endpoint
            )
            logger.info(f"OBS client initialized for bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize OBS client: {e}")
            raise

    def upload_file(self, local_path: Path, object_key: str) -> bool:
        """
        Upload a file to OBS

        Args:
            local_path: Path to local file
            object_key: Object key in OBS (e.g., "OCR/document.jpg")

        Returns:
            True if upload successful, False otherwise
        """
        try:
            with open(local_path, 'rb') as file:
                resp = self.obs_client.putObject(
                    bucketName=self.bucket_name,
                    objectKey=object_key,
                    content=file
                )

            if resp.status < 300:
                logger.info(f"File uploaded successfully to OBS: {object_key}")
                return True
            else:
                logger.error(f"Failed to upload file to OBS: {resp.errorMessage}")
                return False

        except Exception as e:
            logger.error(f"Error uploading file to OBS: {e}")
            return False

    def get_signed_url(self, object_key: str, expires_in: int = 3600) -> str:
        """
        Generate a signed URL for accessing an object in OBS

        Args:
            object_key: Object key in OBS (e.g., "OCR/scanned_document.jpg")
            expires_in: URL expiration time in seconds (default 1 hour)

        Returns:
            Signed URL string
        """
        try:
            resp = self.obs_client.createSignedUrl(
                method='GET',
                bucketName=self.bucket_name,
                objectKey=object_key,
                expires=expires_in
            )

            if resp.signedUrl:
                logger.info(f"Generated signed URL for: {object_key}")
                return resp.signedUrl
            else:
                raise Exception("Failed to generate signed URL")

        except Exception as e:
            logger.error(f"Error generating signed URL: {e}")
            raise

    def get_public_url(self, object_key: str) -> str:
        """
        Get the public URL for an object (if bucket allows public access)

        Args:
            object_key: Object key in OBS

        Returns:
            Public URL string
        """
        return f"{self.endpoint}/{self.bucket_name}/{object_key}"

    def check_object_exists(self, object_key: str) -> bool:
        """
        Check if an object exists in OBS

        Args:
            object_key: Object key in OBS

        Returns:
            True if object exists, False otherwise
        """
        try:
            resp = self.obs_client.getObjectMetadata(
                bucketName=self.bucket_name,
                objectKey=object_key
            )
            return resp.status < 300

        except Exception as e:
            logger.debug(f"Object not found or error: {e}")
            return False

    def delete_object(self, object_key: str) -> bool:
        """
        Delete an object from OBS

        Args:
            object_key: Object key in OBS

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            resp = self.obs_client.deleteObject(
                bucketName=self.bucket_name,
                objectKey=object_key
            )

            if resp.status < 300:
                logger.info(f"Object deleted from OBS: {object_key}")
                return True
            else:
                logger.error(f"Failed to delete object from OBS: {resp.errorMessage}")
                return False

        except Exception as e:
            logger.error(f"Error deleting object from OBS: {e}")
            return False

    def list_objects(self, prefix: str = "OCR/", max_keys: int = 1000) -> list:
        """
        List objects in OBS bucket with given prefix

        Args:
            prefix: Object key prefix to filter (default: "OCR/")
            max_keys: Maximum number of objects to return

        Returns:
            List of object metadata including key, size, last_modified
        """
        try:
            resp = self.obs_client.listObjects(
                bucketName=self.bucket_name,
                prefix=prefix,
                max_keys=max_keys
            )

            if resp.status < 300:
                objects = []
                if resp.body.contents:
                    for obj in resp.body.contents:
                        # Skip directories (keys ending with /)
                        if not obj.key.endswith('/'):
                            objects.append({
                                'key': obj.key,
                                'size': obj.size,
                                'last_modified': obj.lastModified,
                                'etag': obj.etag
                            })

                logger.info(f"Listed {len(objects)} objects with prefix: {prefix}")
                return objects
            else:
                logger.error(f"Failed to list objects: {resp.errorMessage}")
                return []

        except Exception as e:
            logger.error(f"Error listing objects: {e}")
            return []

    def list_folders(self, prefix: str = "OCR/") -> list:
        """
        List folders (common prefixes) in OBS bucket

        Args:
            prefix: Object key prefix to search within

        Returns:
            List of folder names
        """
        try:
            resp = self.obs_client.listObjects(
                bucketName=self.bucket_name,
                prefix=prefix,
                delimiter='/',
                max_keys=1000
            )

            if resp.status < 300:
                folders = []
                if hasattr(resp.body, 'commonPrefixes') and resp.body.commonPrefixes:
                    for prefix_info in resp.body.commonPrefixes:
                        folder_name = prefix_info.prefix.rstrip('/')
                        folders.append(folder_name)

                logger.info(f"Found {len(folders)} folders")
                return folders
            else:
                logger.error(f"Failed to list folders: {resp.errorMessage}")
                return []

        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            return []

    def get_object_metadata(self, object_key: str) -> dict:
        """
        Get metadata for a specific object

        Args:
            object_key: Object key in OBS

        Returns:
            Dictionary with object metadata
        """
        try:
            resp = self.obs_client.getObjectMetadata(
                bucketName=self.bucket_name,
                objectKey=object_key
            )

            if resp.status < 300:
                return {
                    'key': object_key,
                    'size': resp.body.contentLength,
                    'content_type': resp.body.contentType,
                    'last_modified': resp.body.lastModified,
                    'etag': resp.body.etag
                }
            else:
                logger.error(f"Failed to get object metadata: {resp.errorMessage}")
                return {}

        except Exception as e:
            logger.error(f"Error getting object metadata: {e}")
            return {}

    def close(self):
        """Close OBS client connection"""
        if self.obs_client:
            self.obs_client.close()
            logger.info("OBS client connection closed")