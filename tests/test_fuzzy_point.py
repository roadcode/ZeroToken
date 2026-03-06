"""
Test fuzzy_point - OperationRecord and trajectory fuzzy point support.
"""

import pytest
from zerotoken.controller import OperationRecord, PageState


class TestOperationRecordFuzzyPoint:
    """Test OperationRecord fuzzy_point field."""

    def test_operation_record_with_fuzzy_point(self):
        """Test creating OperationRecord with fuzzy_point."""
        ps = PageState("https://a.com", "Title")
        record = OperationRecord(
            step=1,
            action="extract_data",
            params={},
            result={"success": True},
            page_state=ps,
            fuzzy_point={"requires_judgment": True, "reason": "验证码需识别"}
        )
        d = record.to_dict()
        assert d["fuzzy_point"]["requires_judgment"] is True
        assert d["fuzzy_point"]["reason"] == "验证码需识别"

    def test_operation_record_with_fuzzy_point_and_hint(self):
        """Test fuzzy_point with hint field."""
        ps = PageState("https://a.com", "Title")
        record = OperationRecord(
            step=1,
            action="extract_data",
            params={},
            result={},
            page_state=ps,
            fuzzy_point={
                "requires_judgment": True,
                "reason": "列表项需选择",
                "hint": "根据用户意图选择第一项"
            }
        )
        d = record.to_dict()
        assert d["fuzzy_point"]["hint"] == "根据用户意图选择第一项"

    def test_operation_record_without_fuzzy_point(self):
        """Test OperationRecord without fuzzy_point omits it from dict."""
        ps = PageState("https://a.com", "Title")
        record = OperationRecord(
            step=1,
            action="click",
            params={"selector": "#btn"},
            result={"success": True},
            page_state=ps
        )
        d = record.to_dict()
        assert "fuzzy_point" not in d
