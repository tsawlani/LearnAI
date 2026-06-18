# GitLab API Reference

All endpoints use the GitLab REST API v4.
Base URL: `{GITLAB_URL}/api/v4`
Auth header: `PRIVATE-TOKEN: {GITLAB_TOKEN}`

## Endpoints Used

### List Project Milestones
```
GET /projects/:id/milestones
GET /projects/:id/milestones/:milestone_id
```
Params: `search=<name>`, `state=active|closed`

### List Milestone Issues
```
GET /projects/:id/issues?milestone_id=:milestone_id&scope=all&state=all&per_page=100
```
Paginated. Use `X-Next-Page` header to iterate pages.

### Create / Update Wiki Page
```
POST /projects/:id/wikis          ← create
PUT  /projects/:id/wikis/:slug    ← update
```
Body: `{ "title": "...", "content": "..." }`

## Token Scopes Required
- `api` — read issues and milestones
- `write_repository` OR `api` — push wiki pages

## URL Encoding
Project ID with slashes must be percent-encoded:
`my-org/my-repo` → `my-org%2Fmy-repo`
