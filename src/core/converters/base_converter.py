"""
Base format converter class for document processing
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Any, Dict
from PIL import Image
import cv2
import numpy as np
import io
import logging

logger = logging.getLogger(__name__)


class BaseFormatConverter(ABC):
    """
    Abstract base class for all format converters
    Provides common functionality for image processing
    """

    def __init__(self):
        self.format_name = None
        self.supports_multi_page = False
        self.requires_special_handling = False

    @abstractmethod
    def convert_to_pil(self, file_data: bytes) -> Image.Image:
        """
        Convert file data to PIL Image
        Must be implemented by each converter
        """
        pass

    def auto_rotate(self, image: Image.Image, confidence_threshold: float = 0.8) -> Image.Image:
        """
        Automatically detect and correct image rotation using OpenCV
        """
        try:
            # Convert PIL to OpenCV format
            cv_image = self._pil_to_cv2(image)

            # Detect rotation angle
            angle = self.detect_rotation(cv_image)

            if abs(angle) > 1:  # Only rotate if angle is significant
                logger.info(f"Auto-rotating image by {angle} degrees")
                rotated = self._rotate_image(image, angle)
                return rotated

            return image

        except Exception as e:
            logger.warning(f"Auto-rotation failed: {e}")
            return image

    def detect_rotation(self, cv_image: np.ndarray) -> float:
        """
        Detect text rotation angle using OpenCV
        Returns rotation angle in degrees
        """
        try:
            # Convert to grayscale if needed
            if len(cv_image.shape) == 3:
                gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            else:
                gray = cv_image

            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)

            # Detect lines using Hough transform
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)

            if lines is None:
                return 0.0

            # Calculate angles of detected lines
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                angles.append(angle)

            if not angles:
                return 0.0

            # Get the median angle
            median_angle = np.median(angles)

            # Normalize to [-45, 45] range
            if median_angle > 45:
                median_angle -= 90
            elif median_angle < -45:
                median_angle += 90

            return float(median_angle)

        except Exception as e:
            logger.debug(f"Rotation detection failed: {e}")
            return 0.0

    def detect_text_orientation(self, image: Image.Image) -> str:
        """
        Detect if text is upside down or sideways
        Returns: 'normal', 'rotated_90', 'rotated_180', 'rotated_270'
        """
        try:
            # Try to import pytesseract (optional dependency)
            try:
                import pytesseract
            except ImportError:
                logger.debug("pytesseract not available, skipping text orientation detection")
                return 'normal'

            osd = pytesseract.image_to_osd(image)
            rotation = 0

            for line in osd.split('\n'):
                if 'Rotate:' in line:
                    rotation = int(line.split(':')[1].strip())
                    break

            if rotation == 0:
                return 'normal'
            elif rotation == 90:
                return 'rotated_90'
            elif rotation == 180:
                return 'rotated_180'
            elif rotation == 270:
                return 'rotated_270'
            else:
                return 'normal'

        except Exception as e:
            logger.debug(f"Text orientation detection failed: {e}")
            return 'normal'

    def enhance_image_quality(self, image: Image.Image) -> Image.Image:
        """
        Enhance image quality for better OCR results
        """
        try:
            # Convert to OpenCV format
            cv_image = self._pil_to_cv2(image)

            # Convert to grayscale
            if len(cv_image.shape) == 3:
                gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            else:
                gray = cv_image

            # Apply denoising
            denoised = cv2.fastNlMeansDenoising(gray)

            # Apply adaptive thresholding for better text clarity
            enhanced = cv2.adaptiveThreshold(
                denoised, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )

            # Convert back to PIL
            return Image.fromarray(enhanced)

        except Exception as e:
            logger.warning(f"Image enhancement failed: {e}")
            return image

    def resize_for_ocr(self, image: Image.Image, target_dpi: int = 300) -> Image.Image:
        """
        Resize image to optimal DPI for OCR
        """
        try:
            # Get current size
            width, height = image.size

            # Calculate scale factor for target DPI (assuming 72 DPI default)
            current_dpi = 72  # Default screen DPI
            scale_factor = target_dpi / current_dpi

            # Don't upscale too much (max 2x)
            scale_factor = min(scale_factor, 2.0)

            if scale_factor > 1.1:  # Only resize if significant
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)

                # Use high-quality resampling
                resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                return resized

            return image

        except Exception as e:
            logger.warning(f"Image resizing failed: {e}")
            return image

    def validate_image(self, image: Image.Image) -> Tuple[bool, Optional[str]]:
        """
        Validate image for OCR processing
        Returns: (is_valid, error_message)
        """
        width, height = image.size

        # Check minimum dimensions
        if width < 15 or height < 15:
            return False, f"Image too small: {width}x{height} (minimum 15x15)"

        # Check maximum dimensions
        if width > 30000 or height > 30000:
            return False, f"Image too large: {width}x{height} (maximum 30000x30000)"

        # Check aspect ratio (not too extreme)
        aspect_ratio = max(width, height) / min(width, height)
        if aspect_ratio > 100:
            return False, f"Extreme aspect ratio: {aspect_ratio:.1f}:1"

        return True, None

    def get_metadata(self, image: Image.Image) -> Dict[str, Any]:
        """
        Extract metadata from image
        """
        return {
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "format": image.format,
            "info": image.info,
            "has_transparency": image.mode in ('RGBA', 'LA', 'P') and 'transparency' in image.info
        }

    # Helper methods

    def _pil_to_cv2(self, pil_image: Image.Image) -> np.ndarray:
        """Convert PIL Image to OpenCV format"""
        # Convert to RGB if necessary
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')

        # Convert to numpy array
        cv_image = np.array(pil_image)

        # Convert RGB to BGR for OpenCV
        cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)

        return cv_image

    def _cv2_to_pil(self, cv_image: np.ndarray) -> Image.Image:
        """Convert OpenCV image to PIL format"""
        # Convert BGR to RGB
        if len(cv_image.shape) == 3:
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

        return Image.fromarray(cv_image)

    def _rotate_image(self, image: Image.Image, angle: float) -> Image.Image:
        """Rotate image by given angle"""
        # Use PIL's rotate with expand to avoid clipping
        rotated = image.rotate(-angle, expand=True, fillcolor='white')
        return rotated

    def process_image(
        self,
        file_data: bytes,
        auto_rotate: bool = True,
        enhance_quality: bool = False,
        resize_for_ocr_flag: bool = False
    ) -> Tuple[Image.Image, Dict[str, Any]]:
        """
        Complete processing pipeline for image conversion
        Returns: (processed_image, metadata)
        """
        # Convert to PIL
        image = self.convert_to_pil(file_data)

        metadata = self.get_metadata(image)
        metadata['processing_steps'] = []

        # Validate
        is_valid, error = self.validate_image(image)
        if not is_valid:
            raise ValueError(f"Image validation failed: {error}")

        # Auto-rotate if requested
        if auto_rotate:
            original_orientation = self.detect_text_orientation(image)
            metadata['original_orientation'] = original_orientation

            if original_orientation != 'normal':
                image = self.auto_rotate(image)
                metadata['processing_steps'].append('auto_rotation')
                metadata['auto_rotation_applied'] = True

        # Enhance quality if requested
        if enhance_quality:
            image = self.enhance_image_quality(image)
            metadata['processing_steps'].append('quality_enhancement')

        # Resize for OCR if requested
        if resize_for_ocr_flag:
            image = self.resize_for_ocr(image)
            metadata['processing_steps'].append('resize_for_ocr')

        # Update final dimensions
        metadata['final_width'] = image.width
        metadata['final_height'] = image.height

        return image, metadata