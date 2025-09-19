"""
Unit tests for OCR Confidence Analyzer
"""

import pytest
from src.services.ocr_confidence_analyzer import OCRConfidenceAnalyzer
from src.models.ocr_models import OCRResponse, OCRResult, OCRDetails, WordBlock


class TestOCRConfidenceAnalyzer:
    """Test OCR confidence analysis functions"""

    @pytest.fixture
    def analyzer(self):
        return OCRConfidenceAnalyzer()

    @pytest.fixture
    def sample_ocr_response(self):
        """Create a sample OCR response for testing"""
        # Create word blocks with varying confidence levels
        words = [
            WordBlock(words="Hello", confidence=0.98, location=[[0, 0], [100, 0], [100, 30], [0, 30]]),
            WordBlock(words="World", confidence=0.95, location=[[110, 0], [200, 0], [200, 30], [110, 30]]),
            WordBlock(words="Test", confidence=0.85, location=[[0, 40], [100, 40], [100, 70], [0, 70]]),
            WordBlock(words="Document", confidence=0.75, location=[[110, 40], [250, 40], [250, 70], [110, 70]]),
            WordBlock(words="Low", confidence=0.55, location=[[0, 80], [50, 80], [50, 110], [0, 110]]),
            WordBlock(words="Confidence", confidence=0.45, location=[[60, 80], [200, 80], [200, 110], [60, 110]]),
        ]

        ocr_details = OCRDetails(
            words_block_list=words,
            direction=0.0
        )

        ocr_result = OCRResult(
            ocr_result=ocr_details
        )

        return OCRResponse(result=[ocr_result])

    def test_analyze_confidence(self, analyzer, sample_ocr_response):
        """Test confidence analysis"""
        result = analyzer.analyze_confidence(sample_ocr_response)

        assert "summary" in result
        assert "distribution" in result
        assert "problem_areas" in result
        assert "confidence_histogram" in result

        # Check summary
        summary = result["summary"]
        assert summary["total_words"] == 6
        assert 0 <= summary["average_confidence"] <= 1
        assert summary["min_confidence"] == 0.45
        assert summary["max_confidence"] == 0.98

        # Check distribution
        distribution = result["distribution"]
        assert distribution["high"]["count"] == 2  # 0.98, 0.95
        assert distribution["medium"]["count"] == 1  # 0.85
        assert distribution["low"]["count"] == 1  # 0.75
        assert distribution["very_low"]["count"] == 2  # 0.55, 0.45

    def test_problem_areas_detection(self, analyzer, sample_ocr_response):
        """Test detection of problem areas"""
        result = analyzer.analyze_confidence(sample_ocr_response)

        problem_areas = result["problem_areas"]
        assert len(problem_areas) == 2  # Words with confidence < 0.60

        # Check that lowest confidence words are in problem areas
        assert any(area["text"] == "Confidence" for area in problem_areas)
        assert any(area["text"] == "Low" for area in problem_areas)

        # Problem areas should be sorted by confidence (lowest first)
        if len(problem_areas) > 1:
            assert problem_areas[0]["confidence"] <= problem_areas[1]["confidence"]

    def test_overall_quality_assessment(self, analyzer, sample_ocr_response):
        """Test overall quality assessment"""
        result = analyzer.analyze_confidence(sample_ocr_response)

        quality = result["summary"]["overall_quality"]
        assert quality in ["excellent", "good", "moderate", "poor"]

        # With average confidence around 0.73, should be "moderate"
        assert quality == "moderate"

    def test_empty_response(self, analyzer):
        """Test handling of empty OCR response"""
        empty_response = OCRResponse(result=[])
        result = analyzer.analyze_confidence(empty_response)

        assert result["summary"]["total_words"] == 0
        assert result["summary"]["average_confidence"] == 0
        assert len(result["problem_areas"]) == 0

    def test_high_confidence_response(self, analyzer):
        """Test response with all high confidence words"""
        words = [
            WordBlock(words=f"Word{i}", confidence=0.96 + i * 0.01,
                     location=[[0, 0], [100, 0], [100, 30], [0, 30]])
            for i in range(4)
        ]

        ocr_details = OCRDetails(words_block_list=words, direction=0.0)
        ocr_result = OCRResult(ocr_result=ocr_details)
        response = OCRResponse(result=[ocr_result])

        result = analyzer.analyze_confidence(response)

        assert result["summary"]["overall_quality"] == "excellent"
        assert result["distribution"]["high"]["count"] == 4
        assert len(result["problem_areas"]) == 0