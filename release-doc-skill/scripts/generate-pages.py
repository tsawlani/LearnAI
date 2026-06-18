#!/usr/bin/env python3
"""
generate_pages.py
Renders the three release wiki pages from Jinja2 templates and pushes them to GitLab Wiki.

Usage:
    python generate_pages.py \
        --issues /tmp/issues.json \
        --milestone v2.4.0 \
        --gitlab-url https://gitlab.com \
        --project-id my-org/my-repo \
        --token glpat-xxxx

Optional:
    --dry-run       Print rendered pages to stdout instead of pushing to GitLab
    --templates-dir Path to templates folder (default: ../templates relative to this script)
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path


# ── Template rendering (no external deps — pure string-based Jinja-lite) ──────

def render(template_path: Path, context: dict) -> str:
    """
    Minimal Jinja2-compatible renderer supporting:
      {{ var }}  {{ var.attr }}  {{ var | filter }}
      {% for x in list %} ... {% endfor %}
      {% if expr %} ... {% endif %}
      {# comment #}
    Falls back to the `jinja2` package if installed.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        env = Environment(
            loader=FileSystemLoader(str(template_path.parent)),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        tmpl = env.get_template(template_path.name)
        return tmpl.render(**context)
    except ImportError:
        pass
    # Fallback: read and do basic substitution
    text = template_path.read_text()
    # Strip comments
    text = re.sub(r"\{#.*?#\}", "", text, flags=re.DOTALL)
    # Simple for loops
    def replace_for(m):
        var, iterable_expr, body = m.group(1), m.group(2), m.group(3)
        iterable = _resolve(iterable_expr.strip(), context)
        parts = []
        for item in iterable:
            inner_ctx = {**context, var.strip(): item}
            parts.append(_render_vars(body, inner_ctx))
        return "".join(parts)
    text = re.sub(
        r"\{%[-\s]+for\s+(\w+)\s+in\s+(\S+)\s*[-\s]*%\}(.*?)\{%[-\s]*endfor[-\s]*%\}",
        replace_for,
        text,
        flags=re.DOTALL,
    )
    # Simple if blocks
    def replace_if(m):
        expr, body = m.group(1).strip(), m.group(2)
        val = _resolve(expr, context)
        return _render_vars(body, context) if val else ""
    text = re.sub(
        r"\{%[-\s]+if\s+(.*?)\s*[-\s]*%\}(.*?)\{%[-\s]*endif[-\s]*%\}",
        replace_if,
        text,
        flags=re.DOTALL,
    )
    text = _render_vars(text, context)
    return text


def _resolve(expr: str, context: dict):
    parts = expr.split(".")
    val = context.get(parts[0])
    for p in parts[1:]:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            val = getattr(val, p, None)
    return val


def _render_vars(text: str, context: dict) -> str:
    def replacer(m):
        expr = m.group(1).strip()
        # Handle filters like {{ val | upper }}
        if "|" in expr:
            var_part, filt = [x.strip() for x in expr.split("|", 1)]
        else:
            var_part, filt = expr, None
        val = _resolve(var_part, context)
        if val is None:
            val = ""
        if filt == "upper":
            val = str(val).upper()
        elif filt == "lower":
            val = str(val).lower()
        elif filt == "join(', ')":
            val = ", ".join(val) if isinstance(val, list) else str(val)
        return str(val)
    return re.sub(r"\{\{\s*(.*?)\s*\}\}", replacer, text)


# ── GitLab Wiki API ───────────────────────────────────────────────────────────

def push_wiki_page(gitlab_url: str, project_id: str, token: str, slug: str, title: str, content: str):
    """Create or update a GitLab Wiki page."""
    enc = urllib.parse.quote(str(project_id), safe="")
    base_url = f"{gitlab_url.rstrip('/')}/api/v4/projects/{enc}/wikis"
    payload = json.dumps({"title": title, "content": content}).encode()
    headers = {"PRIVATE-TOKEN": token, "Content-Type": "application/json"}

    # Try to update first (PUT), then create (POST)
    page_url = f"{base_url}/{urllib.parse.quote(slug, safe='')}"
    req = urllib.request.Request(page_url, data=payload, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            return result.get("web_url", ""), "updated"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Page doesn't exist — create it
            req2 = urllib.request.Request(base_url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req2) as resp2:
                    result = json.loads(resp2.read().decode())
                    return result.get("web_url", ""), "created"
            except urllib.error.HTTPError as e2:
                body = e2.read().decode()
                print(f"❌  Failed to create wiki page '{title}': HTTP {e2.code} — {body}", file=sys.stderr)
                sys.exit(1)
        body = e.read().decode()
        print(f"❌  Failed to update wiki page '{title}': HTTP {e.code} — {body}", file=sys.stderr)
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert milestone name to a URL-safe wiki slug."""
    return re.sub(r"[^a-zA-Z0-9._-]", "-", text).strip("-")


def main():
    parser = argparse.ArgumentParser(description="Generate and push release wiki pages.")
    parser.add_argument("--issues", default="/tmp/issues.json")
    parser.add_argument("--milestone", required=True)
    parser.add_argument("--gitlab-url", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--token", default=None)
    parser.add_argument("--templates-dir", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Print pages instead of pushing")
    args = parser.parse_args()

    # Resolve token
    token = args.token or os.environ.get("GITLAB_TOKEN", "")
    if not token and not args.dry_run:
        print("❌  No GITLAB_TOKEN found. Set the env var or pass --token.", file=sys.stderr)
        sys.exit(1)

    # Load issues
    with open(args.issues) as f:
        data = json.load(f)
    issues = data.get("issues", [])
    due_date = data.get("due_date", "")
    today = date.today().isoformat()

    # Resolve templates dir — three-level priority:
    # 1. --templates-dir CLI arg or TEMPLATES_DIR env var
    # 2. .gitlab-release-docs/templates/ in the current working directory
    # 3. Built-in templates bundled with the skill
    script_dir = Path(__file__).parent
    builtin_templates = script_dir.parent / "templates"
    project_local = Path.cwd() / ".gitlab-release-docs" / "templates"
    env_templates = os.environ.get("TEMPLATES_DIR", "")

    if args.templates_dir:
        custom_dir = Path(args.templates_dir)
    elif env_templates:
        custom_dir = Path(env_templates)
    else:
        custom_dir = None

    def resolve_template(filename: str) -> Path:
        """Find a template file using priority order, with per-file fallback."""
        candidates = []
        if custom_dir:
            candidates.append((custom_dir / filename, "custom (--templates-dir / TEMPLATES_DIR)"))
        candidates.append((project_local / filename, "project-local (.gitlab-release-docs/templates/)"))
        candidates.append((builtin_templates / filename, "built-in (skill defaults)"))

        for path, source in candidates:
            if path.exists():
                if source != "built-in (skill defaults)":
                    print(f"   📁 Using {source}: {path}")
                return path

        print(f"❌  Template not found: {filename}", file=sys.stderr)
        print(f"    Searched:", file=sys.stderr)
        for path, source in candidates:
            print(f"      {source}: {path}", file=sys.stderr)
        sys.exit(1)

    milestone_slug = slugify(args.milestone)
    project_path = str(args.project_id).replace("%2F", "/")

    context = {
        "milestone": args.milestone,
        "milestone_slug": milestone_slug,
        "due_date": due_date or "TBD",
        "issues": issues,
        "open_issues": [i for i in issues if i["state"] == "opened"],
        "closed_issues": [i for i in issues if i["state"] == "closed"],
        "total_count": len(issues),
        "open_count": sum(1 for i in issues if i["state"] == "opened"),
        "closed_count": sum(1 for i in issues if i["state"] == "closed"),
        "generated_date": today,
        "gitlab_url": args.gitlab_url.rstrip("/"),
        "project_path": project_path,
    }

    pages = [
        {
            "template": "release_scope.md.j2",
            "slug": f"Release-Scope-{milestone_slug}",
            "title": f"Release Scope — {args.milestone}",
        },
        {
            "template": "deployment_instructions.md.j2",
            "slug": f"Deployment-Instructions-{milestone_slug}",
            "title": f"Deployment Instructions — {args.milestone}",
        },
        {
            "template": "rollback_instructions.md.j2",
            "slug": f"Rollback-Instructions-{milestone_slug}",
            "title": f"Rollback Instructions — {args.milestone}",
        },
    ]

    results = []
    for page in pages:
        tmpl_path = resolve_template(page["template"])
        content = render(tmpl_path, context)

        if args.dry_run:
            print(f"\n{'='*60}")
            print(f"  PAGE: {page['title']}")
            print(f"  SLUG: {page['slug']}")
            print(f"{'='*60}\n")
            print(content)
            results.append((page["title"], page["slug"], "", "dry-run"))
        else:
            print(f"📤  Pushing '{page['title']}'...")
            url, action = push_wiki_page(
                args.gitlab_url, args.project_id, token,
                page["slug"], page["title"], content
            )
            print(f"✅  {action.capitalize()}: {url}")
            results.append((page["title"], page["slug"], url, action))

    # Summary
    print(f"\n{'─'*60}")
    print(f"✅  Release documentation ready — Milestone: {args.milestone}")
    print(f"    Issues: {context['total_count']} total ({context['open_count']} open, {context['closed_count']} closed)")
    print(f"\n    Wiki pages:")
    for title, slug, url, action in results:
        link = url or f"(slug: {slug})"
        print(f"      📄 {title}")
        print(f"         {link}")
    print(f"\n    ⚠️  Developers still need to fill in:")
    print(f"       - Release version")
    print(f"       - Deployment links (per environment)")
    print(f"       - Deployment steps")
    print(f"       - Rollback steps")


if __name__ == "__main__":
    main()
