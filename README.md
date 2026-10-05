# WebCopy API Converter

A production-oriented full-stack application that converts unstructured web copy, HTML, or a public webpage into normalized JSON or CSV.

## Stack
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy async
- Database: PostgreSQL 16
- Frontend: Next.js 15, React 19, TypeScript, Tailwind CSS
- Security: JWT, bcrypt, Pydantic validation, HTML allow-list sanitization, SSRF protection, rate limiting
- Deployment: Docker Compose

## Start
```bash
cp .env.example .env
docker compose up --build
```

Frontend: http://localhost:3000  
API docs: http://localhost:8000/docs  
Health: http://localhost:8000/health

## Functional flow
Browser → Next.js → FastAPI router → Pydantic validation → auth dependency → domain service → parser/normalizer → PostgreSQL → JSON response → UI.

The URL importer only accepts HTTP(S), rejects localhost/private/reserved/link-local/multicast targets, limits response size, and does not follow redirects. HTML is sanitized with an allow-list before parsing. User-owned records are always queried with user_id authorization predicates.

## Output
```json
{
  "records": [
    {"name": "Keyboard", "price": "50"}
  ],
  "metadata": {
    "record_count": 1,
    "fields": ["name", "price"],
    "format": "json"
  }
}
```

CSV is generated with a union of discovered fields.

## Production deployment
Use TLS, replace development secrets, use managed PostgreSQL, configure a Redis-backed distributed rate limiter when horizontally scaling, use secure httpOnly cookie authentication, and place API/frontend behind a reverse proxy/CDN.
