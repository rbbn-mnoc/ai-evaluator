"""AI Evaluator - Evaluation prompts for post-resolution analysis."""

def get_evaluation_prompt(
    issue_data: dict,
    ai_analysis: str,
    resolution_notes: str,
    knowledge_data: dict,
    zabbix_data: dict,
) -> str:
    """
    Generate evaluation prompt for assessing resolution quality.
    
    This prompt is designed for a different AI model (Claude Opus) to provide
    unbiased evaluation of how the issue was resolved.
    """
    
    issue_id = issue_data.get("issue_id")
    project = issue_data.get("project_identifier")
    subject = issue_data.get("subject")
    issue_type = issue_data.get("issue_type", "unknown")
    class_id = issue_data.get("class_id", "")
    
    resolve_method = issue_data.get("issue_resolve_method", "unknown")
    resolve_in = issue_data.get("issue_resolve_in", "unknown")
    resolve_by = issue_data.get("issue_resolve_by", "unknown")
    
    prompt = f"""# Resolution Quality Evaluation

You are an expert technical evaluator assessing the quality of issue resolution in a network monitoring system.

## Issue Details
- **Issue ID**: #{issue_id}
- **Project**: {project}
- **Subject**: {subject}
- **Issue Type**: {issue_type}
- **Class ID**: {class_id or 'Not classified'}
- **Resolution Method**: {resolve_method}
- **Resolution Time**: {resolve_in}
- **Resolved By**: {resolve_by}

## Context

### Original AI Analysis
The AI provided this analysis when the issue was created:

```
{ai_analysis or 'No AI analysis available'}
```

### Resolution Notes
Human operator provided these notes during resolution:

```
{resolution_notes or 'No resolution notes provided'}
```

### Historical Knowledge
{_format_knowledge(knowledge_data)}

### Zabbix Context
{_format_zabbix(zabbix_data)}

## Evaluation Task

Provide a comprehensive but concise evaluation with scores (1-10) for each metric:

### 1. Solution Quality (1-10)
**Score**: [Your score]

Evaluate the quality of the AI's original recommendation:
- Was the analysis accurate and relevant?
- Did it identify the root cause correctly?
- Were the recommended actions appropriate?
- Did it leverage historical knowledge effectively?

**Analysis**: [2-3 sentences explaining your score]

### 2. Adherence to Solution (1-10)
**Score**: [Your score]

Assess how well the operator followed the AI recommendation:
- Did they follow the suggested troubleshooting steps?
- Did they deviate from recommendations? If so, why?
- Was deviation justified and effective?

**Analysis**: [2-3 sentences explaining your score]

### 3. Operator Effort (1-10)
**Score**: [Your score] (10 = minimal effort, 1 = extensive effort)

Evaluate the level of work required:
- How much investigation did the operator need to do?
- Was resolution straightforward or complex?
- Did they need to escalate or consult other resources?

**Analysis**: [2-3 sentences explaining your score]

### 4. Automation Potential (1-10)
**Score**: [Your score]

Assess potential for automation:
- Could this resolution be fully automated?
- What percentage of similar issues could be auto-resolved?
- What barriers exist to automation?

**Analysis**: [2-3 sentences with specific automation recommendations]

### 5. Resolution Efficiency (1-10)
**Score**: [Your score]

Overall efficiency assessment:
- Was the issue resolved in optimal time?
- Were resources used effectively?
- Could the process be improved?

**Analysis**: [2-3 sentences explaining your score]

## Summary

Provide a brief overall assessment (3-4 sentences) covering:
- Key strengths in the resolution process
- Main areas for improvement
- Most impactful automation opportunity

## Output Format

Return your evaluation in the following JSON structure:

```json
{{
    "issue_id": {issue_id},
    "evaluated_at": "[ISO timestamp]",
    "model": "[model used]",
    "metrics": {{
        "solution_quality": [1-10],
        "adherence_to_solution": [1-10],
        "operator_effort": [1-10],
        "automation_potential": [1-10],
        "resolution_efficiency": [1-10]
    }},
    "analysis": {{
        "solution_quality_notes": "...",
        "adherence_notes": "...",
        "operator_effort_notes": "...",
        "automation_recommendations": "...",
        "efficiency_notes": "..."
    }},
    "summary": "...",
    "improvement_priority": "high|medium|low"
}}
```

Focus on actionable insights that can improve future resolutions.
"""
    
    return prompt


def _format_knowledge(knowledge_data: dict) -> str:
    """Format knowledge data for prompt context."""
    if not knowledge_data:
        return "No historical knowledge available for this class."
    
    total_occurrences = knowledge_data.get("total_occurrences", 0)
    last_seen = knowledge_data.get("last_seen", "unknown")
    common_resolution = knowledge_data.get("common_resolution_method", "unknown")
    avg_duration = knowledge_data.get("average_resolution_time", "unknown")
    
    return f"""
- Total historical occurrences: {total_occurrences}
- Last seen: {last_seen}
- Common resolution method: {common_resolution}
- Average resolution time: {avg_duration}
- Pattern: {knowledge_data.get('pattern_summary', 'No clear pattern identified')}
"""


def _format_zabbix(zabbix_data: dict) -> str:
    """Format Zabbix data for prompt context."""
    if not zabbix_data or not zabbix_data.get("alerts"):
        return "No Zabbix alerts in correlation window."
    
    alerts = zabbix_data.get("alerts", [])
    return f"""
- Correlated alerts count: {len(alerts)}
- Time window: {zabbix_data.get('time_window', 'unknown')}
- Related devices: {', '.join(set(a.get('host', 'unknown') for a in alerts[:5]))}
"""
