"""
Test configuration loader
"""

import os
from pathlib import Path
from typing import List, Dict, Any
import yaml


class TestConfig:
    """Test configuration manager"""

    def __init__(self, config_path: Path = None):
        """Initialize test configuration"""
        if config_path is None:
            config_path = Path(__file__).parent / "test_config.yaml"

        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            # Return default configuration if file doesn't exist
            return self._get_default_config()

        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "documents": {
                "test_files": ["scanned_document.jpg"],
                "test_all": False,
                "max_batch_size": 5
            },
            "quality": {
                "ocr_threshold": 80.0,
                "thresholds": {
                    "sharpness": {"excellent": 80, "good": 60, "fair": 40, "poor": 20},
                    "contrast": {"excellent": 80, "good": 60, "fair": 40, "poor": 20},
                    "resolution": {"excellent": 90, "good": 60, "fair": 30, "poor": 0},
                    "noise": {"excellent": 90, "good": 70, "fair": 50, "poor": 30}
                }
            },
            "obs": {
                "test_bucket": "sample-dataset-bucket",
                "test_prefix": "OCR/",
                "test_keys": ["OCR/scanned_document.jpg"]
            },
            "queue": {
                "enabled": True,
                "test_priorities": ["high", "medium", "low"],
                "max_queue_size": 100
            },
            "performance": {
                "ocr_timeout": 180,
                "target_time": 6,
                "max_time": 30
            },
            "test_modes": {
                "local_files": True,
                "obs_urls": True,
                "public_urls": True,
                "batch_processing": True,
                "queue_management": True
            },
            "mock": {
                "use_mock_ocr": True,
                "use_mock_obs": True,
                "ocr_delay": 500,
                "obs_delay": 100
            }
        }

    def get_test_documents(self) -> List[str]:
        """Get list of test documents"""
        docs = self._config.get("documents", {}).get("test_files", [])

        # Support environment variable override
        env_docs = os.environ.get("TEST_DOCUMENTS")
        if env_docs:
            docs = env_docs.split(",")

        # Filter for existing files only
        documents_dir = Path(__file__).parent / "documents"
        existing_docs = []
        for doc in docs:
            doc_path = documents_dir / doc.strip()
            if doc_path.exists():
                existing_docs.append(doc.strip())
            else:
                print(f"Warning: Test document not found: {doc_path}")

        return existing_docs if existing_docs else ["scanned_document.jpg"]

    def should_test_all_documents(self) -> bool:
        """Check if all documents should be tested"""
        return self._config.get("documents", {}).get("test_all", False)

    def get_quality_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Get quality thresholds"""
        return self._config.get("quality", {}).get("thresholds", {})

    def get_ocr_threshold(self) -> float:
        """Get OCR quality threshold"""
        return self._config.get("quality", {}).get("ocr_threshold", 80.0)

    def get_obs_test_keys(self) -> List[str]:
        """Get OBS test keys"""
        return self._config.get("obs", {}).get("test_keys", [])

    def is_queue_enabled(self) -> bool:
        """Check if queue testing is enabled"""
        return self._config.get("queue", {}).get("enabled", True)

    def get_queue_priorities(self) -> List[str]:
        """Get queue priorities to test"""
        return self._config.get("queue", {}).get("test_priorities", ["high", "medium", "low"])

    def get_max_batch_size(self) -> int:
        """Get maximum batch size for testing"""
        return self._config.get("documents", {}).get("max_batch_size", 5)

    def is_mode_enabled(self, mode: str) -> bool:
        """Check if a specific test mode is enabled"""
        return self._config.get("test_modes", {}).get(mode, True)

    def should_use_mock(self, service: str) -> bool:
        """Check if mock should be used for a service"""
        mock_key = f"use_mock_{service}"
        return self._config.get("mock", {}).get(mock_key, True)

    def get_performance_limits(self) -> Dict[str, float]:
        """Get performance limits"""
        return {
            "timeout": self._config.get("performance", {}).get("ocr_timeout", 180),
            "target": self._config.get("performance", {}).get("target_time", 6),
            "max": self._config.get("performance", {}).get("max_time", 30)
        }


# Global test configuration instance
test_config = TestConfig()