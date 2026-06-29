"""Open-domain heuristic classifier for LLM chat sessions."""

from __future__ import annotations

import re
from typing import Any

from .llm_chat_models import LlmChatClassification

DOMAINS = (
    "software_dev",
    "construction_project_management",
    "professional_work",
    "business_strategy",
    "fatherhood_parenting",
    "child_development",
    "family_life",
    "personal_health",
    "mental_wellness",
    "relationship_communication",
    "household_operations",
    "home_life",
    "life_planning",
    "personal_finance_admin",
    "legal_admin",
    "shopping_products",
    "travel",
    "writing_content",
    "career_resume",
    "creative_ideation",
    "random_research",
    "personal_learning",
    "general_curiosity",
    "miscellaneous",
)

KNOWLEDGE_TYPES = (
    "research_note",
    "decision_note",
    "how_to_runbook",
    "troubleshooting_session",
    "implementation_plan",
    "meeting_prep",
    "project_status",
    "brainstorm",
    "comparison_evaluation",
    "recommendation",
    "personal_reflection",
    "learning_note",
    "checklist",
    "action_plan",
    "drafting_session",
    "reference_summary",
    "purchase_decision",
    "travel_plan",
    "health_research_note",
    "wellness_tracking_note",
    "parenting_reflection",
    "child_development_research",
    "family_routine_plan",
    "personal_decision_support",
    "life_admin_note",
    "curiosity_research_note",
    "concept_explainer",
    "relationship_communication_note",
    "home_operations_plan",
    "habit_routine_plan",
    "general_session",
)

SENSITIVITIES = (
    "public",
    "normal",
    "personal",
    "confidential",
    "sensitive_health",
    "sensitive_legal",
    "sensitive_financial",
    "credential_risk",
)

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "software_dev": [
        "python", "typescript", "bug", "stack trace", "pytest", "refactor", "git", "api",
        "docker", "kubernetes", "mcp", "server", "deploy", "lint", "compiler", "debug",
    ],
    "construction_project_management": [
        "procore", "rfi", "submittal", "change order", "concrete", "schedule", "gc",
        "subcontractor", "punch list", "site", "building", "permit", "drawings",
    ],
    "professional_work": ["work", "client", "meeting", "deliverable", "stakeholder", "deadline"],
    "business_strategy": ["strategy", "market", "revenue", "growth", "competitive", "roadmap", "okr"],
    "fatherhood_parenting": [
        "parenting", "fatherhood", "dad", "toddler", "bedtime", "discipline", "potty",
        "preschool", "son", "daughter", "kids",
    ],
    "child_development": [
        "developmental", "milestone", "speech", "motor skills", "pediatric", "tantrum",
        "attachment", "play-based",
    ],
    "family_life": ["family", "weekend", "spouse", "marriage", "in-laws", "holiday", "birthday"],
    "personal_health": ["health", "symptom", "doctor", "medication", "sleep", "exercise", "diet"],
    "mental_wellness": ["anxiety", "stress", "therapy", "mindfulness", "burnout", "meditation"],
    "relationship_communication": [
        "communication", "conflict", "boundaries", "listen", "empathy", "argument", "relationship",
    ],
    "household_operations": ["chores", "cleaning", "maintenance", "hvac", "plumbing", "repair"],
    "home_life": ["home", "household", "grocery", "meal prep", "routine"],
    "life_planning": ["goals", "priorities", "life plan", "habits", "year ahead"],
    "personal_finance_admin": ["budget", "tax", "401k", "investment", "mortgage", "insurance", "bank"],
    "legal_admin": ["contract", "legal", "attorney", "lease", "will", "estate", "compliance"],
    "shopping_products": ["buy", "purchase", "product", "compare", "review", "price", "amazon"],
    "travel": ["travel", "flight", "hotel", "itinerary", "vacation", "trip", "passport"],
    "writing_content": ["write", "essay", "blog", "draft", "content", "copy", "article"],
    "career_resume": ["resume", "cv", "interview", "job", "career", "linkedin", "cover letter"],
    "creative_ideation": ["idea", "brainstorm", "creative", "concept", "design", "story"],
    "random_research": ["research", "learn", "explain", "what is", "how does", "curious"],
    "personal_learning": ["course", "study", "tutorial", "learn", "skill"],
    "general_curiosity": ["interesting", "wonder", "why", "explore", "random"],
}

_KNOWLEDGE_KEYWORDS: dict[str, list[str]] = {
    "troubleshooting_session": ["error", "fix", "debug", "broken", "failed", "issue", "traceback"],
    "implementation_plan": ["implement", "plan", "phase", "roadmap", "architecture"],
    "decision_note": ["decide", "decision", "choose", "option", "tradeoff"],
    "action_plan": ["action item", "todo", "next step", "follow up"],
    "purchase_decision": ["buy", "purchase", "compare", "worth it", "recommend"],
    "travel_plan": ["itinerary", "flight", "hotel", "packing"],
    "parenting_reflection": ["parenting", "reflect", "patience", "bedtime"],
    "health_research_note": ["symptom", "study", "research", "health"],
    "curiosity_research_note": ["what is", "how does", "explain", "research"],
    "brainstorm": ["brainstorm", "ideas", "what if"],
    "how_to_runbook": ["how to", "steps", "runbook", "procedure"],
}

_SENSITIVE_HEALTH = ("diagnosis", "medication", "symptom", "doctor", "therapy", "mental health")
_SENSITIVE_LEGAL = ("attorney", "lawsuit", "contract", "legal", "court", "will")
_SENSITIVE_FINANCIAL = ("ssn", "account number", "tax id", "bank", "401k", "salary", "debt")


def _score_keywords(text: str, keywords: list[str]) -> float:
    lower = text.lower()
    hits = sum(1 for kw in keywords if kw in lower)
    if not keywords:
        return 0.0
    return min(1.0, hits / max(3, len(keywords) * 0.15))


def _infer_knowledge_type(text: str, domain: str) -> str:
    scores = {kt: _score_keywords(text, kws) for kt, kws in _KNOWLEDGE_KEYWORDS.items()}
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best] >= 0.2:
        return best
    if domain == "software_dev":
        return "troubleshooting_session"
    if domain in ("fatherhood_parenting", "child_development"):
        return "parenting_reflection"
    if domain in ("personal_health", "mental_wellness"):
        return "health_research_note"
    if domain in ("random_research", "general_curiosity", "personal_learning"):
        return "curiosity_research_note"
    if domain == "shopping_products":
        return "purchase_decision"
    if domain == "travel":
        return "travel_plan"
    return "general_session"


def _infer_sensitivity(text: str, domain: str, *, credential_redacted: bool) -> str:
    lower = text.lower()
    if credential_redacted:
        return "credential_risk"
    if domain in ("personal_health", "mental_wellness") or any(k in lower for k in _SENSITIVE_HEALTH):
        return "sensitive_health"
    if domain == "legal_admin" or any(k in lower for k in _SENSITIVE_LEGAL):
        return "sensitive_legal"
    if domain == "personal_finance_admin" or any(k in lower for k in _SENSITIVE_FINANCIAL):
        return "sensitive_financial"
    if domain in ("fatherhood_parenting", "child_development", "family_life", "relationship_communication"):
        return "personal"
    if domain in ("software_dev", "construction_project_management", "professional_work"):
        return "normal"
    return "normal"


def _secondary_domains(primary: str, scores: dict[str, float]) -> list[str]:
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    out: list[str] = []
    for domain, score in ordered:
        if domain == primary or score < 0.15:
            continue
        out.append(domain)
        if len(out) >= 3:
            break
    return out


def classify_session(text: str, *, credential_redacted: bool = False) -> LlmChatClassification:
    scores = {domain: _score_keywords(text, kws) for domain, kws in _DOMAIN_KEYWORDS.items()}
    primary = max(scores, key=scores.get)  # type: ignore[arg-type]
    confidence = scores[primary]
    if confidence < 0.1:
        primary = "miscellaneous"
        confidence = 0.1
    knowledge_type = _infer_knowledge_type(text, primary)
    sensitivity = _infer_sensitivity(text, primary, credential_redacted=credential_redacted)
    rationale = f"domain={primary} score={confidence:.2f} knowledge={knowledge_type}"
    return LlmChatClassification(
        primary_domain=primary,
        secondary_domains=_secondary_domains(primary, scores),
        knowledge_type=knowledge_type,
        sensitivity=sensitivity,
        confidence=round(confidence, 3),
        rationale=rationale,
    )


def classification_summary(classification: LlmChatClassification) -> str:
    return (
        f"{classification.primary_domain} / {classification.knowledge_type} "
        f"({classification.sensitivity}, conf={classification.confidence})"
    )
