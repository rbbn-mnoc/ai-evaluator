"""Basic tests for AI Evaluator."""

import pytest
from ai_evaluator.prompts import get_evaluation_prompt


def test_evaluation_prompt_generation():
    """Test that evaluation prompt is generated correctly."""
    issue_data = {
        "issue_id": 123,
        "project_identifier": "test-project",
        "subject": "Test Issue",
        "issue_type": "zabbix_check",
        "class_id": "test_class",
        "issue_resolve_method": "manual",
        "issue_resolve_in": "5 minutes",
        "issue_resolve_by": "operator"
    }
    
    ai_analysis = "AI recommended action X"
    resolution_notes = "Operator performed action Y"
    
    prompt = get_evaluation_prompt(
        issue_data=issue_data,
        ai_analysis=ai_analysis,
        resolution_notes=resolution_notes,
        knowledge_data={},
        zabbix_data={}
    )
    
    assert "Issue #123" in prompt
    assert "test-project" in prompt
    assert "AI recommended action X" in prompt
    assert "Operator performed action Y" in prompt
    assert "Solution Quality" in prompt
    assert "Automation Potential" in prompt


def test_prompt_with_empty_data():
    """Test prompt generation with minimal data."""
    issue_data = {
        "issue_id": 456,
        "project_identifier": "minimal",
        "subject": "Minimal Issue"
    }
    
    prompt = get_evaluation_prompt(
        issue_data=issue_data,
        ai_analysis="",
        resolution_notes="",
        knowledge_data={},
        zabbix_data={}
    )
    
    assert "Issue #456" in prompt
    assert "No AI analysis available" in prompt
    assert "No resolution notes provided" in prompt
