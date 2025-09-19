import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

from src.services.ocr_service import HuaweiOCRService
from src.services.obs_service import OBSService
from src.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_document(file_path: str = None, obs_key: str = None):
    if not file_path and not obs_key:
        logger.error("Either file path or OBS key must be provided")
        sys.exit(1)

    if file_path:
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            sys.exit(1)

        if not path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.pdf']:
            logger.error(f"Unsupported file format: {path.suffix}")
            sys.exit(1)

        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > settings.image_max_size_mb:
            logger.error(f"File size ({file_size_mb:.2f}MB) exceeds maximum limit of {settings.image_max_size_mb}MB")
            sys.exit(1)

        print(f"\n{'='*50}")
        print(f"Processing local document: {path.name}")
        print(f"File size: {file_size_mb:.2f}MB")
        print(f"{'='*50}\n")
    else:
        print(f"\n{'='*50}")
        print(f"Processing OBS document: {obs_key}")
        print(f"Bucket: {settings.obs_bucket_name}")
        print(f"{'='*50}\n")

    start_time = datetime.now()

    try:
        ocr_service = HuaweiOCRService()

        if file_path:
            print("🔄 Sending document to OCR service...")
            ocr_response = ocr_service.process_document(path)
        else:
            obs_service = OBSService()

            # Check if object exists
            if not obs_service.check_object_exists(obs_key):
                logger.error(f"Object not found in OBS: {obs_key}")
                sys.exit(1)

            print("🔄 Generating signed URL...")
            signed_url = obs_service.get_signed_url(obs_key, expires_in=300)

            print("🔄 Sending document to OCR service...")
            ocr_response = ocr_service.process_document(image_url=signed_url)

            obs_service.close()

        processing_time = (datetime.now() - start_time).total_seconds()

        extracted_text = ocr_service.extract_text_from_response(ocr_response)
        avg_confidence = ocr_service.get_average_confidence(ocr_response)

        print(f"✅ OCR processing completed in {processing_time:.2f} seconds\n")

        print(f"{'='*50}")
        print("RESULTS")
        print(f"{'='*50}")
        print(f"Confidence Score: {avg_confidence*100:.2f}%")

        if avg_confidence * 100 >= settings.manual_review_threshold:
            print(f"Status: ✅ AUTO-PROCESSED (above {settings.manual_review_threshold}% threshold)")
        else:
            print(f"Status: ⚠️ REQUIRES MANUAL REVIEW (below {settings.manual_review_threshold}% threshold)")

        print(f"\n{'='*50}")
        print("EXTRACTED TEXT")
        print(f"{'='*50}")
        print(extracted_text[:1000] if len(extracted_text) > 1000 else extracted_text)
        if len(extracted_text) > 1000:
            print(f"\n... (showing first 1000 characters of {len(extracted_text)} total)")

        if ocr_response.result:
            for idx, result in enumerate(ocr_response.result):
                if result.table_result and result.table_result.table_count > 0:
                    print(f"\n📊 Found {result.table_result.table_count} table(s)")

                if result.formula_result and result.formula_result.formula_count > 0:
                    print(f"\n🔢 Found {result.formula_result.formula_count} formula(s)")

                if result.kv_result and result.kv_result.kv_block_count > 0:
                    print(f"\n📋 Found {result.kv_result.kv_block_count} key-value pair(s)")

        print(f"\n{'='*50}")
        print("Processing completed successfully!")
        print(f"{'='*50}\n")

        return 0

    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        print(f"\n❌ Error: {str(e)}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="OCR Document Processing CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli.main process --file document.jpg
  python -m src.cli.main process --file invoice.pdf
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    process_parser = subparsers.add_parser('process', help='Process a document')
    process_parser.add_argument(
        '--file',
        help='Path to the local document file to process'
    )
    process_parser.add_argument(
        '--obs-key',
        help='OBS object key for the document (e.g., OCR/document.jpg)'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == 'process':
        if not args.file and not args.obs_key:
            print("Error: Either --file or --obs-key must be provided")
            process_parser.print_help()
            sys.exit(1)

        exit_code = process_document(args.file, args.obs_key)
        sys.exit(exit_code)


if __name__ == "__main__":
    main()