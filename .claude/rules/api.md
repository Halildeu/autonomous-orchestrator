# API Domain Rules

- REST conventions: GET (read), POST (create), PUT (full update), PATCH (partial), DELETE
- URL naming: plural nouns, kebab-case (e.g., /api/v1/account-plans)
- API versioning: URL prefix (/api/v1/, /api/v2/) — not header-based
- Request/response: JSON content type, consistent error envelope
- Error envelope: { "error": { "code": "...", "message": "...", "details": [] } }
- Pagination: cursor-based preferred, offset-based acceptable; always include total_count
- Authentication: Keycloak JWT token in Authorization Bearer header
- Authorization: permission-service/OpenFGA checks — not inline role checks
- Rate limiting: respect service-level rate limit headers
- CORS: configured at reverse proxy level, not in application code
- Input validation: validate at API boundary, trust internal calls
- OpenAPI spec: maintain spec file for all public endpoints
