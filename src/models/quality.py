"""Image quality assessment model."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class QualityIssue(BaseModel):
    """Individual quality issue detected."""
    type: str = Field(..., description="Type of issue (blur, contrast, resolution, noise)")
    severity: str = Field(..., description="Severity level (low, medium, high)")
    description: str = Field(..., description="Description of the issue")
    impact_on_ocr: str = Field(..., description="Expected impact on OCR accuracy")


class QualityAssessment(BaseModel):
    """Image quality assessment results."""

    # Individual quality metrics (0-100 scale)
    sharpness_score: float = Field(..., ge=0, le=100, description="Image sharpness score")
    contrast_score: float = Field(..., ge=0, le=100, description="Image contrast score")
    resolution_score: float = Field(..., ge=0, le=100, description="Resolution adequacy score")
    noise_score: float = Field(..., ge=0, le=100, description="Noise level score (higher is better)")

    # Additional metrics
    brightness_score: float = Field(default=100.0, ge=0, le=100, description="Brightness adequacy score")
    text_orientation_score: float = Field(default=100.0, ge=0, le=100, description="Text alignment score")

    # Detected issues
    issues: List[QualityIssue] = Field(default_factory=list, description="List of detected quality issues")

    # Image properties
    resolution_dpi: Optional[int] = Field(None, description="Image DPI resolution")
    dimensions: Optional[Dict[str, int]] = Field(None, description="Image dimensions (width, height)")
    file_size_mb: Optional[float] = Field(None, description="File size in MB")

    @field_validator("sharpness_score", "contrast_score", "resolution_score", "noise_score",
                     "brightness_score", "text_orientation_score")
    @classmethod
    def validate_scores(cls, v, info):
        """Ensure scores are within valid range."""
        if not 0 <= v <= 100:
            raise ValueError(f"{info.field_name} must be between 0 and 100")
        return v

    @property
    def overall_score(self) -> float:
        """Calculate weighted overall quality score."""
        # Weights for different quality aspects
        weights = {
            "sharpness": 0.3,
            "contrast": 0.25,
            "resolution": 0.2,
            "noise": 0.15,
            "brightness": 0.05,
            "orientation": 0.05
        }

        score = (
            self.sharpness_score * weights["sharpness"] +
            self.contrast_score * weights["contrast"] +
            self.resolution_score * weights["resolution"] +
            self.noise_score * weights["noise"] +
            self.brightness_score * weights["brightness"] +
            self.text_orientation_score * weights["orientation"]
        )

        return round(score, 2)

    @property
    def quality_level(self) -> str:
        """Determine quality level based on overall score."""
        score = self.overall_score
        if score >= 80:
            return "excellent"
        elif score >= 60:
            return "good"
        elif score >= 40:
            return "fair"
        else:
            return "poor"

    @property
    def is_acceptable(self) -> bool:
        """Check if image quality is acceptable for OCR."""
        # Image is acceptable if overall score is above 40 and no critical issues
        has_critical_issues = any(
            issue.severity == "high" for issue in self.issues
        )
        return self.overall_score >= 40 and not has_critical_issues

    def detect_issues(self) -> None:
        """Detect and categorize quality issues based on scores."""
        self.issues = []

        # Check sharpness
        if self.sharpness_score < 30:
            self.issues.append(QualityIssue(
                type="blur",
                severity="high",
                description="Image is severely blurred",
                impact_on_ocr="OCR accuracy will be significantly reduced"
            ))
        elif self.sharpness_score < 50:
            self.issues.append(QualityIssue(
                type="blur",
                severity="medium",
                description="Image has moderate blur",
                impact_on_ocr="Some characters may be misrecognized"
            ))
        elif self.sharpness_score < 70:
            self.issues.append(QualityIssue(
                type="blur",
                severity="low",
                description="Image has slight blur",
                impact_on_ocr="Minor impact on OCR accuracy"
            ))

        # Check contrast
        if self.contrast_score < 30:
            self.issues.append(QualityIssue(
                type="contrast",
                severity="high",
                description="Very poor contrast between text and background",
                impact_on_ocr="Text detection will be severely impaired"
            ))
        elif self.contrast_score < 50:
            self.issues.append(QualityIssue(
                type="contrast",
                severity="medium",
                description="Low contrast between text and background",
                impact_on_ocr="Some text may not be detected"
            ))

        # Check resolution
        if self.resolution_score < 30 or (self.resolution_dpi and self.resolution_dpi < 150):
            self.issues.append(QualityIssue(
                type="resolution",
                severity="high",
                description="Resolution too low for accurate OCR",
                impact_on_ocr="Small text will be illegible"
            ))
        elif self.resolution_score < 50 or (self.resolution_dpi and self.resolution_dpi < 200):
            self.issues.append(QualityIssue(
                type="resolution",
                severity="medium",
                description="Resolution below optimal level",
                impact_on_ocr="Fine details may be lost"
            ))

        # Check noise
        if self.noise_score < 30:
            self.issues.append(QualityIssue(
                type="noise",
                severity="high",
                description="Excessive noise in image",
                impact_on_ocr="False text detection and character errors likely"
            ))
        elif self.noise_score < 50:
            self.issues.append(QualityIssue(
                type="noise",
                severity="medium",
                description="Significant noise present",
                impact_on_ocr="Increased OCR errors expected"
            ))

        # Check brightness
        if self.brightness_score < 20 or self.brightness_score > 95:
            self.issues.append(QualityIssue(
                type="brightness",
                severity="high",
                description="Image is too dark or too bright",
                impact_on_ocr="Text may be completely unreadable"
            ))
        elif self.brightness_score < 40 or self.brightness_score > 85:
            self.issues.append(QualityIssue(
                type="brightness",
                severity="medium",
                description="Suboptimal brightness levels",
                impact_on_ocr="Some text regions may be poorly recognized"
            ))

        # Check orientation
        if self.text_orientation_score < 50:
            self.issues.append(QualityIssue(
                type="orientation",
                severity="medium",
                description="Text appears skewed or rotated",
                impact_on_ocr="OCR accuracy reduced for angled text"
            ))

    def get_recommendations(self) -> List[str]:
        """Get recommendations for improving image quality."""
        recommendations = []

        for issue in self.issues:
            if issue.type == "blur" and issue.severity in ["high", "medium"]:
                recommendations.append("Rescan the document with steady hands or use a document scanner")
            elif issue.type == "contrast" and issue.severity in ["high", "medium"]:
                recommendations.append("Adjust lighting conditions or use image enhancement")
            elif issue.type == "resolution" and issue.severity in ["high", "medium"]:
                recommendations.append("Scan at higher resolution (minimum 300 DPI recommended)")
            elif issue.type == "noise" and issue.severity in ["high", "medium"]:
                recommendations.append("Clean the scanner or camera lens, use better lighting")
            elif issue.type == "brightness":
                recommendations.append("Adjust exposure settings or lighting conditions")
            elif issue.type == "orientation":
                recommendations.append("Ensure document is properly aligned when scanning")

        return list(set(recommendations))  # Remove duplicates

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "overall_score": self.overall_score,
            "quality_level": self.quality_level,
            "is_acceptable": self.is_acceptable,
            "scores": {
                "sharpness": self.sharpness_score,
                "contrast": self.contrast_score,
                "resolution": self.resolution_score,
                "noise": self.noise_score,
                "brightness": self.brightness_score,
                "orientation": self.text_orientation_score
            },
            "issues": [
                {
                    "type": issue.type,
                    "severity": issue.severity,
                    "description": issue.description
                }
                for issue in self.issues
            ],
            "recommendations": self.get_recommendations(),
            "image_properties": {
                "resolution_dpi": self.resolution_dpi,
                "dimensions": self.dimensions,
                "file_size_mb": self.file_size_mb
            }
        }