---
name: gitlab-release-docs
description: >
  Generates release documentation pages in GitLab Wiki from a GitLab milestone.
  Fetches all issues under a given milestone, builds a Release Scope page summarising
  every ticket (title, ID, description, assignee, due date, status), and creates
  templated Deployment Instructions and Rollback Instructions pages with placeholder
  sections for developers to fill in (release version, deployment links, deployment steps).
  Trigger this skill whenever the user mentions: "release docs", "release scope",
  "deployment page", "rollback page", "wiki pages for release", "create release wiki",
  "generate release documentation", "/release-docs", or any request to document a
  GitLab milestone for a release. Also triggers when the user asks to create, generate,
  or update any combination of release scope / deployment / rollback pages from GitLab.
---

# GitLab Release Docs Skill

Generates three GitLab Wiki pages for a release milestone:
1. **Release Scope** — auto-populated from GitLab milestone issues
2. **Deployment Instructions** — structured template with dev-fill placeholders
3. **Rollback Instructions** — structured template with rollback steps and criteria

---

## Trigger Phrases

| Trigger | Example |
|---|---|
| Slash command | `/release-docs` |
| Natural language | "create release docs for milestone v2.4" |
| Natural language | "generate wiki pages for our release" |
| Natural language | "build deployment and rollback pages for milestone X" |

---

## Step 0 — Collect Inputs

Before doing anything, ensure you have these values. Ask the user for any that are missing:

| Variable | Description | Example |
|---|---|---|
| `GITLAB_URL` | Base URL of GitLab instance | `https://gitlab.com` or self-hosted |
| `PROJECT_ID` | GitLab project ID or `namespace/project` slug | `42` or `my-org/my-repo` |
| `MILESTONE_NAME` | Exact milestone name or ID | `v2.4.0` or `34` |
| `GITLAB_TOKEN` | Personal Access Token with `api` + `wiki` scope | — |
| `TEMPLATES_DIR` | *(Optional)* Path to custom templates folder | `.gitlab-release-docs/templates` |

**Auth resolution order:**
1. Check if `GITLAB_TOKEN` is set as an environment variable → use it silently.
2. If not found, check for a `.env` file in the workspace root.
3. If still not found, ask the user to paste their token (remind them it needs `api` and `wiki` scopes).

**Template resolution order** (first match wins per page):
1. `TEMPLATES_DIR` env var or `--templates-dir` CLI arg
2. `.gitlab-release-docs/templates/` in the current working directory (project-local)
3. Built-in templates bundled with the skill (`templates/` next to `SKILL.md`)

See the **Custom Templates** section below for how to author your own templates.

---

## Step 1 — Fetch Milestone Issues

Run the script to pull all issues. Read the script before running:
→ `scripts/fetch_issues.py`

```bash
python scripts/fetch_issues.py \
  --gitlab-url "$GITLAB_URL" \
  --project-id "$PROJECT_ID" \
  --milestone "$MILESTONE_NAME" \
  --token "$GITLAB_TOKEN" \
  --output /tmp/issues.json
```

The script outputs a JSON array of issues. Each issue contains:
- `id`, `iid` (internal project issue number), `title`, `description`
- `assignees` (list of usernames), `milestone` (name + due_date), `state` (opened/closed)
- `web_url`

If the API returns an error, see `references/troubleshooting.md`.

---

## Step 2 — Generate the Three Wiki Pages

Run the page generator. Read the script before running:
→ `scripts/generate_pages.py`

```bash
python scripts/generate_pages.py \
  --issues /tmp/issues.json \
  --milestone "$MILESTONE_NAME" \
  --gitlab-url "$GITLAB_URL" \
  --project-id "$PROJECT_ID" \
  --token "$GITLAB_TOKEN" \
  --templates-dir "${TEMPLATES_DIR:-}"   # optional — omit if not set
```

This script:
1. Resolves templates (custom path → project-local → built-in fallback)
2. Renders `release_scope.md.j2` → pushes to Wiki as `Release-Scope-{MILESTONE}`
3. Renders `deployment_instructions.md.j2` → pushes to Wiki as `Deployment-Instructions-{MILESTONE}`
4. Renders `rollback_instructions.md.j2` → pushes to Wiki as `Rollback-Instructions-{MILESTONE}`

---

## Step 3 — Confirm and Report

After the script runs, report back to the user:

```
✅ Release documentation created for milestone: {MILESTONE_NAME}

Wiki pages created:
  📄 Release Scope       → {GITLAB_URL}/{PROJECT_PATH}/-/wikis/Release-Scope-{MILESTONE}
  📄 Deployment Instrs   → {GITLAB_URL}/{PROJECT_PATH}/-/wikis/Deployment-Instructions-{MILESTONE}
  📄 Rollback Instrs     → {GITLAB_URL}/{PROJECT_PATH}/-/wikis/Rollback-Instructions-{MILESTONE}

Issues included: {N} tickets from milestone "{MILESTONE_NAME}"

⚠️  Developers still need to fill in:
  - Release version
  - Deployment links (per environment)
  - Deployment steps
  - Rollback steps
```

---

## Error Handling

| Error | Action |
|---|---|
| 401 Unauthorized | Ask user to verify token has `api` and `wiki` scopes |
| 404 Project not found | Ask user to confirm `PROJECT_ID` (try numeric ID if slug fails) |
| 404 Milestone not found | List available milestones via `GET /projects/:id/milestones` and ask user to pick |
| Wiki disabled | Instruct user to enable Wiki under Project Settings → General → Visibility |
| No issues found | Warn user — still create empty-table Release Scope page |

---

## Custom Templates

You can provide your own templates to match your team's documentation standards.

### Setup (project-local, recommended)

Create a folder in your repo and add your template files:

```
your-repo/
└── .gitlab-release-docs/
    └── templates/
        ├── release_scope.md.j2            ← optional
        ├── deployment_instructions.md.j2  ← optional
        └── rollback_instructions.md.j2    ← optional
```

The skill picks these up automatically — no flags needed. You only need to provide the templates you want to override; missing files fall back to the built-in ones.

### Setup (global / shared path)

Set `TEMPLATES_DIR` in your environment or `.env` file:

```bash
TEMPLATES_DIR=/path/to/your/shared/templates
```

Or pass it explicitly:

```bash
python scripts/generate_pages.py ... --templates-dir /path/to/templates
```

### Available template variables

All three templates receive this context:

| Variable | Type | Description |
|---|---|---|
| `milestone` | string | Milestone name e.g. `v2.4.0` |
| `milestone_slug` | string | URL-safe slug e.g. `v2-4-0` |
| `due_date` | string | Milestone due date or `TBD` |
| `generated_date` | string | Today's date `YYYY-MM-DD` |
| `issues` | list | All issues (see fields below) |
| `open_issues` | list | Filtered to state `opened` |
| `closed_issues` | list | Filtered to state `closed` |
| `total_count` | int | Total issue count |
| `open_count` | int | Open issue count |
| `closed_count` | int | Closed issue count |
| `gitlab_url` | string | Base GitLab URL |
| `project_path` | string | `namespace/project` slug |

**Per-issue fields** (available inside `{% for issue in issues %}`):

| Field | Description |
|---|---|
| `issue.iid` | Project-scoped issue number |
| `issue.title` | Issue title |
| `issue.description` | Issue body text |
| `issue.state` | `opened` or `closed` |
| `issue.assignees` | List of usernames |
| `issue.milestone_name` | Milestone title |
| `issue.due_date` | Milestone due date |
| `issue.web_url` | Full GitLab issue URL |
| `issue.labels` | List of label strings |

### Template syntax

Templates use [Jinja2](https://jinja.palletsprojects.com/) syntax. The skill ships with a built-in fallback renderer for environments without Jinja2 installed, but `pip install jinja2` is recommended for full filter support.

```jinja
{# Loop over issues #}
{% for issue in issues %}
- [#{{ issue.iid }}]({{ issue.web_url }}) — {{ issue.title }}
{% endfor %}

{# Conditional #}
{% if open_count > 0 %}
⚠️ {{ open_count }} issues still open!
{% endif %}

{# Filters #}
{{ milestone | upper }}
{{ issue.assignees | join(', ') }}
```

### Template file reference

See `references/template_guide.md` for annotated examples of each built-in template.

---

## Reference Files

- `references/gitlab_api.md` — GitLab REST API endpoints used
- `references/troubleshooting.md` — Common errors and fixes
- `references/template_guide.md` — Annotated template examples
- `templates/` — Built-in Jinja2 templates (used as fallback)
- `scripts/fetch_issues.py` — Fetches issues from GitLab API
- `scripts/generate_pages.py` — Renders templates and pushes to Wiki
