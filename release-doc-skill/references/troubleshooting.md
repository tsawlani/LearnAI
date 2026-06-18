# Troubleshooting

## HTTP 401 — Unauthorized
- Token is missing, expired, or lacks required scopes
- Fix: Generate a new Personal Access Token with `api` scope
- GitLab → User Settings → Access Tokens → Add new token

## HTTP 403 — Forbidden
- Token is valid but user lacks permission on this project
- Fix: Ensure the token owner has at least Developer role on the project

## HTTP 404 — Project Not Found
- `PROJECT_ID` is wrong or the token owner cannot see the project
- Try using the numeric project ID (visible in Project Settings → General)
- For groups: ensure the group path is correct (`group/subgroup/repo`)

## HTTP 404 — Wiki Page Not Found (on PUT)
- This is handled automatically — the script falls back to POST (create)

## Wiki Disabled
- Error: `Wiki is disabled for this project`
- Fix: Project Settings → General → Visibility, project features, permissions → Wiki → enable it

## No Issues Returned
- Milestone exists but no issues are assigned to it
- Check: GitLab → Issues → filter by Milestone → confirm issues exist
- The Release Scope page will be created with an empty table

## Milestone Not Found
- The script will print available milestone names
- Milestone name is case-sensitive and must match exactly
- Alternatively pass the numeric milestone ID

## Jinja2 Not Installed
- The generator has a built-in fallback renderer for basic templates
- For full template support: `pip install jinja2`

## Rate Limiting
- GitLab enforces rate limits (600 req/min for authenticated API)
- For projects with 500+ issues, the script uses pagination automatically
- If you hit limits, wait 60 seconds and retry
