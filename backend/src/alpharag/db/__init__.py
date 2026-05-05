"""Database infrastructure: ORM models, session factory, repositories.

Only this package and `llm/` may talk to the outside world (Postgres, OpenAI).
Higher layers go through repositories.
"""
