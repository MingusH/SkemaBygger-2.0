@echo off
cd /d "e:\Programmering\SkemaByggerImproved"
docker compose exec -i backend python -m app.mcp_server
