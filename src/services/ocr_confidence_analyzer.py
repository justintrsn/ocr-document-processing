"""
OCR Confidence Analyzer - Provides detailed confidence analysis
"""

import logging
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass

from src.models.ocr_models import OCRResponse

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceDistribution:
    """Confidence distribution statistics"""
    high_confidence: int = 0      # >= 95%
    medium_confidence: int = 0    # 80-95%
    low_confidence: int = 0       # 60-80%
    very_low_confidence: int = 0  # < 60%

    high_confidence_words: List[str] = None
    medium_confidence_words: List[Tuple[str, float]] = None
    low_confidence_words: List[Tuple[str, float]] = None
    very_low_confidence_words: List[Tuple[str, float]] = None

    def __post_init__(self):
        if self.high_confidence_words is None:
            self.high_confidence_words = []
        if self.medium_confidence_words is None:
            self.medium_confidence_words = []
        if self.low_confidence_words is None:
            self.low_confidence_words = []
        if self.very_low_confidence_words is None:
            self.very_low_confidence_words = []


class OCRConfidenceAnalyzer:
    """Analyze OCR confidence in detail"""

    # Confidence thresholds
    HIGH_CONFIDENCE = 0.95
    MEDIUM_CONFIDENCE = 0.80
    LOW_CONFIDENCE = 0.60

    def analyze_confidence(self, ocr_response: OCRResponse) -> Dict[str, Any]:
        """
        Analyze OCR confidence with detailed breakdown

        Args:
            ocr_response: OCR response from Huawei service

        Returns:
            Detailed confidence analysis
        """
        distribution = ConfidenceDistribution()
        all_confidences = []
        problem_areas = []

        if ocr_response.result:
            for result in ocr_response.result:
                if result.ocr_result and result.ocr_result.words_block_list:
                    for word_block in result.ocr_result.words_block_list:
                        if word_block.confidence is not None:
                            confidence = word_block.confidence
                            words = word_block.words
                            all_confidences.append(confidence)

                            # Categorize by confidence level
                            if confidence >= self.HIGH_CONFIDENCE:
                                distribution.high_confidence += 1
                                distribution.high_confidence_words.append(words)
                            elif confidence >= self.MEDIUM_CONFIDENCE:
                                distribution.medium_confidence += 1
                                distribution.medium_confidence_words.append((words, confidence))
                            elif confidence >= self.LOW_CONFIDENCE:
                                distribution.low_confidence += 1
                                distribution.low_confidence_words.append((words, confidence))
                            else:
                                distribution.very_low_confidence += 1
                                distribution.very_low_confidence_words.append((words, confidence))

                            # Track problem areas
                            if confidence < self.MEDIUM_CONFIDENCE:
                                problem_areas.append({
                                    "text": words,
                                    "confidence": confidence,
                                    "location": word_block.location,
                                    "severity": self._get_severity(confidence)
                                })

        # Calculate statistics
        total_words = len(all_confidences)
        avg_confidence = sum(all_confidences) / total_words if all_confidences else 0.0
        min_confidence = min(all_confidences) if all_confidences else 0.0
        max_confidence = max(all_confidences) if all_confidences else 0.0

        # Calculate percentages
        high_pct = (distribution.high_confidence / total_words * 100) if total_words > 0 else 0
        medium_pct = (distribution.medium_confidence / total_words * 100) if total_words > 0 else 0
        low_pct = (distribution.low_confidence / total_words * 100) if total_words > 0 else 0
        very_low_pct = (distribution.very_low_confidence / total_words * 100) if total_words > 0 else 0

        # Determine overall quality
        overall_quality = self._determine_quality(avg_confidence, distribution)

        # Identify critical fields with low confidence
        critical_fields = self._identify_critical_fields(distribution)

        return {
            "summary": {
                "total_words": total_words,
                "average_confidence": round(avg_confidence, 4),
                "min_confidence": round(min_confidence, 4),
                "max_confidence": round(max_confidence, 4),
                "overall_quality": overall_quality
            },
            "distribution": {
                "high_confidence": {
                    "count": distribution.high_confidence,
                    "percentage": round(high_pct, 1),
                    "threshold": f">= {self.HIGH_CONFIDENCE:.0%}"
                },
                "medium_confidence": {
                    "count": distribution.medium_confidence,
                    "percentage": round(medium_pct, 1),
                    "threshold": f"{self.MEDIUM_CONFIDENCE:.0%}-{self.HIGH_CONFIDENCE:.0%}",
                    "words": distribution.medium_confidence_words[:5]  # Top 5 examples
                },
                "low_confidence": {
                    "count": distribution.low_confidence,
                    "percentage": round(low_pct, 1),
                    "threshold": f"{self.LOW_CONFIDENCE:.0%}-{self.MEDIUM_CONFIDENCE:.0%}",
                    "words": distribution.low_confidence_words[:5]
                },
                "very_low_confidence": {
                    "count": distribution.very_low_confidence,
                    "percentage": round(very_low_pct, 1),
                    "threshold": f"< {self.LOW_CONFIDENCE:.0%}",
                    "words": distribution.very_low_confidence_words
                }
            },
            "problem_areas": problem_areas,
            "critical_fields": critical_fields,
            "recommendations": self._get_recommendations(distribution, problem_areas)
        }

    def _get_severity(self, confidence: float) -> str:
        """Get severity level based on confidence"""
        if confidence >= self.MEDIUM_CONFIDENCE:
            return "low"
        elif confidence >= self.LOW_CONFIDENCE:
            return "medium"
        else:
            return "high"

    def _determine_quality(self, avg_confidence: float, distribution: ConfidenceDistribution) -> str:
        """Determine overall OCR quality"""
        total_words = (distribution.high_confidence + distribution.medium_confidence +
                      distribution.low_confidence + distribution.very_low_confidence)

        if total_words == 0:
            return "no_data"

        # Calculate quality score (weighted)
        high_weight = distribution.high_confidence * 1.0
        medium_weight = distribution.medium_confidence * 0.7
        low_weight = distribution.low_confidence * 0.3
        very_low_weight = distribution.very_low_confidence * 0.0

        quality_score = (high_weight + medium_weight + low_weight + very_low_weight) / total_words

        if quality_score >= 0.95 and distribution.very_low_confidence == 0:
            return "excellent"
        elif quality_score >= 0.85 and distribution.very_low_confidence <= 1:
            return "good"
        elif quality_score >= 0.70:
            return "acceptable"
        elif quality_score >= 0.50:
            return "poor"
        else:
            return "very_poor"

    def _identify_critical_fields(self, distribution: ConfidenceDistribution) -> List[Dict]:
        """Identify critical fields that may have low confidence"""
        critical_keywords = [
            "name", "date", "id", "nric", "number", "no.",
            "amount", "total", "diagnosis", "medication"
        ]

        critical_fields = []

        # Check medium and low confidence words for critical fields
        for word, conf in distribution.medium_confidence_words + distribution.low_confidence_words:
            word_lower = word.lower()
            for keyword in critical_keywords:
                if keyword in word_lower:
                    critical_fields.append({
                        "field": word,
                        "confidence": conf,
                        "risk": "medium" if conf >= self.MEDIUM_CONFIDENCE else "high"
                    })
                    break

        return critical_fields

    def _get_recommendations(self, distribution: ConfidenceDistribution, problem_areas: List) -> List[str]:
        """Get recommendations based on confidence analysis"""
        recommendations = []

        total_words = (distribution.high_confidence + distribution.medium_confidence +
                      distribution.low_confidence + distribution.very_low_confidence)

        if total_words == 0:
            recommendations.append("No text detected - check image quality")
            return recommendations

        # Check for very low confidence words
        if distribution.very_low_confidence > 0:
            pct = (distribution.very_low_confidence / total_words) * 100
            recommendations.append(f"Manual review recommended: {pct:.1f}% of text has very low confidence")

        # Check for low confidence concentration
        if distribution.low_confidence > total_words * 0.2:
            recommendations.append("Consider image enhancement or re-scanning")

        # Check problem areas
        if len(problem_areas) > 5:
            recommendations.append(f"Multiple problem areas detected ({len(problem_areas)} regions)")

        # Check specific issues
        for area in problem_areas[:3]:  # Top 3 problem areas
            if area["severity"] == "high":
                recommendations.append(f"Critical: '{area['text'][:30]}...' needs manual verification")

        if not recommendations:
            recommendations.append("OCR quality is good - automatic processing recommended")

        return recommendations

    def get_confidence_report(self, ocr_response: OCRResponse) -> str:
        """
        Generate a human-readable confidence report

        Args:
            ocr_response: OCR response from Huawei service

        Returns:
            Formatted report string
        """
        analysis = self.analyze_confidence(ocr_response)

        report = []
        report.append("=" * 60)
        report.append("OCR CONFIDENCE ANALYSIS REPORT")
        report.append("=" * 60)

        # Summary
        summary = analysis["summary"]
        report.append(f"\n📊 SUMMARY")
        report.append(f"  Total Words: {summary['total_words']}")
        report.append(f"  Average Confidence: {summary['average_confidence']:.2%}")
        report.append(f"  Range: {summary['min_confidence']:.2%} - {summary['max_confidence']:.2%}")
        report.append(f"  Overall Quality: {summary['overall_quality'].upper()}")

        # Distribution
        dist = analysis["distribution"]
        report.append(f"\n📈 CONFIDENCE DISTRIBUTION")
        report.append(f"  High (>= 95%): {dist['high_confidence']['count']} words ({dist['high_confidence']['percentage']:.1f}%)")
        report.append(f"  Medium (80-95%): {dist['medium_confidence']['count']} words ({dist['medium_confidence']['percentage']:.1f}%)")
        report.append(f"  Low (60-80%): {dist['low_confidence']['count']} words ({dist['low_confidence']['percentage']:.1f}%)")
        report.append(f"  Very Low (< 60%): {dist['very_low_confidence']['count']} words ({dist['very_low_confidence']['percentage']:.1f}%)")

        # Problem areas
        if analysis["problem_areas"]:
            report.append(f"\n⚠️ PROBLEM AREAS")
            for area in analysis["problem_areas"][:5]:
                report.append(f"  - '{area['text'][:50]}' ({area['confidence']:.2%}) - Severity: {area['severity']}")

        # Critical fields
        if analysis["critical_fields"]:
            report.append(f"\n🔴 CRITICAL FIELDS WITH ISSUES")
            for field in analysis["critical_fields"]:
                report.append(f"  - {field['field']}: {field['confidence']:.2%} (Risk: {field['risk']})")

        # Recommendations
        report.append(f"\n💡 RECOMMENDATIONS")
        for rec in analysis["recommendations"]:
            report.append(f"  • {rec}")

        report.append("\n" + "=" * 60)

        return "\n".join(report)