# Agents for Farm Products

A full-stack weekly ordering platform for farm-product buyers and administrators. Customers can browse products, manage draft orders and subscriptions, and ask an AI assistant for help. Administrators can review consolidated demand, manage weekly order cycles, and use a separate assistant.

## Tech stack

- FastAPI, SQLAlchemy, Alembic, and PostgreSQL
- Amazon Bedrock, Strands Agents, and AgentCore
- Next.js, React, TypeScript, and Tailwind CSS
- JWT authentication locally, with optional Amazon Cognito support

## Run locally

The application code lives in `harmony-acres`.

### Backend

```bash
cd harmony-acres
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-test.txt
```

Create `harmony-acres/.env` with at least:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/harmony_acres
JWT_SECRET=replace-me
```

Then start the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`.

### Frontend

```bash
cd harmony-acres/frontend
npm install
npm run dev
```

The web app runs at `http://localhost:3000`.

## Tests

```bash
cd harmony-acres
pytest
```

See `PLAN.md` for the implementation roadmap and `harmony-acres/DEPLOY.md` for AWS deployment notes.