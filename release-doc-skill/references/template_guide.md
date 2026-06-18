# Template Guide

This guide shows how to author custom templates for the gitlab-release-docs skill.
All templates use Jinja2 syntax. Install Jinja2 for full support: `pip install jinja2`

---

## Template Files

| Filename (must match exactly) | Wiki Page Created |
|---|---|
| `release_scope.md.j2` | `Release-Scope-{milestone}` |
| `deployment_instructions.md.j2` | `Deployment-Instructions-{milestone}` |
| `rollback_instructions.md.j2` | `Rollback-Instructions-{milestone}` |

You only need to provide the files you want to customise — missing files fall back to built-in defaults.

---

## Minimal Working Example

A minimal `release_scope.md.j2`:

```jinja
# Release: {{ milestone }}

Generated: {{ generated_date }} | Due: {{ due_date }}

## Issues ({{ total_count }} total)

{% for issue in issues %}
- [#{{ issue.iid }}]({{ issue.web_url }}) **{{ issue.title }}**
  Assignee: {{ issue.assignees | join(', ') or '—' }} | Status: {{ issue.state }}
{% endfor %}
```

---

## All Available Variables

### Global (available in all three templates)

```jinja
{{ milestone }}          {# "v2.4.0" #}
{{ milestone_slug }}     {# "v2-4-0"  — URL-safe, used in wiki links #}
{{ due_date }}           {# "2024-03-15" or "TBD" #}
{{ generated_date }}     {# "2024-02-20" — today's date #}
{{ gitlab_url }}         {# "https://gitlab.com" #}
{{ project_path }}       {# "my-org/my-repo" #}

{{ total_count }}        {# 12 #}
{{ open_count }}         {# 4  #}
{{ closed_count }}       {# 8  #}

{{ issues }}             {# list of all issues #}
{{ open_issues }}        {# list filtered to state="opened" #}
{{ closed_issues }}      {# list filtered to state="closed" #}
```

### Per-Issue Fields (inside a for loop)

```jinja
{% for issue in issues %}
{{ issue.iid }}           {# 42 — project-scoped issue number #}
{{ issue.title }}         {# "Fix login timeout bug" #}
{{ issue.description }}   {# Full issue body (may be empty — check first) #}
{{ issue.state }}         {# "opened" or "closed" #}
{{ issue.assignees }}     {# ["alice", "bob"] — list of usernames #}
{{ issue.milestone_name }}{# "v2.4.0" #}
{{ issue.due_date }}      {# "2024-03-15" or "" #}
{{ issue.web_url }}       {# "https://gitlab.com/org/repo/-/issues/42" #}
{{ issue.labels }}        {# ["backend", "bug"] — list #}
{% endfor %}
```

---

## Common Patterns

### Issue table

```jinja
| ID | Title | Assignee | Status |
|---|---|---|---|
{% for issue in issues %}
| [#{{ issue.iid }}]({{ issue.web_url }}) | {{ issue.title }} | {{ issue.assignees | join(', ') or '—' }} | {{ '✅' if issue.state == 'closed' else '🔵' }} |
{% endfor %}
```

### Conditional description block

```jinja
{% for issue in issues %}
### #{{ issue.iid }} — {{ issue.title }}
{% if issue.description %}
{{ issue.description }}
{% else %}
_No description provided._
{% endif %}
{% endfor %}
```

### Cross-page links (use milestone_slug, not milestone — it's URL-safe)

```jinja
[Deployment Instructions](Deployment-Instructions-{{ milestone_slug }})
[Rollback Instructions](Rollback-Instructions-{{ milestone_slug }})
[Release Scope](Release-Scope-{{ milestone_slug }})
```

### Open vs closed sections

```jinja
## ✅ Completed ({{ closed_count }})
{% for issue in closed_issues %}
- [#{{ issue.iid }}]({{ issue.web_url }}) {{ issue.title }}
{% endfor %}

## 🔵 Still Open ({{ open_count }})
{% for issue in open_issues %}
- [#{{ issue.iid }}]({{ issue.web_url }}) {{ issue.title }}
{% endfor %}
```

### Deployment placeholder block (copy-paste into your template)

```jinja
## Release Details

| Field | Value |
|---|---|
| **Release Version** | `[TO BE FILLED]` |
| **Milestone** | {{ milestone }} |
| **Due Date** | {{ due_date }} |
| **Release Manager** | `[TO BE FILLED]` |
```

---

## Tips

- **`[TO BE FILLED]`** is the conventional placeholder text — developers know to look for it.
- Use `{{ value or '—' }}` to show a dash when a value might be empty.
- Use `{{ list | join(', ') }}` to render a list as a comma-separated string.
- Wiki page slugs are auto-generated from the milestone name — use `{{ milestone_slug }}` in links.
- Templates are re-rendered every time the skill runs — keep static content in the template, dynamic content via variables.
