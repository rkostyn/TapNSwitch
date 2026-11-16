# Deploying

    cp .env.example .env        # edit secrets
    docker compose up -d --build

The frontend is served on port 8000 and the API on 8001. Set `FRONTEND_PORT`,
`API_PORT` and `API_URL` in `.env` to change them. Data lives in the
`deploy_mongo_data` and `deploy_redis_data` volumes.

Everyday groups and tournaments run in the same deployment; a tournament is an
event type chosen when the event is created.
