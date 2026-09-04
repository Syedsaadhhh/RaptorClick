"""Vercel serverless entry point for the RaptorClick FastAPI application."""

# Requests are forwarded here by backend/vercel.json.
from app.main import app
