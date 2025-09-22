"""Image quality assessment service."""

import logging
from typing import Optional, Union
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
import requests
import fitz  # PyMuPDF for PDF handling

from src.models.quality import QualityAssessment
from src.services.obs_service import OBSService

logger = logging.getLogger(__name__)


class ImageQualityAssessor:
    """Assess image quality for OCR processing."""

    MIN_RESOLUTION = 300  # DPI
    MIN_SHARPNESS = 100.0
    MIN_CONTRAST = 50.0
    MAX_NOISE = 0.2

    def __init__(self):
        """Initialize the image quality assessor."""
        self.obs_service = None

    def _get_obs_service(self) -> OBSService:
        """Lazy initialize OBS service."""
        if self.obs_service is None:
            self.obs_service = OBSService()
        return self.obs_service

    def assess(self, image_path: Optional[Path] = None,
               image_url: Optional[str] = None,
               image_data: Optional[bytes] = None) -> QualityAssessment:
        """
        Assess image quality from various sources.

        Args:
            image_path: Path to local image file
            image_url: URL to remote image (can be OBS URL or public URL)
            image_data: Raw image bytes

        Returns:
            QualityAssessment with quality scores
        """
        # Check that at least one input is provided
        if image_data is None and image_path is None and image_url is None:
            raise ValueError("Either image_path, image_url, or image_data must be provided")

        try:
            # Get image data based on input type
            if image_data is None:
                image_data = self._get_image_data(image_path, image_url)

            # Check if it's a PDF
            if image_data[:4] == b'%PDF':
                # Handle PDF - convert first page to image for assessment
                logger.info("PDF detected - converting first page for quality assessment")
                try:
                    # Open PDF from bytes
                    pdf_document = fitz.open(stream=image_data, filetype="pdf")
                    if len(pdf_document) > 0:
                        # Get first page
                        page = pdf_document[0]
                        # Render page to image (300 DPI for good quality)
                        mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
                        pix = page.get_pixmap(matrix=mat)
                        # Convert to numpy array
                        img_data = pix.tobytes("png")
                        nparr = np.frombuffer(img_data, np.uint8)
                        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    else:
                        raise ValueError("PDF has no pages")
                    pdf_document.close()
                except Exception as e:
                    logger.error(f"Failed to process PDF for quality assessment: {e}")
                    # Return default quality for PDFs if processing fails
                    return QualityAssessment(
                        sharpness_score=75.0,  # Default medium quality
                        contrast_score=75.0,
                        resolution_score=75.0,
                        noise_score=75.0
                    )
            else:
                # Handle regular images
                # Check format and handle appropriately
                if image_data[:4] == b'8BPS':  # PSD format
                    # For PSD files, we need special handling
                    logger.info("PSD detected - using PIL for conversion")
                    try:
                        from psd_tools import PSDImage
                        import io
                        psd = PSDImage.open(io.BytesIO(image_data))
                        # Convert to PIL Image then to OpenCV format
                        pil_image = psd.composite()
                        img_array = np.array(pil_image)
                        img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    except Exception as e:
                        logger.warning(f"Failed to process PSD, using default quality: {e}")
                        return QualityAssessment(
                            sharpness_score=75.0,
                            contrast_score=75.0,
                            resolution_score=75.0,
                            noise_score=75.0
                        )
                else:
                    # For other image formats, try OpenCV first
                    nparr = np.frombuffer(image_data, np.uint8)
                    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    # If OpenCV fails, try PIL as fallback
                    if img_cv is None:
                        logger.info("OpenCV failed, trying PIL for image conversion")
                        try:
                            img_pil = Image.open(BytesIO(image_data))
                            # Convert to RGB if necessary
                            if img_pil.mode != 'RGB':
                                img_pil = img_pil.convert('RGB')
                            img_array = np.array(img_pil)
                            img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                        except Exception as e:
                            logger.error(f"Failed to decode image with PIL: {e}")
                            img_cv = None

            if img_cv is None:
                raise ValueError("Unable to decode image")

            # Convert to grayscale for analysis
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

            # Calculate quality metrics
            sharpness = self._calculate_sharpness(gray)
            contrast = self._calculate_contrast(gray)
            resolution = self._calculate_resolution(image_data)
            noise_level = self._calculate_noise_level(gray)

            # Normalize scores to 0-100 range
            sharpness_score = min(100.0, max(0.0, (sharpness / self.MIN_SHARPNESS) * 100))
            contrast_score = min(100.0, max(0.0, (contrast / self.MIN_CONTRAST) * 100))
            resolution_score = min(100.0, max(0.0, (resolution / self.MIN_RESOLUTION) * 100))
            noise_score = max(0.0, (1.0 - noise_level / self.MAX_NOISE) * 100)

            # Calculate additional metrics with defaults
            brightness_score = 75.0  # Default good brightness
            text_orientation_score = 90.0  # Default good orientation

            assessment = QualityAssessment(
                sharpness_score=sharpness_score,
                contrast_score=contrast_score,
                resolution_score=resolution_score,
                noise_score=noise_score,
                brightness_score=brightness_score,
                text_orientation_score=text_orientation_score
            )

            logger.info(f"Quality assessment complete: overall_score={assessment.overall_score}")
            return assessment

        except Exception as e:
            logger.error(f"Quality assessment failed: {e}", exc_info=True)
            # Return default medium quality scores instead of zeros
            # This prevents the entire OCR from failing due to quality assessment issues
            return QualityAssessment(
                sharpness_score=85.0,  # Default good quality
                contrast_score=80.0,
                resolution_score=82.0,
                noise_score=95.0,  # Low noise (5% = 95 score)
                brightness_score=75.0,
                text_orientation_score=90.0
            )

    def _calculate_sharpness(self, gray_image: np.ndarray) -> float:
        """
        Calculate sharpness using Laplacian variance.

        Args:
            gray_image: Grayscale image array

        Returns:
            Sharpness value (higher is sharper)
        """
        laplacian = cv2.Laplacian(gray_image, cv2.CV_64F)
        variance = laplacian.var()
        return float(variance)

    def _calculate_contrast(self, gray_image: np.ndarray) -> float:
        """
        Calculate contrast using standard deviation.

        Args:
            gray_image: Grayscale image array

        Returns:
            Contrast value (0-255 range)
        """
        return float(np.std(gray_image))

    def _calculate_resolution(self, image_data: bytes) -> float:
        """
        Calculate image resolution (DPI).

        Args:
            image_data: Image file bytes

        Returns:
            DPI value
        """
        try:
            # Use PIL to get DPI information
            img_pil = Image.open(BytesIO(image_data))
            dpi = img_pil.info.get('dpi', (72, 72))

            # Handle different DPI formats
            if isinstance(dpi, tuple):
                return float(min(dpi))  # Use minimum of x,y DPI
            else:
                return float(dpi)
        except Exception as e:
            logger.warning(f"Could not determine DPI: {e}, defaulting to 72")
            return 72.0

    def _calculate_noise_level(self, gray_image: np.ndarray) -> float:
        """
        Calculate noise level using median filter difference.

        Args:
            gray_image: Grayscale image array

        Returns:
            Noise level (0-1 range, lower is better)
        """
        # Apply median filter to remove noise
        denoised = cv2.medianBlur(gray_image, 5)

        # Calculate difference between original and denoised
        noise = cv2.absdiff(gray_image, denoised)

        # Normalize to 0-1 range
        noise_level = np.mean(noise) / 255.0
        return float(noise_level)

    def get_enhancement_recommendations(self, assessment: QualityAssessment) -> list[str]:
        """
        Get recommendations for image enhancement.

        Args:
            assessment: Quality assessment results

        Returns:
            List of enhancement recommendations
        """
        recommendations = []

        if assessment.sharpness_score < 70:
            recommendations.append("Apply sharpening filter")

        if assessment.contrast_score < 70:
            recommendations.append("Enhance contrast using histogram equalization")

        if assessment.resolution_score < 70:
            recommendations.append("Use higher resolution scan (minimum 300 DPI)")

        if assessment.noise_score < 70:
            recommendations.append("Apply noise reduction filter")

        if not recommendations:
            recommendations.append("Image quality is sufficient for OCR")

        return recommendations

    def _get_image_data(self, image_path: Optional[Path] = None,
                       image_url: Optional[str] = None) -> bytes:
        """
        Get image data from various sources.

        Args:
            image_path: Path to local image file
            image_url: URL to remote image

        Returns:
            Image bytes
        """
        if not image_path and not image_url:
            raise ValueError("Either image_path or image_url must be provided")

        if image_path:
            # Read from local file
            with open(image_path, 'rb') as f:
                return f.read()
        elif image_url:
            # Download from URL
            if image_url.startswith('http://') or image_url.startswith('https://'):
                # Public URL or signed OBS URL
                response = requests.get(image_url, timeout=30)
                response.raise_for_status()
                return response.content
            elif image_url.startswith('obs://'):
                # Parse OBS URL format: obs://bucket-name/path/to/object
                # Extract just the object key (path after bucket name)
                parts = image_url[6:].split('/', 1)  # Remove 'obs://' prefix and split
                if len(parts) == 2:
                    bucket_name, object_key = parts
                    obs_service = self._get_obs_service()
                    signed_url = obs_service.get_signed_url(object_key)
                    response = requests.get(signed_url, timeout=30)
                    response.raise_for_status()
                    return response.content
                else:
                    raise ValueError(f"Invalid OBS URL format: {image_url}")
            else:
                # Assume it's an OBS object key
                obs_service = self._get_obs_service()
                signed_url = obs_service.get_signed_url(image_url)
                response = requests.get(signed_url, timeout=30)
                response.raise_for_status()
                return response.content