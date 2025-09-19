#!/usr/bin/env python
"""
Script to add a test document to the test configuration
"""

import sys
import yaml
from pathlib import Path


def add_test_document(doc_name: str):
    """Add a test document to the configuration"""
    config_path = Path(__file__).parent / "test_config.yaml"
    documents_dir = Path(__file__).parent / "documents"

    # Check if document exists
    doc_path = documents_dir / doc_name
    if not doc_path.exists():
        print(f"❌ Document not found: {doc_path}")
        print(f"   Please copy your document to: {documents_dir}/")
        return False

    # Load configuration
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Add to test files if not already present
    test_files = config.get("documents", {}).get("test_files", [])
    if doc_name not in test_files:
        test_files.append(doc_name)
        config["documents"]["test_files"] = test_files
        print(f"✅ Added {doc_name} to test documents")
    else:
        print(f"ℹ️  {doc_name} already in test configuration")

    # Add OBS key
    obs_key = f"OCR/{doc_name}"
    obs_keys = config.get("obs", {}).get("test_keys", [])
    if obs_key not in obs_keys:
        obs_keys.append(obs_key)
        config["obs"]["test_keys"] = obs_keys
        print(f"✅ Added {obs_key} to OBS test keys")

    # Save configuration
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"\n📋 Configuration updated!")
    print(f"   Test documents: {test_files}")
    print(f"   OBS keys: {obs_keys}")
    print(f"\n🧪 Run tests with: pytest tests/image_quality/test_batch_processing.py -v")

    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python add_test_document.py <document_name>")
        print("Example: python add_test_document.py scanned_document2.jpg")
        sys.exit(1)

    doc_name = sys.argv[1]
    success = add_test_document(doc_name)
    sys.exit(0 if success else 1)