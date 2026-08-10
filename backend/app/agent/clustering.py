"""
================================================================================
DETERMINISTIC GUARDRAIL — NOT THE RECOMMENDATION ENGINE
================================================================================

This module is a DETERMINISTIC GUARDRAIL, not the recommendation engine.

It only maps known paid-course categories to broad topic families
(e.g. React → frontend) to prevent semantic drift in retrieval
(e.g. stop a loose "backend" query from ranking FastAPI when the user is
actually frontend-focused).

It does NOT:
  - select final free resources
  - rank the final recommendation set for the user
  - generate narrative copy

That reasoning happens in ``app/agent/nodes.py`` via LLM calls:
  - summarize_activity
  - grade_retrieval
  - generate_recommendation

Chroma semantic search returns candidate catalog IDs; the LLM's
generate_recommendation node picks among those IDs. This file never
chooses a YouTube/resource ID as the product itself.
================================================================================
"""

from __future__ import annotations

from collections import Counter
from typing import Any

# Paid mock category → interest family (retrieval scoping only)
CATEGORY_TO_FAMILY: dict[str, str] = {
    "React": "frontend",
    "JavaScript": "frontend",
    "TypeScript": "frontend",
    "Next.js": "frontend",
    "Design": "design",  # own family — not folded into frontend
    "Backend": "backend",
    "FastAPI": "backend",
    "Go": "backend",
    "Python": "python",
    "SQL": "data",
    "Data Science": "data",
    "Machine Learning": "ml",
    "AI": "ml",
    "Docker": "devops",
    "DevOps": "devops",
    "Cloud": "devops",
    "Git": "devops",
    "DSA": "cs",
    "Computer Science": "cs",
    "System Design": "cs",
    "Mobile": "mobile",
    "Security": "security",
}

# Free-catalog category (existing column) → family — sanity / filter only.
# Uses catalog categories already on FreeResource rows — not new course tags.
FREE_CATEGORY_TO_FAMILY: dict[str, str] = {
    "web-development": "frontend",
    "design": "design",
    "backend": "backend",
    "programming": "python",
    "computer-science": "cs",
    "data": "data",
    "machine-learning": "ml",
    "ai": "ml",
    "devops": "devops",
    "cloud": "devops",
    "tools": "devops",
    "mobile": "mobile",
    "security": "security",
}

# For re-trigger confidence only: related fine families can share a bucket so a
# clear Python/ML/data streak is not diluted into five 1-count ties.
CONFIDENCE_AFFINITY: dict[str, str] = {
    "frontend": "frontend",
    "design": "design",
    "backend": "backend_stack",
    "devops": "backend_stack",
    "python": "python_data",
    "ml": "python_data",
    "data": "python_data",
    "cs": "python_data",
    "mobile": "mobile",
    "security": "security",
}

# Guardrail metadata: how to *scope* Chroma queries — never a final pick list
FAMILY_GUARDRAIL_META: dict[str, dict[str, Any]] = {
    "frontend": {
        "label": "React and modern JavaScript",
        "themes": ["react", "typescript", "javascript"],
        "search_query": (
            "React TypeScript JavaScript frontend web development "
            "Next.js UI components hooks"
        ),
        "free_categories": {"web-development"},
        # No figma/ui boost here — Design is a separate family
        "prefer_tokens": [
            "react", "javascript", "typescript", "next", "frontend", "hooks",
        ],
        "reject_tokens": [
            "fastapi", "pytorch", "terraform", "docker", "kubernetes",
            "figma", "ui design",
        ],
    },
    "design": {
        "label": "UI/UX design",
        "themes": ["design", "figma"],
        "search_query": "Figma UI UX design interfaces components prototypes",
        "free_categories": {"design"},
        "prefer_tokens": ["figma", "ui", "ux", "design", "prototype"],
        "reject_tokens": ["fastapi", "pytorch", "react tutorial", "kubernetes"],
    },
    "backend": {
        "label": "backend APIs and services",
        "themes": ["backend", "apis", "nodejs"],
        "search_query": (
            "Node.js Express backend REST APIs GraphQL server PostgreSQL FastAPI"
        ),
        "free_categories": {"backend"},
        "prefer_tokens": [
            "node", "express", "graphql", "api", "postgres", "redis", "fastapi",
        ],
        "reject_tokens": ["react tutorial", "flutter", "figma", "pytorch", "next.js"],
    },
    "python": {
        "label": "Python programming",
        "themes": ["python"],
        "search_query": "Python programming beginners functions data structures",
        "free_categories": {"programming", "computer-science", "backend"},
        "prefer_tokens": ["python", "fastapi", "django"],
        "reject_tokens": ["react", "flutter", "figma"],
    },
    "data": {
        "label": "SQL and data analysis",
        "themes": ["sql", "data"],
        "search_query": "SQL databases Pandas data analysis PostgreSQL",
        "free_categories": {"data", "programming"},
        "prefer_tokens": ["sql", "pandas", "database", "data"],
        "reject_tokens": ["react", "flutter", "figma"],
    },
    "ml": {
        "label": "machine learning and AI",
        "themes": ["machine-learning", "ai"],
        "search_query": (
            "machine learning Python scikit-learn neural networks LLM LangChain"
        ),
        "free_categories": {"machine-learning", "ai", "programming"},
        "prefer_tokens": [
            "machine", "learning", "pytorch", "langchain", "llm", "neural",
        ],
        "reject_tokens": ["figma", "flutter", "css", "react tutorial"],
    },
    "devops": {
        "label": "DevOps and cloud tooling",
        "themes": ["devops", "cloud"],
        "search_query": "Docker Kubernetes GitHub Actions CI CD AWS Terraform DevOps",
        "free_categories": {"devops", "cloud", "tools"},
        "prefer_tokens": [
            "docker", "kubernetes", "aws", "terraform", "github", "actions", "git",
        ],
        "reject_tokens": ["react", "flutter", "figma"],
    },
    "cs": {
        "label": "computer science fundamentals",
        "themes": ["algorithms", "computer-science"],
        "search_query": "data structures algorithms computer science CS50 Python",
        "free_categories": {"computer-science", "programming"},
        "prefer_tokens": ["algorithm", "cs50", "data structure", "interview"],
        "reject_tokens": ["figma", "flutter"],
    },
    "mobile": {
        "label": "mobile app development",
        "themes": ["flutter", "mobile"],
        "search_query": "Flutter Dart mobile app development",
        "free_categories": {"mobile"},
        "prefer_tokens": ["flutter", "dart", "mobile"],
        "reject_tokens": ["fastapi", "pytorch"],
    },
    "security": {
        "label": "cybersecurity fundamentals",
        "themes": ["security"],
        "search_query": "cybersecurity networking encryption OWASP",
        "free_categories": {"security"},
        "prefer_tokens": ["security", "cyber", "encryption"],
        "reject_tokens": ["figma", "flutter"],
    },
}

# Back-compat alias for older imports / docs
FAMILY_META = FAMILY_GUARDRAIL_META


def _family_for_event(meta: dict[str, Any]) -> str | None:
    cat = str(meta.get("category") or "").strip()
    if cat and cat in CATEGORY_TO_FAMILY:
        return CATEGORY_TO_FAMILY[cat]
    title = str(meta.get("title") or meta.get("query") or "").lower()
    if not title:
        return None
    checks = [
        ("react", "frontend"),
        ("typescript", "frontend"),
        ("javascript", "frontend"),
        ("next.js", "frontend"),
        ("figma", "design"),
        ("ui/ux", "design"),
        ("fastapi", "backend"),
        ("node", "backend"),
        ("express", "backend"),
        ("pytorch", "ml"),
        ("machine learning", "ml"),
        ("langchain", "ml"),
        ("docker", "devops"),
        ("kubernetes", "devops"),
        ("terraform", "devops"),
        ("python", "python"),
        ("sql", "data"),
        ("flutter", "mobile"),
    ]
    for needle, fam in checks:
        if needle in title:
            return fam
    return None


def family_for_free_category(category: str | None) -> str | None:
    """Map a free-catalog category string to a guardrail family."""
    if not category:
        return None
    return FREE_CATEGORY_TO_FAMILY.get(str(category).strip().lower())


def get_family_guardrail_hint(events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build a retrieval *hint* from activity (majority family).

    This does not pick free resources. Callers use the hint to scope Chroma
    queries / demote off-family noise before LLM grading & generation.
    """
    weights: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    paid_cats: Counter[str] = Counter()
    n = len(events)
    for i, ev in enumerate(events):
        meta = ev.get("raw_metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        fam = _family_for_event(meta)
        if not fam:
            continue
        family_counts[fam] += 1
        recency = 1.0 + (i / max(n, 1)) * 0.5
        weights[fam] += recency
        cat = str(meta.get("category") or "").strip()
        if cat:
            paid_cats[cat] += 1

    if not weights:
        return {
            "family": None,
            "themes": ["programming"],
            "search_query": "free programming tutorials",
            "dominant_pattern": "what you've been exploring",
            "free_categories": None,
            "prefer_tokens": [],
            "reject_tokens": [],
            "profile": "Learner browsing technical courses without a clear dominant cluster yet.",
            "family_weights": {},
            "family_counts": {},
            "top_categories": [],
            "confident": False,
            "confidence_reason": "insufficient_confidence",
        }

    ranked = weights.most_common()
    top_fam, _top_w = ranked[0]

    primary = FAMILY_GUARDRAIL_META[top_fam]
    themes = list(primary["themes"])[:2]
    label = str(primary["label"])
    query = str(primary["search_query"])
    free_cats = set(primary["free_categories"])
    prefer = list(primary["prefer_tokens"])
    reject = list(primary["reject_tokens"])

    profile = (
        f"Learner with a clear concentrated interest in {label}. "
        f"One-off views outside this cluster should be ignored for recommendations."
    )

    confident, conf_reason = dominant_family_is_confident(dict(family_counts))

    # Tags for UI: categories from the dominant family first, then affinity siblings
    aff = CONFIDENCE_AFFINITY.get(top_fam, top_fam)
    primary_cats: list[str] = []
    sibling_cats: list[str] = []
    for c, _n in paid_cats.most_common():
        cf = CATEGORY_TO_FAMILY.get(c)
        if cf == top_fam:
            primary_cats.append(c)
        elif cf and CONFIDENCE_AFFINITY.get(cf, cf) == aff:
            sibling_cats.append(c)
    top_categories = (primary_cats + sibling_cats)[:5] or [c for c, _ in paid_cats.most_common(5)]

    return {
        "family": top_fam,
        "themes": themes,
        "search_query": query,
        "dominant_pattern": label,
        "free_categories": free_cats,
        "prefer_tokens": prefer,
        "reject_tokens": reject,
        "profile": profile,
        "family_weights": dict(weights),
        "family_counts": dict(family_counts),
        "top_categories": top_categories,
        "confident": confident,
        "confidence_reason": conf_reason,
    }


def build_source_summary(
    events: list[dict[str, Any]],
    hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Snapshot of activity that produced a recommendation (for UI tags)."""
    hint = hint or get_family_guardrail_hint(events)
    return {
        "family": hint.get("family"),
        "dominant_pattern": hint.get("dominant_pattern"),
        "themes": list(hint.get("themes") or [])[:2],
        "top_categories": list(hint.get("top_categories") or [])[:5],
        "family_counts": dict(hint.get("family_counts") or {}),
        "event_count": len(events),
    }


# Older name — keep as thin alias so imports don't break mid-refactor
def cluster_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    return get_family_guardrail_hint(events)


def _affinity_counts(family_counts: dict[str, int]) -> dict[str, int]:
    buckets: Counter[str] = Counter()
    for fam, n in family_counts.items():
        buckets[CONFIDENCE_AFFINITY.get(fam, fam)] += int(n)
    return dict(buckets)


def dominant_family_is_confident(family_counts: dict[str, int]) -> tuple[bool, str]:
    """
    Minimum-confidence rule before running the full agent.

    Uses fine family counts first; if that fails, affinity buckets (e.g. python+ml+data)
    so a clear post-rec Python/ML streak is not stuck as five 1-count ties.

    Confident when:
      - dominant family/bucket has ≥ 3 signals, OR
      - dominant is the only family/bucket and has ≥ 2 signals, OR
      - dominant count is strictly greater than next by ≥ 2 (and ≥ 2), OR
      - dominant > 2× next
    """
    if not family_counts:
        return False, "insufficient_confidence"

    def _ok(counts: dict[str, int]) -> bool:
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        top_count = int(ranked[0][1])
        second_count = int(ranked[1][1]) if len(ranked) > 1 else 0
        if top_count >= 3:
            return True
        if second_count == 0 and top_count >= 2:
            return True
        if top_count >= second_count + 2 and top_count >= 2:
            return True
        if top_count > 2 * second_count:
            return True
        return False

    if _ok(family_counts):
        return True, "confident_majority"
    affinity = _affinity_counts(family_counts)
    if _ok(affinity):
        return True, "confident_majority"
    return False, "insufficient_confidence"


def filter_chroma_hits_by_family(
    hits: list[dict[str, Any]],
    *,
    free_categories: set[str] | None,
    prefer_tokens: list[str],
    reject_tokens: list[str],
    limit: int,
    required_family: str | None = None,
) -> list[dict[str, Any]]:
    """
    Guardrail post-filter on Chroma hits (demote / drop off-family noise).

    Does not invent resources — only reorders / filters embedding results
    before they reach the LLM generate node.
    """

    def score(hit: dict[str, Any]) -> float:
        meta = hit.get("metadata") or {}
        title = str(meta.get("title") or hit.get("document") or "").lower()
        cat = str(meta.get("category") or "").lower()
        dist = float(hit.get("distance") or 1.0)
        s = -dist
        if free_categories and cat in {c.lower() for c in free_categories}:
            s += 1.5
        for tok in prefer_tokens:
            if tok in title or tok in cat:
                s += 0.6
        for tok in reject_tokens:
            if tok in title:
                s -= 2.0
        if required_family:
            hit_fam = family_for_free_category(cat)
            if hit_fam == required_family:
                s += 2.0
            elif hit_fam and hit_fam != required_family:
                s -= 3.0
        return s

    scored = sorted(hits, key=score, reverse=True)
    if free_categories:
        in_fam = [
            h
            for h in scored
            if str((h.get("metadata") or {}).get("category") or "").lower()
            in {c.lower() for c in free_categories}
        ]
        if in_fam:
            scored = in_fam + [h for h in scored if h not in in_fam]

    cleaned: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for h in scored:
        title = str((h.get("metadata") or {}).get("title") or h.get("document") or "").lower()
        cat = str((h.get("metadata") or {}).get("category") or "").lower()
        if any(tok in title for tok in reject_tokens):
            rejected.append(h)
            continue
        if required_family:
            hit_fam = family_for_free_category(cat)
            if hit_fam and hit_fam != required_family:
                rejected.append(h)
                continue
        cleaned.append(h)
    final = cleaned if cleaned else rejected
    # Prefer in-family only when required_family set — never fall back to off-family
    if required_family and cleaned:
        final = cleaned
    elif required_family and not cleaned:
        return []
    return final[:limit]


# Older name
def rank_and_filter_hits(
    hits: list[dict[str, Any]],
    *,
    free_categories: set[str] | None,
    prefer_tokens: list[str],
    reject_tokens: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    return filter_chroma_hits_by_family(
        hits,
        free_categories=free_categories,
        prefer_tokens=prefer_tokens,
        reject_tokens=reject_tokens,
        limit=limit,
    )
