# Repository Guidelines

## Project Structure & Module Organization
This repository is currently documentation-first: `PRD.md` defines the product and architecture, and `LICENSE` defines usage terms. When implementation starts, keep the codebase aligned with the PRD layout:

- `backend/app/` for FastAPI code, grouped into `api/`, `services/`, `repositories/`, `models/`, `schemas/`, and `core/`.
- `frontend/` for the Next.js App Router UI.
- `tests/` for automated tests, mirroring the source layout where practical.
- `docs/` for design notes and API contracts.

## Build, Test, and Development Commands
No runnable app or scripts are committed yet. Add repo commands to the relevant manifest files and keep them consistent with `PRD.md`.

Common commands for this repository should be:

- `npm run dev` or `pnpm dev` for the Next.js frontend.
- `pytest` for backend tests.
- `alembic upgrade head` for database migrations.
- `docker compose up` for local PostgreSQL and Redis.

## Coding Style & Naming Conventions
Follow the conventions implied by the planned stack:

- Python: 4-space indentation, type hints on public functions, `snake_case` for modules and functions, `PascalCase` for classes.
- TypeScript/React: `camelCase` for variables and functions, `PascalCase` for components, file names matching route or component purpose.
- Keep API modules grouped by responsibility, for example `app/api/v1/routers/analysis.py`.
- Prefer explicit validation and small, single-purpose functions over large service methods.
- Use the formatter and linter configured by the repo once they exist; avoid a second toolchain unless needed.

## Testing Guidelines
Write tests alongside features and name them after behavior, not implementation:

- Python: `test_analysis_service.py`, `test_auth_routes.py`.
- Frontend: `analysis-form.test.tsx`, `paywall-modal.test.tsx`.

Cover success paths, validation failures, and external integration boundaries. For AI and payment flows, mock external APIs and assert request/response shape rather than live network calls.

## Commit & Pull Request Guidelines
The existing history uses short imperative commits such as `Create LICENSE`. Keep commits focused and descriptive, for example `Add analysis quota check`.

Pull requests should include:

- A brief summary of the change and the user-visible impact.
- Related issue or PRD section when applicable.
- Screenshots or request/response examples for UI and API changes.
- Notes on migrations, environment variables, or external service setup.

Keep secrets in environment variables only. Do not commit API keys, JWT secrets, or payment/webhook credentials. Validate uploads server-side, delete temporary files promptly, and avoid logging resume content or raw payment payloads.
