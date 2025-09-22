"""
PDF format converter with page-by-page processing support
"""

from PIL import Image
import io
import logging
from typing import Optional, List, Dict, Any, Union
from src.core.converters.base_converter import BaseFormatConverter

logger = logging.getLogger(__name__)


class PDFFormatConverter(BaseFormatConverter):
    """
    Handles PDF conversion with page-by-page processing
    Critical: Huawei OCR API requires processing PDFs one page at a time
    """

    def __init__(self):
        super().__init__()
        self.format_name = 'PDF'
        self.supports_multi_page = True
        self.requires_special_handling = True

    def convert_to_pil(self, file_data: bytes, page_number: int = 1) -> Image.Image:
        """
        Convert a specific PDF page to PIL Image
        Default to first page if not specified

        Args:
            file_data: PDF file bytes
            page_number: Page number to convert (1-indexed)
        """
        try:
            from pdf2image import convert_from_bytes
        except ImportError:
            raise ImportError("pdf2image library is required for PDF processing")

        try:
            # Convert specific page to image
            # first_page and last_page are 1-indexed
            images = convert_from_bytes(
                file_data,
                first_page=page_number,
                last_page=page_number,
                dpi=300,  # High DPI for better OCR
                fmt='PIL',
                thread_count=1,
                use_pdftocairo=True  # Better quality
            )

            if not images:
                raise ValueError(f"Could not extract page {page_number} from PDF")

            image = images[0]

            # Ensure RGB mode for OCR
            if image.mode != 'RGB':
                image = image.convert('RGB')

            logger.info(f"Successfully converted PDF page {page_number} to image")
            return image

        except Exception as e:
            logger.error(f"Failed to convert PDF page {page_number}: {e}")
            raise ValueError(f"PDF page conversion failed: {e}")

    def extract_page(self, file_data: bytes, page_number: int) -> Image.Image:
        """
        Extract a specific page from PDF as PIL Image

        Args:
            file_data: PDF file bytes
            page_number: Page number to extract (1-indexed)
        """
        return self.convert_to_pil(file_data, page_number)

    def extract_all_pages(self, file_data: bytes) -> List[Image.Image]:
        """
        Extract all pages from PDF as list of PIL Images
        Note: For large PDFs, this can be memory intensive
        """
        try:
            from pdf2image import convert_from_bytes
        except ImportError:
            raise ImportError("pdf2image library is required for PDF processing")

        try:
            images = convert_from_bytes(
                file_data,
                dpi=300,
                fmt='PIL',
                thread_count=4,  # Use parallel processing
                use_pdftocairo=True
            )

            # Ensure all images are in RGB mode
            rgb_images = []
            for i, img in enumerate(images):
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                rgb_images.append(img)
                logger.debug(f"Extracted page {i+1} of {len(images)}")

            logger.info(f"Successfully extracted {len(rgb_images)} pages from PDF")
            return rgb_images

        except Exception as e:
            logger.error(f"Failed to extract all PDF pages: {e}")
            raise ValueError(f"PDF extraction failed: {e}")

    def extract_page_range(
        self,
        file_data: bytes,
        start_page: int,
        end_page: int
    ) -> List[Image.Image]:
        """
        Extract a range of pages from PDF

        Args:
            file_data: PDF file bytes
            start_page: Starting page number (1-indexed)
            end_page: Ending page number (1-indexed, inclusive)
        """
        try:
            from pdf2image import convert_from_bytes
        except ImportError:
            raise ImportError("pdf2image library is required for PDF processing")

        try:
            images = convert_from_bytes(
                file_data,
                first_page=start_page,
                last_page=end_page,
                dpi=300,
                fmt='PIL',
                thread_count=2,
                use_pdftocairo=True
            )

            # Ensure RGB mode
            rgb_images = []
            for img in images:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                rgb_images.append(img)

            logger.info(f"Extracted pages {start_page}-{end_page} from PDF")
            return rgb_images

        except Exception as e:
            logger.error(f"Failed to extract PDF page range: {e}")
            raise ValueError(f"PDF page range extraction failed: {e}")

    def get_page_count(self, file_data: bytes) -> int:
        """
        Get the total number of pages in the PDF
        """
        try:
            from pdf2image import pdfinfo_from_bytes
        except ImportError:
            raise ImportError("pdf2image library is required for PDF processing")

        try:
            info = pdfinfo_from_bytes(file_data)
            page_count = info.get('Pages', 0)
            logger.debug(f"PDF has {page_count} pages")
            return page_count

        except Exception as e:
            logger.error(f"Failed to get PDF page count: {e}")
            return 0

    def get_pdf_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """
        Extract metadata from PDF
        """
        try:
            from pdf2image import pdfinfo_from_bytes
        except ImportError:
            raise ImportError("pdf2image library is required for PDF processing")

        metadata = {}

        try:
            info = pdfinfo_from_bytes(file_data)

            metadata = {
                'page_count': info.get('Pages', 0),
                'encrypted': info.get('Encrypted', 'no') == 'yes',
                'page_size': info.get('Page size', 'unknown'),
                'file_size': len(file_data),
                'pdf_version': info.get('PDF version', 'unknown'),
                'title': info.get('Title', ''),
                'author': info.get('Author', ''),
                'subject': info.get('Subject', ''),
                'keywords': info.get('Keywords', ''),
                'creator': info.get('Creator', ''),
                'producer': info.get('Producer', ''),
                'creation_date': info.get('CreationDate', ''),
                'modification_date': info.get('ModDate', '')
            }

            # Parse page size to get dimensions
            if metadata['page_size'] != 'unknown':
                try:
                    # Format: "612 x 792 pts (letter)"
                    size_parts = metadata['page_size'].split(' x ')
                    if len(size_parts) >= 2:
                        width = float(size_parts[0].split()[0])
                        height = float(size_parts[1].split()[0])
                        metadata['page_width_pts'] = width
                        metadata['page_height_pts'] = height
                        # Convert to pixels at 72 DPI
                        metadata['page_width_px'] = int(width)
                        metadata['page_height_px'] = int(height)
                except Exception:
                    pass

            return metadata

        except Exception as e:
            logger.error(f"Failed to extract PDF metadata: {e}")
            return {'error': str(e)}

    def validate_pdf(self, file_data: bytes) -> tuple[bool, Optional[str]]:
        """
        Validate PDF file before processing
        """
        # Check magic bytes
        if not file_data.startswith(b'%PDF'):
            return False, "Not a valid PDF file"

        # Check minimum size
        if len(file_data) < 100:
            return False, "PDF file too small"

        # Get page count and validate
        page_count = self.get_page_count(file_data)

        if page_count == 0:
            return False, "PDF has no pages"

        if page_count > 100:
            logger.warning(f"PDF has {page_count} pages, which may take long to process")

        # Check if encrypted
        metadata = self.get_pdf_metadata(file_data)
        if metadata.get('encrypted', False):
            return False, "PDF is encrypted/password protected"

        return True, None

    def process_page_with_retry(
        self,
        file_data: bytes,
        page_number: int,
        max_retries: int = 2
    ) -> tuple[Optional[Image.Image], Optional[str]]:
        """
        Process a PDF page with retry logic for fault tolerance

        Returns:
            (image, error_message) - image is None if failed
        """
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                image = self.extract_page(file_data, page_number)

                # Validate extracted image
                if image.width < 15 or image.height < 15:
                    raise ValueError(f"Page {page_number} image too small: {image.size}")

                return image, None

            except Exception as e:
                last_error = str(e)
                retry_count += 1

                if retry_count <= max_retries:
                    logger.warning(f"Retry {retry_count}/{max_retries} for page {page_number}: {e}")
                else:
                    logger.error(f"Failed to process page {page_number} after {max_retries} retries: {e}")

        return None, last_error

    def optimize_page_for_ocr(self, image: Image.Image, page_number: int) -> Image.Image:
        """
        Optimize a PDF page image for OCR processing
        """
        # Apply base optimization
        image = self.resize_for_ocr(image)

        # Check if page is mostly text or mostly graphics
        is_text_heavy = self._is_text_heavy_page(image)

        if is_text_heavy:
            # Apply text-specific enhancements
            image = self.enhance_image_quality(image)
            logger.debug(f"Applied text enhancement to page {page_number}")
        else:
            logger.debug(f"Page {page_number} appears to be graphics-heavy")

        return image

    def _is_text_heavy_page(self, image: Image.Image) -> bool:
        """
        Determine if a page is primarily text or graphics
        """
        try:
            import cv2
            import numpy as np

            # Convert to grayscale
            gray = image.convert('L')
            gray_np = np.array(gray)

            # Apply edge detection
            edges = cv2.Canny(gray_np, 50, 150)

            # Count edge pixels
            edge_ratio = np.sum(edges > 0) / edges.size

            # Text pages typically have 5-20% edge pixels
            return 0.05 <= edge_ratio <= 0.20

        except Exception as e:
            logger.debug(f"Could not determine page type: {e}")
            return True  # Default to text optimization

    def get_page_thumbnail(
        self,
        file_data: bytes,
        page_number: int,
        size: tuple = (150, 150)
    ) -> Image.Image:
        """
        Get a thumbnail of a specific page
        """
        try:
            # Extract page at lower DPI for thumbnail
            from pdf2image import convert_from_bytes

            images = convert_from_bytes(
                file_data,
                first_page=page_number,
                last_page=page_number,
                dpi=72,  # Low DPI for thumbnail
                fmt='PIL'
            )

            if images:
                thumb = images[0]
                thumb.thumbnail(size, Image.Resampling.LANCZOS)
                return thumb

        except Exception as e:
            logger.error(f"Failed to create thumbnail: {e}")

        # Return blank thumbnail on failure
        return Image.new('RGB', size, color='white')