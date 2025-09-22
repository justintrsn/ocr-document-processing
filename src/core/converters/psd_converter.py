"""
PSD (Photoshop) format converter using psd-tools
"""

from PIL import Image
import io
import logging
from typing import Optional, Dict, Any, List
from src.core.converters.base_converter import BaseFormatConverter

logger = logging.getLogger(__name__)


class PSDFormatConverter(BaseFormatConverter):
    """
    Handles conversion for Adobe Photoshop PSD files
    Requires psd-tools library
    """

    def __init__(self):
        super().__init__()
        self.format_name = 'PSD'
        self.requires_special_handling = True

    def convert_to_pil(self, file_data: bytes) -> Image.Image:
        """
        Convert PSD file to PIL Image
        Composites all visible layers into a single image
        """
        try:
            from psd_tools import PSDImage
        except ImportError:
            raise ImportError("psd-tools library is required for PSD file processing")

        try:
            # Open PSD file
            psd = PSDImage.open(io.BytesIO(file_data))

            # Composite all layers into a single image
            # This respects layer visibility and blend modes
            composite_image = psd.composite()

            if composite_image is None:
                # If composite fails, try to get the first layer
                logger.warning("PSD composite failed, attempting to extract first layer")
                for layer in psd:
                    if hasattr(layer, 'composite'):
                        composite_image = layer.composite()
                        if composite_image:
                            break

                if composite_image is None:
                    raise ValueError("Unable to extract image from PSD file")

            # Ensure RGB mode for OCR
            if composite_image.mode != 'RGB':
                if composite_image.mode == 'RGBA':
                    # Create white background for transparency
                    background = Image.new('RGB', composite_image.size, (255, 255, 255))
                    background.paste(composite_image, mask=composite_image.split()[3])
                    composite_image = background
                else:
                    composite_image = composite_image.convert('RGB')

            return composite_image

        except Exception as e:
            logger.error(f"Failed to convert PSD: {e}")
            raise ValueError(f"PSD conversion failed: {e}")

    def extract_layers(self, file_data: bytes) -> List[Dict[str, Any]]:
        """
        Extract individual layers from PSD file
        Returns list of layer information with images
        """
        try:
            from psd_tools import PSDImage
        except ImportError:
            raise ImportError("psd-tools library is required for PSD file processing")

        layers_info = []

        try:
            psd = PSDImage.open(io.BytesIO(file_data))

            for i, layer in enumerate(psd):
                layer_info = {
                    'index': i,
                    'name': layer.name,
                    'visible': layer.visible,
                    'opacity': layer.opacity,
                    'blend_mode': str(layer.blend_mode) if hasattr(layer, 'blend_mode') else 'normal'
                }

                # Try to get layer image
                try:
                    if hasattr(layer, 'composite'):
                        layer_image = layer.composite()
                        if layer_image:
                            layer_info['image'] = layer_image
                            layer_info['size'] = layer_image.size
                            layer_info['has_image'] = True
                        else:
                            layer_info['has_image'] = False
                    else:
                        layer_info['has_image'] = False

                    # Get layer bounds
                    if hasattr(layer, 'bbox'):
                        bbox = layer.bbox
                        layer_info['bbox'] = {
                            'left': bbox.left,
                            'top': bbox.top,
                            'right': bbox.right,
                            'bottom': bbox.bottom
                        }

                except Exception as e:
                    logger.debug(f"Could not extract layer {i} image: {e}")
                    layer_info['has_image'] = False

                layers_info.append(layer_info)

            return layers_info

        except Exception as e:
            logger.error(f"Failed to extract PSD layers: {e}")
            return []

    def extract_text_layers(self, file_data: bytes) -> List[Dict[str, Any]]:
        """
        Extract text layers from PSD file
        Returns list of text layer information
        """
        try:
            from psd_tools import PSDImage
        except ImportError:
            raise ImportError("psd-tools library is required for PSD file processing")

        text_layers = []

        try:
            psd = PSDImage.open(io.BytesIO(file_data))

            for layer in psd:
                # Check if layer is a text layer
                if hasattr(layer, 'text_data'):
                    text_info = {
                        'name': layer.name,
                        'text': layer.text_data.text if hasattr(layer.text_data, 'text') else '',
                        'font': layer.text_data.font_name if hasattr(layer.text_data, 'font_name') else 'unknown',
                        'font_size': layer.text_data.font_size if hasattr(layer.text_data, 'font_size') else 0,
                        'visible': layer.visible
                    }

                    # Get position if available
                    if hasattr(layer, 'bbox'):
                        bbox = layer.bbox
                        text_info['position'] = {
                            'x': bbox.left,
                            'y': bbox.top,
                            'width': bbox.right - bbox.left,
                            'height': bbox.bottom - bbox.top
                        }

                    text_layers.append(text_info)

            return text_layers

        except Exception as e:
            logger.debug(f"Could not extract text layers: {e}")
            return []

    def get_psd_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """
        Extract metadata from PSD file
        """
        try:
            from psd_tools import PSDImage
        except ImportError:
            raise ImportError("psd-tools library is required for PSD file processing")

        metadata = {}

        try:
            psd = PSDImage.open(io.BytesIO(file_data))

            metadata = {
                'width': psd.width,
                'height': psd.height,
                'channels': psd.channels,
                'depth': psd.depth,
                'color_mode': str(psd.color_mode),
                'layer_count': len(list(psd)),
                'has_preview': psd.has_preview() if hasattr(psd, 'has_preview') else False
            }

            # Get visible layers count
            visible_count = sum(1 for layer in psd if layer.visible)
            metadata['visible_layers'] = visible_count

            # Check for text layers
            has_text = any(hasattr(layer, 'text_data') for layer in psd)
            metadata['has_text_layers'] = has_text

            # Get file version if available
            if hasattr(psd, 'version'):
                metadata['version'] = psd.version

            return metadata

        except Exception as e:
            logger.error(f"Failed to extract PSD metadata: {e}")
            return {}

    def optimize_for_ocr(self, image: Image.Image, file_data: bytes) -> Image.Image:
        """
        Optimize PSD-derived image for OCR
        May use layer information to enhance text visibility
        """
        # First apply base optimization
        image = super().resize_for_ocr(image)

        # Try to enhance using text layers if available
        text_layers = self.extract_text_layers(file_data)

        if text_layers:
            logger.info(f"Found {len(text_layers)} text layers in PSD")
            # Could potentially use text layer positions to focus OCR
            # or validate OCR results against known text

        return image

    def validate_psd(self, file_data: bytes) -> tuple[bool, Optional[str]]:
        """
        Validate PSD file before processing
        """
        # Check magic bytes
        if not file_data.startswith(b'8BPS'):
            return False, "Not a valid PSD file"

        # Check minimum size
        if len(file_data) < 100:
            return False, "PSD file too small"

        try:
            from psd_tools import PSDImage

            # Try to open the file
            psd = PSDImage.open(io.BytesIO(file_data))

            # Check dimensions
            if psd.width < 15 or psd.height < 15:
                return False, f"PSD dimensions too small: {psd.width}x{psd.height}"

            if psd.width > 30000 or psd.height > 30000:
                return False, f"PSD dimensions too large: {psd.width}x{psd.height}"

            # Check if we can composite
            composite = psd.composite()
            if composite is None:
                # Check if there are any layers
                if not list(psd):
                    return False, "PSD file has no layers"
                # File might still be processable even if composite fails
                logger.warning("PSD composite returned None, but file has layers")

            return True, None

        except Exception as e:
            return False, f"PSD validation failed: {str(e)}"