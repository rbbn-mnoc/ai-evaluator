#!/usr/bin/env python3
"""Test script to trigger manual evaluation for a Redmine issue."""

import os
import sys
import requests
from datetime import datetime


def fetch_issue_from_redmine(issue_id: int) -> dict:
    """Fetch issue data from Redmine API."""
    redmine_url = os.getenv("REDMINE_URL", "https://redmine.ribbonmaas.net")
    api_key = os.getenv("REDMINE_API_KEY", "")
    
    if not api_key:
        print("❌ Error: REDMINE_API_KEY environment variable not set")
        sys.exit(1)
    
    url = f"{redmine_url}/issues/{issue_id}.json"
    headers = {"X-Redmine-API-Key": api_key}
    
    print(f"🔍 Fetching issue #{issue_id} from Redmine...")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        issue_data = response.json()["issue"]
        print(f"✓ Found issue: {issue_data['subject'][:60]}...")
        
        return issue_data
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching issue from Redmine: {e}")
        sys.exit(1)


def build_evaluation_request(issue_data: dict) -> dict:
    """Build evaluation request payload from Redmine issue data."""
    # Get custom fields
    custom_fields = {cf["id"]: cf.get("value", "") for cf in issue_data.get("custom_fields", [])}
    
    return {
        "issue_id": issue_data["id"],
        "project_id": issue_data["project"]["id"],
        "project_identifier": issue_data["project"].get("identifier", "unknown"),
        "subject": issue_data["subject"],
        "description": issue_data.get("description", ""),
        "author": issue_data.get("author", {}).get("name", "Unknown"),
        "tracker": issue_data.get("tracker", {}).get("name", "Unknown"),
        "status": issue_data.get("status", {}).get("name", "Unknown"),
        "priority": issue_data.get("priority", {}).get("name", "Unknown"),
        "created_on": issue_data.get("created_on", datetime.utcnow().isoformat()),
        "updated_on": issue_data.get("updated_on", datetime.utcnow().isoformat()),
        "issue_type": custom_fields.get(43, "manual"),  # Field 43 = Issue Type
        "alarming_state": custom_fields.get(44, "false"),  # Field 44 = Alarming State
        "class_id": custom_fields.get(45, ""),  # Field 45 = Class ID
        "issue_resolve_method": custom_fields.get(46, ""),  # Field 46 = Resolve Method
        "issue_resolve_in": custom_fields.get(47, ""),  # Field 47 = Resolve In
        "issue_resolve_by": custom_fields.get(48, ""),  # Field 48 = Resolve By
        "issue_resolve_at": custom_fields.get(49, ""),  # Field 49 = Resolve At
        "collector_name": custom_fields.get(54, ""),  # Field 54 = Collector
        "trigger_name": custom_fields.get(55, ""),  # Field 55 = Trigger Name
        "known_error_id": custom_fields.get(56, ""),  # Field 56 = Known Error ID
        "zabbix_event_id": custom_fields.get(57, ""),  # Field 57 = Zabbix Event ID
    }


def trigger_evaluation(issue_id: int, evaluator_url: str = "http://localhost:8002/evaluate"):
    """Trigger evaluation for a specific issue."""
    username = os.getenv("SERVICE_USERNAME", "evaluator")
    password = os.getenv("SERVICE_PASSWORD", "changeme")
    
    # Fetch issue from Redmine
    issue_data = fetch_issue_from_redmine(issue_id)
    
    # Build evaluation request
    request_payload = build_evaluation_request(issue_data)
    
    print(f"\n📊 Triggering evaluation for issue #{issue_id}...")
    print(f"   URL: {evaluator_url}")
    print(f"   Project: {request_payload['project_identifier']}")
    print(f"   Status: {request_payload['status']}")
    print(f"   Type: {request_payload['issue_type']}")
    
    try:
        response = requests.post(
            evaluator_url,
            json=request_payload,
            auth=(username, password),
            timeout=120  # Evaluations can take 30-60s
        )
        
        response.raise_for_status()
        result = response.json()
        
        print(f"\n✅ Evaluation completed!")
        print(f"   Success: {result.get('success')}")
        print(f"   Message: {result.get('message')}")
        
        if result.get("evaluation"):
            eval_data = result["evaluation"]
            if "metrics" in eval_data:
                metrics = eval_data["metrics"]
                print(f"\n📈 Evaluation Metrics:")
                print(f"   Solution Quality: {metrics.get('solution_quality', 'N/A')}/10")
                print(f"   Adherence to Solution: {metrics.get('adherence_to_solution', 'N/A')}/10")
                print(f"   Operator Effort: {metrics.get('operator_effort', 'N/A')}/10")
                print(f"   Automation Potential: {metrics.get('automation_potential', 'N/A')}/10")
                print(f"   Resolution Efficiency: {metrics.get('resolution_efficiency', 'N/A')}/10")
            
            if "summary" in eval_data:
                print(f"\n📝 Summary:")
                print(f"   {eval_data['summary'][:200]}...")
        
        return result
    
    except requests.exceptions.Timeout:
        print(f"\n❌ Error: Evaluation timed out after 120 seconds")
        print(f"   Check ai-evaluator logs for details")
        sys.exit(1)
    
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error triggering evaluation: {e}")
        if hasattr(e.response, 'text'):
            print(f"   Response: {e.response.text[:200]}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_evaluation.py <issue_id> [evaluator_url]")
        print("Example: python test_evaluation.py 691332")
        print("Example: python test_evaluation.py 691332 http://localhost:8002/evaluate")
        sys.exit(1)
    
    issue_id = int(sys.argv[1])
    evaluator_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8002/evaluate"
    
    trigger_evaluation(issue_id, evaluator_url)
