"""Seed admin user + curated free_resources (dual-written to Postgres + Chroma).

Usage (from backend/):
    python seed_data.py
"""

from __future__ import annotations

import logging
import sys

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import FreeResource, User
from app import vector_store
import app.models  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed")

ADMIN_EMAIL = "admin@smartreco.dev"
ADMIN_PASSWORD = "admin123"

SEED_RESOURCES: list[dict] = [
    {
        "title": "Python for Everybody — Full Course",
        "description": "Beginner-friendly Python fundamentals: variables, loops, functions, and basic data structures.",
        "topic_tags": ["python", "programming", "beginners"],
        "youtube_url": "https://www.youtube.com/watch?v=8DvywoWv6fI",
        "level": "beginner",
        "category": "programming",
    },
    {
        "title": "CS50's Introduction to Computer Science",
        "description": "Harvard CS50 lectures covering algorithms, C, Python, SQL, and web fundamentals.",
        "topic_tags": ["cs50", "computer-science", "algorithms"],
        "youtube_url": "https://www.youtube.com/playlist?list=PLhQjrBD2T381WAHyX1kWbPTyPdVXX6cYf",
        "level": "beginner",
        "category": "computer-science",
    },
    {
        "title": "JavaScript Full Course for Beginners",
        "description": "Modern JavaScript: DOM, async/await, fetch API, and ES6+ features for web development.",
        "topic_tags": ["javascript", "web", "frontend"],
        "youtube_url": "https://www.youtube.com/watch?v=PkZNo7MFNFg",
        "level": "beginner",
        "category": "web-development",
    },
    {
        "title": "React Official Tutorial — Learn React",
        "description": "Build interactive UIs with React components, hooks, state, and props.",
        "topic_tags": ["react", "frontend", "javascript"],
        "youtube_url": "https://www.youtube.com/watch?v=bMknfKXIFA8",
        "level": "intermediate",
        "category": "web-development",
    },
    {
        "title": "FastAPI — Complete Course",
        "description": "Build production APIs with FastAPI, Pydantic models, dependency injection, and OpenAPI docs.",
        "topic_tags": ["fastapi", "python", "backend", "apis"],
        "youtube_url": "https://www.youtube.com/watch?v=0RS9W8ktvwQ",
        "level": "intermediate",
        "category": "backend",
    },
    {
        "title": "SQL Tutorial — Full Database Course",
        "description": "Relational databases, joins, indexes, and practical SQL queries for analytics and apps.",
        "topic_tags": ["sql", "databases", "postgres"],
        "youtube_url": "https://www.youtube.com/watch?v=HXV3zeQKqGY",
        "level": "beginner",
        "category": "data",
    },
    {
        "title": "Machine Learning with Python — FreeCodeCamp",
        "description": "Supervised learning, scikit-learn, neural nets intro, and hands-on ML projects.",
        "topic_tags": ["machine-learning", "python", "scikit-learn"],
        "youtube_url": "https://www.youtube.com/watch?v=NWONeJKn6kc",
        "level": "intermediate",
        "category": "machine-learning",
    },
    {
        "title": "Data Structures and Algorithms in Python",
        "description": "Arrays, linked lists, trees, graphs, sorting, and interview-style problem solving.",
        "topic_tags": ["dsa", "algorithms", "python", "interview"],
        "youtube_url": "https://www.youtube.com/watch?v=pkYVOmU3MgA",
        "level": "intermediate",
        "category": "computer-science",
    },
    {
        "title": "Docker Tutorial for Beginners",
        "description": "Containers, images, Dockerfiles, volumes, and docker-compose for local development.",
        "topic_tags": ["docker", "devops", "containers"],
        "youtube_url": "https://www.youtube.com/watch?v=fqMOX6JJhGo",
        "level": "beginner",
        "category": "devops",
    },
    {
        "title": "Git and GitHub Crash Course",
        "description": "Version control basics: commits, branches, pull requests, and collaboration workflows.",
        "topic_tags": ["git", "github", "version-control"],
        "youtube_url": "https://www.youtube.com/watch?v=RGOj5yH7evk",
        "level": "beginner",
        "category": "tools",
    },
    {
        "title": "TypeScript Course for Beginners",
        "description": "Static typing, interfaces, generics, and tooling for safer JavaScript projects.",
        "topic_tags": ["typescript", "javascript", "frontend"],
        "youtube_url": "https://www.youtube.com/watch?v=BwuLxPH8IDs",
        "level": "beginner",
        "category": "web-development",
    },
    {
        "title": "Next.js 14 Tutorial for Beginners",
        "description": "App Router, server components, routing, and deploying a modern React app.",
        "topic_tags": ["nextjs", "react", "ssr"],
        "youtube_url": "https://www.youtube.com/watch?v=ZVnjOTwF8ws",
        "level": "intermediate",
        "category": "web-development",
    },
    {
        "title": "AWS Cloud Practitioner Essentials",
        "description": "Core AWS services, security, pricing, and cloud concepts for beginners.",
        "topic_tags": ["aws", "cloud", "devops"],
        "youtube_url": "https://www.youtube.com/watch?v=ulprqHHWlng",
        "level": "beginner",
        "category": "cloud",
    },
    {
        "title": "Terraform Course — Beginner to Pro",
        "description": "Infrastructure as code with Terraform providers, state, and modules.",
        "topic_tags": ["terraform", "iac", "devops"],
        "youtube_url": "https://www.youtube.com/watch?v=7xngnjfIlK4",
        "level": "intermediate",
        "category": "devops",
    },
    {
        "title": "System Design Interview — Basics",
        "description": "Scalability patterns: load balancers, caches, databases, and CAP tradeoffs.",
        "topic_tags": ["system-design", "scalability", "architecture"],
        "youtube_url": "https://www.youtube.com/watch?v=xpDnVSmXF_M",
        "level": "advanced",
        "category": "computer-science",
    },
    {
        "title": "Flutter Course for Beginners",
        "description": "Build cross-platform mobile apps with Flutter widgets and Dart.",
        "topic_tags": ["flutter", "dart", "mobile"],
        "youtube_url": "https://www.youtube.com/watch?v=VPvVD8t02U8",
        "level": "beginner",
        "category": "mobile",
    },
    {
        "title": "Cybersecurity Full Course for Beginners",
        "description": "Networking, threats, cryptography, and defensive security fundamentals.",
        "topic_tags": ["security", "cybersecurity", "networking"],
        "youtube_url": "https://www.youtube.com/watch?v=U_P23SqJaDc",
        "level": "beginner",
        "category": "security",
    },
    {
        "title": "Pandas for Data Analysis — Full Course",
        "description": "Clean and analyze tabular data with Pandas Series, DataFrames, and groupby.",
        "topic_tags": ["pandas", "data-analysis", "python"],
        "youtube_url": "https://www.youtube.com/watch?v=vmEHCJofslg",
        "level": "beginner",
        "category": "data",
    },
    {
        "title": "LangChain Crash Course",
        "description": "Build LLM apps with prompts, chains, retrieval, and simple agents.",
        "topic_tags": ["langchain", "llm", "rag", "ai"],
        "youtube_url": "https://www.youtube.com/watch?v=lG7Uxts9SXs",
        "level": "intermediate",
        "category": "ai",
    },
    {
        "title": "Go Programming — Full Course",
        "description": "Go syntax, concurrency with goroutines, and building HTTP services.",
        "topic_tags": ["golang", "go", "backend"],
        "youtube_url": "https://www.youtube.com/watch?v=YS4e4q9oBaU",
        "level": "intermediate",
        "category": "backend",
    },
    {
        "title": "Figma UI Design Tutorial",
        "description": "Design interfaces, components, and prototypes in Figma for product teams.",
        "topic_tags": ["figma", "ui", "ux", "design"],
        "youtube_url": "https://www.youtube.com/watch?v=FTFaQWZBqQ8",
        "level": "beginner",
        "category": "design",
    },
    {
        "title": "Redis Crash Course",
        "description": "In-memory data structures, caching patterns, and Redis for backends.",
        "topic_tags": ["redis", "caching", "backend"],
        "youtube_url": "https://www.youtube.com/watch?v=jgpTfVgjoZQ",
        "level": "intermediate",
        "category": "backend",
    },
    {
        "title": "Prompt Engineering Guide",
        "description": "Practical prompting patterns for developers building with LLMs.",
        "topic_tags": ["prompt-engineering", "llm", "ai"],
        "youtube_url": "https://www.youtube.com/watch?v=dOxUroR57xs",
        "level": "beginner",
        "category": "ai",
    },
    {
        "title": "GraphQL Full Course",
        "description": "Schemas, queries, mutations, and building APIs with GraphQL.",
        "topic_tags": ["graphql", "api", "backend"],
        "youtube_url": "https://www.youtube.com/watch?v=ed8SzALtpwM",
        "level": "intermediate",
        "category": "backend",
    },
    {
        "title": "GitHub Actions CI/CD Tutorial",
        "description": "Automate tests and deployments with GitHub Actions workflows.",
        "topic_tags": ["github-actions", "ci-cd", "devops"],
        "youtube_url": "https://www.youtube.com/watch?v=R8_veQiYBjI",
        "level": "beginner",
        "category": "devops",
    },
]


def ensure_admin(db) -> User:
    admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if admin:
        if admin.role != "admin":
            admin.role = "admin"
            db.commit()
            db.refresh(admin)
        logger.info("Admin already exists: %s (id=%s)", ADMIN_EMAIL, admin.id)
        return admin

    admin = User(
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        role="admin",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    logger.info("Created admin %s / %s (id=%s)", ADMIN_EMAIL, ADMIN_PASSWORD, admin.id)
    return admin


def upsert_resource(db, payload: dict) -> FreeResource:
    existing = (
        db.query(FreeResource)
        .filter(FreeResource.title == payload["title"])
        .first()
    )
    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        resource = existing
        logger.info("Updating resource: %s", resource.title)
    else:
        resource = FreeResource(**payload, sync_status="pending")
        db.add(resource)
        logger.info("Creating resource: %s", payload["title"])

    db.commit()
    db.refresh(resource)

    try:
        vector_store.upsert_resource(
            resource_id=resource.id,
            title=resource.title,
            description=resource.description,
            topic_tags=resource.topic_tags or [],
            level=resource.level,
            category=resource.category,
            youtube_url=resource.youtube_url,
        )
        resource.sync_status = "synced"
    except Exception:
        logger.exception("Chroma sync failed for %s", resource.title)
        resource.sync_status = "failed"

    db.commit()
    db.refresh(resource)
    return resource


def main() -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_admin(db)
        synced = 0
        failed = 0
        for payload in SEED_RESOURCES:
            resource = upsert_resource(db, payload)
            if resource.sync_status == "synced":
                synced += 1
            else:
                failed += 1
        logger.info("Seed complete: synced=%s failed=%s total=%s", synced, failed, len(SEED_RESOURCES))

        # Smoke: semantic search should return something for a Python query
        hits = vector_store.query_similar("learn python programming for beginners", top_k=3)
        logger.info("Sample Chroma hits: %s", [h.get("metadata", {}).get("title") for h in hits])
        return 0 if failed == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
