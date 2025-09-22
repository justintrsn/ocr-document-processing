"""
Image format converter for standard image formats
"""

from PIL import Image
import io
import logging
from typing import Optional, Dict, Any
from src.core.converters.base_converter import BaseFormatConverter
from src.models.formats import FileFormat

logger = logging.getLogger(__name__)


class ImageFormatConverter(BaseFormatConverter):
    """
    Handles conversion for standard image formats:
    PNG, JPG, JPEG, BMP, GIF, TIFF, WebP, ICO
    """

    SUPPORTED_FORMATS = {
        FileFormat.PNG: 'PNG',
        FileFormat.JPG: 'JPEG',
        FileFormat.JPEG: 'JPEG',
        FileFormat.BMP: 'BMP',
        FileFormat.GIF: 'GIF',
        FileFormat.TIFF: 'TIFF',
        FileFormat.WEBP: 'WebP',
        FileFormat.ICO: 'ICO'
    }

    def __init__(self, format_type: Optional[FileFormat] = None):
        super().__init__()
        self.format_type = format_type
        self.format_name = self.SUPPORTED_FORMATS.get(format_type, 'AUTO')

    def convert_to_pil(self, file_data: bytes) -> Image.Image:
        """
        Convert image bytes to PIL Image
        """
        try:
            # Open image with PIL
            image = Image.open(io.BytesIO(file_data))

            # Handle specific format quirks
            image = self._handle_format_specific(image)

            # Convert to RGB if necessary for OCR
            image = self._ensure_rgb(image)

            return image

        except Exception as e:
            logger.error(f"Failed to convert image: {e}")
            raise ValueError(f"Image conversion failed: {e}")

    def _handle_format_specific(self, image: Image.Image) -> Image.Image:
        """Handle format-specific conversions and quirks"""

        # GIF handling - extract first frame if animated
        if image.format == 'GIF' and hasattr(image, 'is_animated') and image.is_animated:
            logger.info("Extracting first frame from animated GIF")
            image.seek(0)  # Go to first frame
            # Convert to static image
            static_image = Image.new('RGBA', image.size)
            static_image.paste(image)
            return static_image

        # ICO handling - select best size
        if image.format == 'ICO':
            logger.info(f"Processing ICO with size {image.size}")
            # ICO files can contain multiple sizes, PIL usually picks the best one
            # But we can ensure we have a reasonable size
            if image.width < 32 or image.height < 32:
                # Try to get a larger size if available
                try:
                    image = image.resize((max(32, image.width), max(32, image.height)), Image.Resampling.LANCZOS)
                except Exception:
                    pass

        # TIFF handling - handle multi-page TIFF
        if image.format == 'TIFF':
            # For now, just use the first page
            # Multi-page TIFF could be handled similar to PDF
            try:
                image.seek(0)
            except Exception:
                pass

        # WebP handling - ensure it's static
        if image.format == 'WebP' and hasattr(image, 'is_animated') and image.is_animated:
            logger.info("Extracting first frame from animated WebP")
            image.seek(0)
            static_image = Image.new('RGBA', image.size)
            static_image.paste(image)
            return static_image

        return image

    def _ensure_rgb(self, image: Image.Image) -> Image.Image:
        """
        Ensure image is in RGB mode for OCR processing
        Handles various color modes appropriately
        """
        if image.mode == 'RGB':
            return image

        # Handle different modes
        if image.mode == 'RGBA':
            # Create white background for transparency
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])  # Use alpha channel as mask
            return background

        elif image.mode == 'P':
            # Palette mode - check for transparency
            if 'transparency' in image.info:
                # Convert to RGBA first to handle transparency
                image = image.convert('RGBA')
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                return background
            else:
                return image.convert('RGB')

        elif image.mode == 'L':
            # Grayscale - convert to RGB
            return image.convert('RGB')

        elif image.mode == 'LA':
            # Grayscale with alpha
            background = Image.new('RGB', image.size, (255, 255, 255))
            # Convert to RGBA first
            rgba = image.convert('RGBA')
            background.paste(rgba, mask=rgba.split()[3])
            return background

        elif image.mode == 'CMYK':
            # CMYK - convert to RGB
            return image.convert('RGB')

        elif image.mode == '1':
            # Binary (1-bit) - convert to RGB
            return image.convert('RGB')

        else:
            # Unknown mode - try direct conversion
            logger.warning(f"Unknown image mode: {image.mode}, attempting conversion")
            return image.convert('RGB')

    def optimize_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        Optimize image specifically for OCR processing
        """
        # Ensure minimum size for OCR
        if image.width < 100 or image.height < 100:
            scale = max(100 / image.width, 100 / image.height)
            new_width = int(image.width * scale)
            new_height = int(image.height * scale)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.info(f"Upscaled small image to {new_width}x{new_height}")

        # Ensure reasonable DPI (if too large, downscale)
        if image.width > 4000 or image.height > 4000:
            scale = min(4000 / image.width, 4000 / image.height)
            new_width = int(image.width * scale)
            new_height = int(image.height * scale)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.info(f"Downscaled large image to {new_width}x{new_height}")

        return image

    def extract_text_regions(self, image: Image.Image) -> list:
        """
        Extract potential text regions from image
        Returns list of (x, y, width, height) tuples
        """
        try:
            import cv2
            import numpy as np

            # Convert to OpenCV format
            cv_image = np.array(image)
            if len(cv_image.shape) == 3:
                gray = cv2.cvtColor(cv_image, cv2.COLOR_RGB2GRAY)
            else:
                gray = cv_image

            # Apply threshold
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Filter contours for text-like regions
            text_regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                # Filter based on aspect ratio and size
                aspect_ratio = w / float(h)
                if 0.5 < aspect_ratio < 20 and w > 10 and h > 10:
                    text_regions.append((x, y, w, h))

            return text_regions

        except Exception as e:
            logger.debug(f"Text region extraction failed: {e}")
            return []

    def get_format_info(self, image: Image.Image) -> Dict[str, Any]:
        """Get detailed format information"""
        info = {
            "format": image.format,
            "mode": image.mode,
            "size": image.size,
            "info": dict(image.info)
        }

        # Add format-specific information
        if image.format == 'GIF':
            info['is_animated'] = hasattr(image, 'is_animated') and image.is_animated
            if info['is_animated']:
                try:
                    info['n_frames'] = image.n_frames
                except Exception:
                    info['n_frames'] = 1

        elif image.format == 'JPEG':
            info['dpi'] = image.info.get('dpi', (72, 72))
            info['quality'] = image.info.get('quality', 'unknown')

        elif image.format == 'PNG':
            info['dpi'] = image.info.get('dpi', (72, 72))
            info['transparency'] = 'transparency' in image.info

        elif image.format == 'TIFF':
            info['compression'] = image.info.get('compression', 'none')
            info['dpi'] = image.info.get('dpi', (72, 72))

        return info