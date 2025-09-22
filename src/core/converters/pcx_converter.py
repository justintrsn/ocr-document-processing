"""
PCX format converter for ZSoft PC Paintbrush images
"""

from PIL import Image
import io
import logging
from typing import Optional, Dict, Any
from src.core.converters.base_converter import BaseFormatConverter

logger = logging.getLogger(__name__)


class PCXFormatConverter(BaseFormatConverter):
    """
    Handles conversion for PCX (PC Paintbrush) format
    PCX is an old format but still supported by Pillow natively
    """

    def __init__(self):
        super().__init__()
        self.format_name = 'PCX'
        self.requires_special_handling = False  # Pillow handles PCX natively

    def convert_to_pil(self, file_data: bytes) -> Image.Image:
        """
        Convert PCX file to PIL Image
        PCX is supported natively by Pillow
        """
        try:
            # Open PCX with PIL
            image = Image.open(io.BytesIO(file_data))

            # Verify it's actually a PCX file
            if image.format != 'PCX':
                logger.warning(f"Expected PCX format but got {image.format}")

            # PCX files can have different color modes
            # Convert to RGB for OCR processing
            if image.mode != 'RGB':
                image = self._convert_to_rgb(image)

            # PCX files are often old scans, may benefit from enhancement
            if self._needs_enhancement(image):
                logger.info("PCX image appears to be low quality, applying enhancement")
                image = self.enhance_image_quality(image)

            return image

        except Exception as e:
            logger.error(f"Failed to convert PCX: {e}")
            raise ValueError(f"PCX conversion failed: {e}")

    def _convert_to_rgb(self, image: Image.Image) -> Image.Image:
        """
        Convert PCX image to RGB mode
        Handles various PCX color modes appropriately
        """
        original_mode = image.mode

        if image.mode == 'P':
            # Palette mode - common for PCX
            if 'transparency' in image.info:
                # Has transparency, convert via RGBA
                image = image.convert('RGBA')
                # Create white background
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                image = background
            else:
                # No transparency, direct conversion
                image = image.convert('RGB')

        elif image.mode == '1':
            # Binary (1-bit) mode - common for old PCX files
            image = image.convert('RGB')

        elif image.mode == 'L':
            # Grayscale
            image = image.convert('RGB')

        else:
            # Try direct conversion for other modes
            try:
                image = image.convert('RGB')
            except Exception as e:
                logger.warning(f"Could not convert PCX mode {original_mode} to RGB: {e}")

        logger.debug(f"Converted PCX from {original_mode} to RGB mode")
        return image

    def _needs_enhancement(self, image: Image.Image) -> bool:
        """
        Determine if PCX image needs quality enhancement
        Old PCX files often have poor quality
        """
        try:
            # Check image statistics
            import numpy as np

            # Convert to numpy array
            img_array = np.array(image)

            # Check contrast (standard deviation)
            std_dev = np.std(img_array)

            # Low contrast indicates poor quality scan
            if std_dev < 30:
                return True

            # Check if image is mostly white/black (poor scan)
            mean_value = np.mean(img_array)
            if mean_value < 50 or mean_value > 200:
                return True

            return False

        except Exception as e:
            logger.debug(f"Could not analyze PCX quality: {e}")
            return False  # Don't enhance if we can't analyze

    def validate_pcx(self, file_data: bytes) -> tuple[bool, Optional[str]]:
        """
        Validate PCX file before processing
        """
        # Check minimum size
        if len(file_data) < 128:  # PCX header is 128 bytes
            return False, "File too small to be valid PCX"

        # Check PCX magic byte (0x0A)
        if file_data[0:1] != b'\x0a':
            return False, "Not a valid PCX file (invalid magic byte)"

        # Check version (byte 1)
        version = file_data[1] if len(file_data) > 1 else 0
        valid_versions = [0, 2, 3, 4, 5]  # Valid PCX versions
        if version not in valid_versions:
            logger.warning(f"Unusual PCX version: {version}")

        # Check encoding (byte 2) - should be 1 for RLE
        encoding = file_data[2] if len(file_data) > 2 else 0
        if encoding != 1:
            logger.warning(f"Unusual PCX encoding: {encoding}")

        # Try to open with PIL to validate
        try:
            image = Image.open(io.BytesIO(file_data))

            if image.format != 'PCX':
                return False, f"File detected as {image.format}, not PCX"

            # Check dimensions
            width, height = image.size
            if width < 15 or height < 15:
                return False, f"PCX dimensions too small: {width}x{height}"

            if width > 30000 or height > 30000:
                return False, f"PCX dimensions too large: {width}x{height}"

            return True, None

        except Exception as e:
            return False, f"PCX validation failed: {str(e)}"

    def get_pcx_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """
        Extract metadata from PCX file header
        """
        metadata = {}

        try:
            # Parse PCX header (128 bytes)
            if len(file_data) >= 128:
                metadata['magic_byte'] = hex(file_data[0])
                metadata['version'] = file_data[1]
                metadata['encoding'] = file_data[2]
                metadata['bits_per_pixel'] = file_data[3]

                # Window coordinates (bytes 4-11)
                xmin = int.from_bytes(file_data[4:6], 'little')
                ymin = int.from_bytes(file_data[6:8], 'little')
                xmax = int.from_bytes(file_data[8:10], 'little')
                ymax = int.from_bytes(file_data[10:12], 'little')

                metadata['dimensions'] = {
                    'width': xmax - xmin + 1,
                    'height': ymax - ymin + 1
                }

                # DPI (bytes 12-15)
                hdpi = int.from_bytes(file_data[12:14], 'little')
                vdpi = int.from_bytes(file_data[14:16], 'little')
                metadata['dpi'] = {'horizontal': hdpi, 'vertical': vdpi}

                # Number of color planes (byte 65)
                metadata['color_planes'] = file_data[65] if len(file_data) > 65 else 1

                # Bytes per line (bytes 66-67)
                if len(file_data) > 67:
                    bytes_per_line = int.from_bytes(file_data[66:68], 'little')
                    metadata['bytes_per_line'] = bytes_per_line

            # Open with PIL for additional metadata
            image = Image.open(io.BytesIO(file_data))
            metadata['pil_format'] = image.format
            metadata['pil_mode'] = image.mode
            metadata['pil_size'] = image.size
            metadata['pil_info'] = dict(image.info)

        except Exception as e:
            logger.error(f"Failed to extract PCX metadata: {e}")
            metadata['error'] = str(e)

        return metadata

    def optimize_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        Optimize PCX image for OCR
        PCX files are often old/low-quality scans
        """
        # Apply base optimization
        image = super().resize_for_ocr(image)

        try:
            import cv2
            import numpy as np

            # Convert to OpenCV format
            cv_image = self._pil_to_cv2(image)

            # Convert to grayscale
            if len(cv_image.shape) == 3:
                gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            else:
                gray = cv_image

            # Apply histogram equalization to improve contrast
            equalized = cv2.equalizeHist(gray)

            # Apply bilateral filter to reduce noise while preserving edges
            filtered = cv2.bilateralFilter(equalized, 9, 75, 75)

            # Apply adaptive thresholding for better text extraction
            thresh = cv2.adaptiveThreshold(
                filtered, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )

            # Convert back to PIL
            optimized = Image.fromarray(thresh)

            # Convert back to RGB for OCR
            if optimized.mode != 'RGB':
                optimized = optimized.convert('RGB')

            logger.info("Applied OCR optimization to PCX image")
            return optimized

        except Exception as e:
            logger.warning(f"PCX optimization failed, using original: {e}")
            return image

    def repair_corrupted_pcx(self, file_data: bytes) -> Optional[bytes]:
        """
        Attempt to repair common PCX file corruptions
        """
        try:
            # Check if header is intact
            if len(file_data) < 128:
                logger.error("PCX file too corrupted (missing header)")
                return None

            # Try to fix common issues
            repaired = bytearray(file_data)

            # Ensure magic byte is correct
            if repaired[0] != 0x0A:
                logger.info("Fixing PCX magic byte")
                repaired[0] = 0x0A

            # Ensure encoding is RLE
            if repaired[2] != 1:
                logger.info("Fixing PCX encoding byte")
                repaired[2] = 1

            # Ensure version is valid
            if repaired[1] not in [0, 2, 3, 4, 5]:
                logger.info("Fixing PCX version byte")
                repaired[1] = 5  # Use version 5 (most common)

            # Try to open repaired file
            try:
                Image.open(io.BytesIO(bytes(repaired)))
                logger.info("Successfully repaired PCX file")
                return bytes(repaired)
            except Exception:
                logger.error("PCX repair failed")
                return None

        except Exception as e:
            logger.error(f"PCX repair error: {e}")
            return None

    def convert_from_pcx(self, image: Image.Image, target_format: str = 'PNG') -> bytes:
        """
        Convert PCX image to another format
        Useful for compatibility with systems that don't support PCX
        """
        try:
            output = io.BytesIO()

            # Ensure RGB mode for better compatibility
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Save in target format
            image.save(output, format=target_format, optimize=True)

            logger.info(f"Converted PCX to {target_format}")
            return output.getvalue()

        except Exception as e:
            logger.error(f"Failed to convert PCX to {target_format}: {e}")
            raise ValueError(f"PCX format conversion failed: {e}")