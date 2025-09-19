import base64
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

import requests
from PIL import Image
import io

from src.core.config import settings
from src.models.ocr_models import OCRResponse

logger = logging.getLogger(__name__)


class HuaweiOCRService:
    def __init__(self):
        self.endpoint = settings.huawei_ocr_endpoint
        self.access_key = settings.huawei_access_key
        self.secret_key = settings.huawei_secret_key
        self.project_id = settings.huawei_project_id
        self.region = settings.huawei_region
        self.timeout = settings.api_timeout
        self._token = None
        self._token_expiry = None

    def _get_iam_token(self) -> str:
        """Get or refresh IAM token for authentication"""

        # Check if we have a valid cached token
        if self._token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._token

        # Get new token
        iam_endpoint = f"https://iam.{self.region}.myhuaweicloud.com"
        url = f"{iam_endpoint}/v3/auth/tokens"

        payload = {
            "auth": {
                "identity": {
                    "methods": ["hw_ak_sk"],
                    "hw_ak_sk": {
                        "access": {
                            "key": self.access_key
                        },
                        "secret": {
                            "key": self.secret_key
                        }
                    }
                },
                "scope": {
                    "project": {
                        "id": self.project_id
                    }
                }
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        try:
            logger.info("Requesting new IAM token")
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 201:
                self._token = response.headers.get('X-Subject-Token')
                # Token is valid for 24 hours, but we'll refresh after 23 hours
                self._token_expiry = datetime.now() + timedelta(hours=23)
                logger.info("IAM token obtained successfully")
                return self._token
            else:
                logger.error(f"Failed to get IAM token: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get IAM token: {response.status_code} - {response.text}")

        except requests.RequestException as e:
            logger.error(f"Error requesting IAM token: {e}")
            raise

    def _prepare_image(self, image_path: Path) -> str:
        try:
            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                max_size = settings.image_optimal_size_mb * 1024 * 1024

                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG', quality=95)
                img_bytes = img_byte_arr.getvalue()

                if len(img_bytes) > max_size:
                    quality = 95
                    while len(img_bytes) > max_size and quality > 30:
                        quality -= 5
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='JPEG', quality=quality)
                        img_bytes = img_byte_arr.getvalue()

                return base64.b64encode(img_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Error preparing image: {e}")
            raise

    def process_document(self, image_path: Path = None, image_url: str = None, options: Optional[Dict[str, Any]] = None) -> OCRResponse:
        """
        Process a document using OCR

        Args:
            image_path: Path to local image file (for base64 mode)
            image_url: URL to remote image (for URL mode)
            options: Additional OCR options

        Returns:
            OCRResponse object with recognition results
        """
        try:
            if not image_path and not image_url:
                raise ValueError("Either image_path or image_url must be provided")

            url = settings.ocr_url

            # Build payload based on input type
            if image_url:
                # URL mode
                payload = {
                    "url": image_url
                }
            else:
                # Base64 mode
                image_base64 = self._prepare_image(image_path)
                payload = {
                    "data": image_base64
                }

            if options:
                payload.update(options)

            # Get IAM token for authentication
            token = self._get_iam_token()

            headers = {
                "Content-Type": "application/json",
                "X-Auth-Token": token
            }

            logger.info(f"Sending OCR request for image: {image_path if image_path else image_url}")
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.error(f"OCR API error: {response.status_code} - {response.text}")
                raise Exception(f"OCR API error: {response.status_code} - {response.text}")

            response_data = response.json()
            logger.info(f"OCR processing successful for: {image_path}")

            return OCRResponse.model_validate(response_data)

        except requests.RequestException as e:
            logger.error(f"Request error during OCR processing: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during OCR processing: {e}")
            raise

    def extract_text_from_response(self, ocr_response: OCRResponse) -> str:
        texts = []

        if ocr_response.result:
            for result in ocr_response.result:
                if result.ocr_result and result.ocr_result.words_block_list:
                    for word_block in result.ocr_result.words_block_list:
                        texts.append(word_block.words)

        return "\n".join(texts)

    def get_average_confidence(self, ocr_response: OCRResponse) -> float:
        confidences = []

        if ocr_response.result:
            for result in ocr_response.result:
                if result.ocr_result and result.ocr_result.words_block_list:
                    for word_block in result.ocr_result.words_block_list:
                        if word_block.confidence is not None:
                            confidences.append(word_block.confidence)

        return sum(confidences) / len(confidences) if confidences else 0.0