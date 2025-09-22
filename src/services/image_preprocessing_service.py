"""
Image preprocessing service for OCR quality improvement.
Works with ImageQualityAssessor to apply appropriate enhancements.
Supports all formats: PNG, JPG/JPEG, BMP, GIF, TIFF, WebP, PCX, ICO, PSD, PDF
"""

import logging
from typing import Optional, Tuple, List
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
import fitz  # PyMuPDF for PDF handling

from src.models.quality import QualityAssessment

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    Preprocesses images to improve OCR accuracy.
    Uses OpenCV for image enhancement operations.
    """

    def __init__(self):
        """Initialize the image preprocessor."""
        self.logger = logging.getLogger(__name__)

    def _load_image_safely(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """
        Safely load image from bytes, handling all supported formats.
        Returns OpenCV-compatible BGR image array or None if failed.
        """
        # First try OpenCV (handles most common formats)
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                return img
        except Exception as e:
            logger.debug(f"OpenCV decode failed: {e}")

        # Try PIL as fallback (handles more formats like WebP, PCX, ICO)
        try:
            img_pil = Image.open(BytesIO(image_bytes))
            # Convert to RGB if necessary
            if img_pil.mode != 'RGB':
                img_pil = img_pil.convert('RGB')
            # Convert to numpy array and BGR for OpenCV
            img_array = np.array(img_pil)
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            return img_bgr
        except Exception as e:
            logger.debug(f"PIL decode failed: {e}")

        # Special handling for PSD files
        if image_bytes[:4] == b'8BPS':
            try:
                from psd_tools import PSDImage
                import io
                psd = PSDImage.open(io.BytesIO(image_bytes))
                pil_image = psd.composite()
                if pil_image:
                    img_array = np.array(pil_image)
                    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    return img_bgr
            except Exception as e:
                logger.debug(f"PSD decode failed: {e}")

        logger.error("Failed to decode image with any method")
        return None

    def _save_image_safely(self, img: np.ndarray, original_format_hint: Optional[bytes] = None) -> bytes:
        """
        Safely save image to bytes, preserving format if possible.
        """
        # Default to PNG for best quality
        format_type = 'PNG'

        # Try to preserve original format
        if original_format_hint:
            if original_format_hint[:2] == b'\xff\xd8':
                format_type = 'JPEG'
            elif original_format_hint[:2] == b'BM':
                format_type = 'BMP'
            elif original_format_hint[:6] in (b'GIF87a', b'GIF89a'):
                format_type = 'GIF'
            elif original_format_hint[:4] in (b'II*\x00', b'MM\x00*'):
                format_type = 'TIFF'
            elif original_format_hint[:4] == b'RIFF' and len(original_format_hint) > 12 and original_format_hint[8:12] == b'WEBP':
                format_type = 'WEBP'

        # Convert back to bytes
        success, buffer = cv2.imencode(f'.{format_type.lower()}', img)
        if success:
            return buffer.tobytes()
        else:
            # Fallback to PNG if format fails
            success, buffer = cv2.imencode('.png', img)
            if success:
                return buffer.tobytes()
            else:
                raise ValueError("Failed to encode image")

    def auto_rotate(self, image_bytes: bytes) -> bytes:
        """
        Automatically detect and correct image rotation.

        Args:
            image_bytes: Input image as bytes

        Returns:
            Rotated image as bytes
        """
        try:
            # Load image safely (handles all formats)
            img = self._load_image_safely(image_bytes)
            if img is None:
                logger.error("Failed to decode image for rotation")
                return image_bytes

            # Convert to grayscale for text detection
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Detect edges
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)

            # Detect lines using Hough transform
            lines = cv2.HoughLines(edges, 1, np.pi/180, 200)

            if lines is not None and len(lines) > 0:
                # Calculate dominant angle
                angles = []
                for line in lines[:20]:  # Use first 20 lines
                    rho, theta = line[0]
                    angle = (theta * 180 / np.pi) - 90
                    if -45 <= angle <= 45:  # Filter reasonable angles
                        angles.append(angle)

                if angles:
                    # Get median angle
                    rotation_angle = np.median(angles)

                    # Apply rotation if significant
                    if abs(rotation_angle) > 0.5:
                        logger.info(f"Rotating image by {rotation_angle:.2f} degrees")

                        # Get rotation matrix
                        height, width = img.shape[:2]
                        center = (width // 2, height // 2)
                        matrix = cv2.getRotationMatrix2D(center, rotation_angle, 1.0)

                        # Calculate new dimensions to avoid cropping
                        cos = np.abs(matrix[0, 0])
                        sin = np.abs(matrix[0, 1])
                        new_width = int((height * sin) + (width * cos))
                        new_height = int((height * cos) + (width * sin))

                        # Adjust rotation matrix for new dimensions
                        matrix[0, 2] += (new_width / 2) - center[0]
                        matrix[1, 2] += (new_height / 2) - center[1]

                        # Rotate image
                        rotated = cv2.warpAffine(img, matrix, (new_width, new_height),
                                                flags=cv2.INTER_LINEAR,
                                                borderMode=cv2.BORDER_CONSTANT,
                                                borderValue=(255, 255, 255))

                        # Convert back to bytes, preserving format
                        return self._save_image_safely(rotated, image_bytes)

            logger.debug("No rotation needed")
            return image_bytes

        except Exception as e:
            logger.error(f"Auto-rotation failed: {e}")
            return image_bytes

    def enhance_contrast(self, image_bytes: bytes) -> bytes:
        """
        Enhance image contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization).

        Args:
            image_bytes: Input image as bytes

        Returns:
            Contrast-enhanced image as bytes
        """
        try:
            # Load image safely (handles all formats)
            img = self._load_image_safely(image_bytes)
            if img is None:
                logger.error("Failed to decode image for contrast enhancement")
                return image_bytes

            # Convert to LAB color space for better contrast enhancement
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

            # Split channels
            l, a, b = cv2.split(lab)

            # Apply CLAHE to L channel
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)

            # Merge channels
            enhanced_lab = cv2.merge([l, a, b])

            # Convert back to BGR
            enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

            # Convert back to bytes, preserving format
            result = self._save_image_safely(enhanced, image_bytes)
            logger.info("Contrast enhanced successfully")
            return result

        except Exception as e:
            logger.error(f"Contrast enhancement failed: {e}")
            return image_bytes

    def reduce_noise(self, image_bytes: bytes) -> bytes:
        """
        Reduce image noise using bilateral filtering.

        Args:
            image_bytes: Input image as bytes

        Returns:
            Denoised image as bytes
        """
        try:
            # Load image safely (handles all formats)
            img = self._load_image_safely(image_bytes)
            if img is None:
                logger.error("Failed to decode image for noise reduction")
                return image_bytes

            # Apply bilateral filter - preserves edges while reducing noise
            denoised = cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)

            # Convert back to bytes, preserving format
            result = self._save_image_safely(denoised, image_bytes)
            logger.info("Noise reduced successfully")
            return result

        except Exception as e:
            logger.error(f"Noise reduction failed: {e}")
            return image_bytes

    def sharpen(self, image_bytes: bytes) -> bytes:
        """
        Sharpen image using unsharp masking.

        Args:
            image_bytes: Input image as bytes

        Returns:
            Sharpened image as bytes
        """
        try:
            # Load image safely (handles all formats)
            img = self._load_image_safely(image_bytes)
            if img is None:
                logger.error("Failed to decode image for sharpening")
                return image_bytes

            # Create sharpening kernel
            kernel = np.array([
                [0, -1, 0],
                [-1, 5, -1],
                [0, -1, 0]
            ])

            # Apply sharpening
            sharpened = cv2.filter2D(img, -1, kernel)

            # Convert back to bytes, preserving format
            result = self._save_image_safely(sharpened, image_bytes)
            logger.info("Image sharpened successfully")
            return result

        except Exception as e:
            logger.error(f"Sharpening failed: {e}")
            return image_bytes

    def binarize(self, image_bytes: bytes, adaptive: bool = True) -> bytes:
        """
        Convert image to binary (black and white) for better text recognition.

        Args:
            image_bytes: Input image as bytes
            adaptive: Use adaptive thresholding if True, else use Otsu's method

        Returns:
            Binarized image as bytes
        """
        try:
            # Load image safely and convert to grayscale
            img_color = self._load_image_safely(image_bytes)
            if img_color is None:
                logger.error("Failed to decode image for binarization")
                return image_bytes
            img = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

            if adaptive:
                # Adaptive thresholding
                binary = cv2.adaptiveThreshold(
                    img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 11, 2
                )
            else:
                # Otsu's thresholding
                _, binary = cv2.threshold(
                    img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                )

            # Convert back to bytes, preserving format
            # Note: For binary images, PNG is usually best
            success, buffer = cv2.imencode('.png', binary)
            if success:
                logger.info("Image binarized successfully")
                return buffer.tobytes()
            return image_bytes

        except Exception as e:
            logger.error(f"Binarization failed: {e}")
            return image_bytes

    def deskew(self, image_bytes: bytes) -> bytes:
        """
        Correct image skew using projection profile analysis.

        Args:
            image_bytes: Input image as bytes

        Returns:
            Deskewed image as bytes
        """
        try:
            # Load image safely (handles all formats)
            img = self._load_image_safely(image_bytes)
            if img is None:
                logger.error("Failed to decode image for deskewing")
                return image_bytes

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Find all contours
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)

            if lines is not None:
                angles = []
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                    if -45 <= angle <= 45:
                        angles.append(angle)

                if angles:
                    median_angle = np.median(angles)

                    if abs(median_angle) > 0.5:
                        logger.info(f"Deskewing by {median_angle:.2f} degrees")

                        # Rotate to correct skew
                        height, width = img.shape[:2]
                        center = (width // 2, height // 2)
                        matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)

                        deskewed = cv2.warpAffine(
                            img, matrix, (width, height),
                            flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT,
                            borderValue=(255, 255, 255)
                        )

                        # Convert back to bytes, preserving format
                        return self._save_image_safely(deskewed, image_bytes)

            logger.debug("No deskewing needed")
            return image_bytes

        except Exception as e:
            logger.error(f"Deskewing failed: {e}")
            return image_bytes

    def preprocess(self, image_bytes: bytes, assessment: Optional[QualityAssessment] = None, enable_preprocessing: bool = True) -> bytes:
        """
        Apply preprocessing based on quality assessment.
        Automatically handles all supported formats including PDFs.

        Args:
            image_bytes: Input file as bytes (any supported format)
            assessment: Quality assessment results
            enable_preprocessing: If True, apply preprocessing to all formats (default True)

        Returns:
            Preprocessed file as bytes
        """
        try:
            # If preprocessing is disabled, return original
            if not enable_preprocessing:
                logger.info("Preprocessing disabled - returning original file")
                return image_bytes

            # Check if it's a PDF
            if image_bytes[:4] == b'%PDF':
                logger.info("PDF detected - applying PDF preprocessing")
                return self._preprocess_pdf(image_bytes, assessment)

            processed = image_bytes

            if assessment is None:
                # Apply default preprocessing if no assessment provided
                logger.info("Applying default preprocessing")
                processed = self.auto_rotate(processed)
                processed = self.reduce_noise(processed)
                processed = self.enhance_contrast(processed)
                processed = self.sharpen(processed)
            else:
                # Apply preprocessing based on assessment scores
                logger.info(f"Applying preprocessing based on assessment (overall: {assessment.overall_score:.1f})")

                # Always try auto-rotation for text documents
                processed = self.auto_rotate(processed)

                # Apply noise reduction if needed
                if assessment.noise_score < 70:
                    logger.info(f"Applying noise reduction (score: {assessment.noise_score:.1f})")
                    processed = self.reduce_noise(processed)

                # Apply contrast enhancement if needed
                if assessment.contrast_score < 70:
                    logger.info(f"Enhancing contrast (score: {assessment.contrast_score:.1f})")
                    processed = self.enhance_contrast(processed)

                # Apply sharpening if needed
                if assessment.sharpness_score < 70:
                    logger.info(f"Sharpening image (score: {assessment.sharpness_score:.1f})")
                    processed = self.sharpen(processed)

                # Apply binarization for very poor quality text
                if assessment.overall_score < 50:
                    logger.info(f"Applying binarization for poor quality (score: {assessment.overall_score:.1f})")
                    processed = self.binarize(processed)

            return processed

        except Exception as e:
            logger.error(f"Preprocessing failed: {e}")
            return image_bytes

    def _preprocess_pdf(self, pdf_bytes: bytes, assessment: Optional[QualityAssessment] = None) -> bytes:
        """
        Preprocess PDF by converting each page to image, preprocessing, and reconstructing.

        Args:
            pdf_bytes: PDF file as bytes
            assessment: Quality assessment results

        Returns:
            Preprocessed PDF as bytes
        """
        try:
            # Open PDF from bytes
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

            # Create a new PDF for the preprocessed pages
            output_pdf = fitz.open()

            logger.info(f"Processing PDF with {len(pdf_document)} pages")

            for page_num in range(len(pdf_document)):
                # Get the page
                page = pdf_document[page_num]

                # Render page to image at 300 DPI
                mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
                pix = page.get_pixmap(matrix=mat)

                # Convert to bytes for preprocessing
                img_bytes = pix.tobytes("png")

                # Preprocess the image (disable preprocessing flag to avoid recursion)
                processed_img_bytes = self.preprocess(img_bytes, assessment, enable_preprocessing=True)

                # Convert processed image back to pixmap
                processed_img = Image.open(BytesIO(processed_img_bytes))

                # Save to temporary bytes
                temp_io = BytesIO()
                processed_img.save(temp_io, format='PNG')
                temp_io.seek(0)

                # Create a new page with the processed image
                img_pdf = fitz.open(stream=temp_io.read(), filetype="png")
                output_pdf.insert_pdf(img_pdf)
                img_pdf.close()

                logger.debug(f"Preprocessed page {page_num + 1}/{len(pdf_document)}")

            # Save the output PDF to bytes
            output_bytes = output_pdf.tobytes()

            # Clean up
            pdf_document.close()
            output_pdf.close()

            logger.info(f"PDF preprocessing complete - processed {len(pdf_document)} pages")
            return output_bytes

        except Exception as e:
            logger.error(f"PDF preprocessing failed: {e}")
            return pdf_bytes

    def resize_for_ocr(self, image_bytes: bytes, target_dpi: int = 300) -> bytes:
        """
        Resize image to optimal DPI for OCR.

        Args:
            image_bytes: Input image as bytes
            target_dpi: Target DPI (default 300)

        Returns:
            Resized image as bytes
        """
        try:
            # Open with PIL to get DPI info
            img_pil = Image.open(BytesIO(image_bytes))
            current_dpi = img_pil.info.get('dpi', (72, 72))

            if isinstance(current_dpi, tuple):
                current_dpi = min(current_dpi)

            if current_dpi < target_dpi:
                # Calculate scale factor
                scale = target_dpi / current_dpi

                # Load image safely
                img_cv = self._load_image_safely(image_bytes)

                if img_cv is not None:
                    # Calculate new dimensions
                    height, width = img_cv.shape[:2]
                    new_width = int(width * scale)
                    new_height = int(height * scale)

                    # Resize with cubic interpolation for better quality
                    resized = cv2.resize(img_cv, (new_width, new_height),
                                        interpolation=cv2.INTER_CUBIC)

                    # Convert back to bytes, preserving format
                    result = self._save_image_safely(resized, image_bytes)
                    logger.info(f"Image resized from {current_dpi} to {target_dpi} DPI")
                    return result

            return image_bytes

        except Exception as e:
            logger.error(f"Resizing failed: {e}")
            return image_bytes