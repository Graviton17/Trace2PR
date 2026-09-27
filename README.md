# Trace2PR Backend

Trace2PR: End-to-end incident response — Alert → Analysis → Fix → PR

## Tech Stack

- **Framework**: FastAPI (Python 3.12+)
- **Database**: Supabase (PostgreSQL + Auth + Realtime + Vault)
- **Execution**: E2B Code Interpreter Sandbox
- **LLM**: LiteLLM (Anthropic / OpenAI)
- **Background Tasks**: Celery + Redis
- **Integrations**: Composio (OAuth + Webhooks for 250+ tools)

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Monitoring     │     │   Trace2PR      │     │   GitHub        │
│  (Datadog,      │────▶│   Backend       │────▶│   (PR Creation) │
│   Sentry, etc)  │     │                 │     │                 │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
             ┌──────────┐ ┌──────────┐ ┌──────────┐
             │ Supabase │ │  Composio│ │   E2B    │
             │ (DB+Auth)│ │ (OAuth)  │ │ Sandbox  │
             └──────────┘ └──────────┘ └──────────┘
```

## Quick Start

### Prerequisites

- Python 3.12+
- Supabase project (local or cloud)
- Composio account (for OAuth integrations)
- Redis (for Celery)

### 1. Clone and Install

```bash
cd Trace2PR-backend
make install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required environment variables:

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (secret) |
| `E2B_API_KEY` | E2B API key for sandboxes |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | LLM provider keys |
| `COMPOSIO_API_KEY` | Composio API key for OAuth integrations |
| `REDIS_URL` | Redis connection string |
| `FRONTEND_URL` | Frontend URL for OAuth redirects |

### 3. Set Up Database

Run the migration in your Supabase SQL editor:

```bash
# Copy contents of supabase/migrations/001_initial_schema.sql
# Paste into Supabase SQL Editor and run
```

### 4. Configure Supabase Auth

In Supabase Dashboard → Authentication → Providers:
- Enable **GitHub** OAuth (add callback URL: `http://localhost:5173/auth/callback`)
- Enable **Google** OAuth (add callback URL: `http://localhost:5173/auth/callback`)
- Enable **Email** provider (for magic links)

In Authentication → URL Configuration:
- Site URL: `http://localhost:5173`
- Redirect URLs: `http://localhost:5173/auth/callback`

### 5. Configure Composio

1. Create account at [composio.dev](https://composio.dev)
2. Get API key from dashboard
3. Add to `.env` as `COMPOSIO_API_KEY`

### 6. Run Development Server

```bash
make dev
# Server runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## API Endpoints

### Authentication
- `POST /api/auth/signup` - Email/password signup
- `POST /api/auth/signin` - Email/password signin
- `POST /api/auth/magic-link` - Send magic link
- `POST /api/auth/oauth` - Initiate OAuth (GitHub/Google)
- `POST /api/auth/signout` - Sign out
- `GET /api/auth/user` - Get current user
- `POST /api/auth/refresh` - Refresh session

### Integrations (via Composio)
- `GET /api/integrations/catalog` - List available integrations
- `GET /api/integrations` - List user's connected integrations
- `POST /api/integrations/connect` - Initiate OAuth connection
- `GET /api/integrations/{service}/status` - Check connection status
- `POST /api/integrations/{service}/verify` - Re-verify connection
- `DELETE /api/integrations/{service}` - Disconnect integration

### Webhooks
- `POST /api/webhooks/composio` - Composio webhook receiver (all tools)
- `POST /api/webhooks/{datadog|sentry|pagerduty|grafana|cloudwatch}` - Direct webhooks
- `GET /api/webhooks/logs` - View webhook logs

### Incidents
- `GET /api/incidents` - List incidents
- `GET /api/incidents/{id}` - Get incident details
- `POST /api/incidents` - Create incident

### Other
- `GET /api/alerts` - List alerts
- `GET /api/prs` - List pull requests
- `GET /api/knowledge` - Knowledge base
- `GET /api/health` - Health check

## Webhook Configuration

### Using Composio (Recommended)

1. Connect integration via `/api/integrations/connect`
2. Composio automatically handles webhook registration
3. Events flow to `POST /api/webhooks/composio`

### Direct Webhooks (Alternative)

Configure in your monitoring tool:

| Tool | Webhook URL | Events |
|------|-------------|--------|
| Datadog | `https://your-api.com/api/webhooks/datadog` | Monitor alerts |
| Sentry | `https://your-api.com/api/webhooks/sentry` | Issue alerts |
| PagerDuty | `https://your-api.com/api/webhooks/pagerduty` | Incident triggers |
| Grafana | `https://your-api.com/api/webhooks/grafana` | Alert notifications |
| CloudWatch | `https://your-api.com/api/webhooks/cloudwatch` | Alarm states |

## Development Commands

```bash
make dev          # Start dev server with reload
make install      # Install dependencies
make lint         # Run ruff linter
make format       # Format code with ruff
make typecheck    # Run mypy type checking
make test         # Run pytest
make shell        # Open Python shell with env loaded
```

## Project Structure

```
trace2pr/
├── api/
│   ├── middleware/
│   │   ├── auth.py          # Supabase auth middleware
│   │   └── errors.py        # Global error handlers
│   ├── routes/
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── integrations.py  # Composio integration endpoints
│   │   ├── webhooks.py      # Webhook receivers
│   │   ├── incidents.py     # Incident management
│   │   ├── alerts.py        # Alert management
│   │   ├── prs.py           # Pull request management
│   │   ├── knowledge.py     # Knowledge base
│   │   ├── analysis.py      # Root cause analysis
│   │   ├── fixer.py         # Code fix generation
│   │   ├── sandbox.py       # E2B sandbox execution
│   │   └── settings.py      # App settings
│   └── schemas/             # Pydantic models
├── integrations/
│   ├── composio_service.py  # Composio client wrapper
│   ├── credential_store.py  # Supabase Vault integration
│   ├── verifiers/           # Credential verifiers
│   └── resolver.py          # Incident resolution logic
├── db/
│   └── supabase_client.py   # Supabase client management
├── config/
│   └── settings.py          # Configuration management
└── app.py                   # FastAPI application factory
```

## Supabase RLS Policies

All tables have Row Level Security enabled. Users can only access their own data:

```sql
-- Example policy (applied to all tables)
CREATE POLICY "Users can view own integrations" ON public.integrations
    FOR SELECT USING (auth.uid() = user_id);
```

## Composio Integration Details

### Supported Tools (via Composio)
- Datadog, Sentry, PagerDuty, Grafana, CloudWatch
- GitHub, GitLab, Bitbucket
- Slack, Linear, Jira, Asana
- AWS, GCP, Azure
- 250+ more...

### OAuth Flow
1. User clicks "Connect" on integration
2. Backend calls `composio.initiate_connection()`
3. User redirected to Composio OAuth page
4. User authorizes the tool
5. Composio redirects back to `/dashboard/integrations/callback`
6. Frontend checks status via `/api/integrations/{service}/status`

### Webhook Flow
1. Monitoring tool fires alert
2. Composio receives webhook (configured automatically)
3. Composio forwards to `POST /api/webhooks/composio`
4. Backend creates incident and triggers analysis

## Testing

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_integrations.py -v

# Run with coverage
pytest --cov=trace2pr tests/
```

## Deployment

### Docker

```bash
docker-compose up -d
```

### Environment Variables for Production

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
COMPOSIO_API_KEY=...
E2B_API_KEY=...
ANTHROPIC_API_KEY=...
REDIS_URL=redis://redis:6379
FRONTEND_URL=https://your-frontend.com

# Optional
SENTRY_DSN=...
LOG_LEVEL=info
```

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

MIT License - see LICENSE file for details.