from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class WordBlock(BaseModel):
    words: str
    confidence: Optional[float] = None
    location: Optional[List[List[int]]] = None
    char_list: Optional[List[Dict[str, Any]]] = None


class OCRResult(BaseModel):
    words_block_list: List[WordBlock]
    direction: Optional[float] = None
    words_block_count: Optional[int] = None


class TableCell(BaseModel):
    start_row: int
    end_row: int
    start_col: int
    end_col: int
    location: List[List[int]]
    words: str
    confidence: Optional[float] = None


class TableResult(BaseModel):
    table_count: int
    table_list: List[Dict[str, Any]]


class FormulaBlock(BaseModel):
    words: str
    location: List[List[int]]
    confidence: Optional[float] = None


class FormulaResult(BaseModel):
    formula_count: int
    formula_list: List[FormulaBlock]


class KVBlock(BaseModel):
    key: str
    value: str
    key_location: Optional[List[List[int]]] = None
    value_location: Optional[List[List[int]]] = None
    key_confidence: Optional[float] = None
    value_confidence: Optional[float] = None


class KVResult(BaseModel):
    kv_block_count: int
    kv_block_list: List[KVBlock]


class LayoutBlock(BaseModel):
    layout: str
    location: List[List[int]]
    text: Optional[str] = None
    confidence: Optional[float] = None


class LayoutResult(BaseModel):
    layout_block_count: int
    layout_block_list: List[LayoutBlock]


class ResultItem(BaseModel):
    ocr_result: Optional[OCRResult] = None
    table_result: Optional[TableResult] = None
    formula_result: Optional[FormulaResult] = None
    kv_result: Optional[KVResult] = None
    layout_result: Optional[LayoutResult] = None


class OCRResponse(BaseModel):
    result: List[ResultItem]
    error_code: Optional[str] = None
    error_msg: Optional[str] = None