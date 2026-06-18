#!/usr/bin/env python3
"""
fetch_issues.py
Fetches all issues for a GitLab milestone and saves them to a JSON file.

Usage:
    python fetch_issues.py \
        --gitlab-url https://gitlab.com \
        --project-id my-org/my-repo \
        --milestone v2.4.0 \
        --token glpat-xxxx \
        --output /tmp/issues.json
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error


def get_token(args_token: str | None) -> str:
    """Resolve token: CLI arg > env var > .env file."""
    if args_token:
        return args_token
    token = os.environ.get("GITLAB_TOKEN", "")
    if token:
        return token
    # Try .env in cwd
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GITLAB_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    print("❌  No GitLab token found. Set GITLAB_TOKEN env var or pass --token.", file=sys.stderr)
    sys.exit(1)


def api_get(gitlab_url: str, path: str, token: str) -> list | dict:
    """Make a paginated GET request to the GitLab API."""
    base = f"{gitlab_url.rstrip('/')}/api/v4{path}"
    results = []
    page = 1
    while True:
        sep = "&" if "?" in base else "?"
        url = f"{base}{sep}per_page=100&page={page}"
        req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": token})
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list):
                    results.extend(data)
                    if len(data) < 100:
                        break
                    page += 1
                else:
                    return data
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"❌  HTTP {e.code} from GitLab API: {body}", file=sys.stderr)
            sys.exit(1)
    return results


def resolve_milestone(gitlab_url: str, project_id: str, milestone_ref: str, token: str) -> dict:
    """Find milestone by name or numeric ID."""
    enc = urllib.parse.quote(str(project_id), safe="")
    # If numeric, try direct lookup first
    if milestone_ref.isdigit():
        m = api_get(gitlab_url, f"/projects/{enc}/milestones/{milestone_ref}", token)
        if isinstance(m, dict) and "id" in m:
            return m
    # Search by title
    milestones = api_get(gitlab_url, f"/projects/{enc}/milestones?search={urllib.parse.quote(milestone_ref)}", token)
    for m in milestones:
        if m["title"] == milestone_ref:
            return m
    # List available and exit
    all_ms = api_get(gitlab_url, f"/projects/{enc}/milestones", token)
    names = [m["title"] for m in all_ms]
    print(f"❌  Milestone '{milestone_ref}' not found.", file=sys.stderr)
    print(f"    Available milestones: {', '.join(names) or '(none)'}", file=sys.stderr)
    sys.exit(1)


def fetch_issues(gitlab_url: str, project_id: str, milestone_id: int, token: str) -> list:
    """Fetch all issues (open + closed) for a milestone."""
    enc = urllib.parse.quote(str(project_id), safe="")
    issues = api_get(
        gitlab_url,
        f"/projects/{enc}/issues?milestone_id={milestone_id}&scope=all&state=all",
        token,
    )
    return issues


def simplify_issue(issue: dict) -> dict:
    """Extract only the fields we need."""
    return {
        "id": issue.get("id"),
        "iid": issue.get("iid"),
        "title": issue.get("title", ""),
        "description": (issue.get("description") or "").strip(),
        "state": issue.get("state", "opened"),
        "assignees": [a["username"] for a in issue.get("assignees", [])],
        "milestone_name": (issue.get("milestone") or {}).get("title", ""),
        "due_date": (issue.get("milestone") or {}).get("due_date", ""),
        "web_url": issue.get("web_url", ""),
        "labels": issue.get("labels", []),
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch GitLab milestone issues.")
    parser.add_argument("--gitlab-url", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--milestone", required=True)
    parser.add_argument("--token", default=None)
    parser.add_argument("--output", default="/tmp/issues.json")
    args = parser.parse_args()

    token = get_token(args.token)

    print(f"🔍  Resolving milestone '{args.milestone}'...")
    milestone = resolve_milestone(args.gitlab_url, args.project_id, args.milestone, token)
    print(f"✅  Found milestone: {milestone['title']} (ID: {milestone['id']})")

    print(f"📥  Fetching issues...")
    raw_issues = fetch_issues(args.gitlab_url, args.project_id, milestone["id"], token)
    issues = [simplify_issue(i) for i in raw_issues]

    open_count = sum(1 for i in issues if i["state"] == "opened")
    closed_count = sum(1 for i in issues if i["state"] == "closed")
    print(f"✅  {len(issues)} issues fetched ({open_count} open, {closed_count} closed)")

    with open(args.output, "w") as f:
        json.dump({"milestone": milestone["title"], "due_date": milestone.get("due_date", ""), "issues": issues}, f, indent=2)
    print(f"💾  Saved to {args.output}")


if __name__ == "__main__":
    main()
