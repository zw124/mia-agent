# Local Setup

## 1. Install dependencies

```bash
npm install
python -m venv .venv
. .venv/bin/activate
pip install -e "apps/agent-service[dev]"
```

## 2. Configure environment

Copy values from `.env.example` into local environment files appropriate for your setup.

## 3. Start development services

```bash
npm run desktop:dev
```

or run individual services as needed.

## 4. Validate

```bash
npm run typecheck
npm run build
npm run test
```
