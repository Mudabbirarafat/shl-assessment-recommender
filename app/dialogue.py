import re
from typing import List, Dict, Any, Tuple

from .catalog import get_catalog, TEST_TYPE_LABELS
from .catalog import get_catalog
from .schemas import Message, Recommendation, ChatResponse
from app import catalog

# ---------------------------------------------------------------------------
# Keyword banks
# ---------------------------------------------------------------------------

ROLE_HINTS = [
    "developer", "engineer", "programmer", "analyst", "manager", "supervisor",
    "sales", "customer service", "support agent", "representative", "rep",
    "accountant", "administrator", "admin", "tester", "qa", "designer",
    "consultant", "specialist", "coordinator", "executive", "director",
    "java", "python", "sql", "javascript", ".net", "c#", "c++", "react",
    "node", "selenium", "qa engineer", "hr", "marketing", "finance",
    "leader", "team lead", "graduate", "intern", "clerk", "receptionist",
]

TEST_TYPE_KEYWORDS = {
    "P": ["personality", "behavioral fit", "behaviour fit", "work style", "culture fit"],
    "A": ["cognitive", "reasoning", "aptitude", "numerical", "verbal reasoning",
          "inductive", "deductive", "iq", "general ability"],
    "B": ["situational judgement", "situational judgment", "sjt", "behavioral",
          "behavioural", "judgement test"],
    "K": ["coding", "technical", "programming", "knowledge test", "skills test",
          "language test"],
    "S": ["simulation", "hands-on", "hands on", "live coding"],
    "D": ["360", "leadership development", "feedback tool"],
}

REFINEMENT_TRIGGERS = [
    "actually", "instead", "also add", "add ", "remove", "drop ", "instead of",
    "change it to", "what about", "can you also", "swap", "replace",
]

COMPARE_TRIGGERS = [
    "difference between", "compare", "vs ", "versus", "which is better",
    "how does", "how is .* different",
]

OFF_TOPIC_SIGNALS = [
    "is it legal", "lawsuit", "sue", "discriminat", "fire an employee",
    "fire someone", "terminate an employee", "what salary", "salary range",
    "write a job posting", "write a job description", "interview questions for",
    "negotiate a raise", "visa sponsorship", "immigration", "tax advice",
    "stock price", "weather", "recipe", "write me a poem", "translate this",
    "what is the capital of",
]

INJECTION_SIGNALS = [
    "ignore previous instructions", "ignore the above", "system prompt",
    "you are now", "act as", "disregard your instructions", "jailbreak",
    "pretend you have no restrictions", "reveal your prompt", "developer mode",
]

CLOSING_SIGNALS = [
    "thanks", "thank you", "that's all", "that is all", "no that's it",
    "sounds good", "perfect", "great, that's it", "nothing else", "all set",
    "that works", "looks good", "no further questions",
]

DURATION_RE = re.compile(r"(?:under|less than|within|no more than|max(?:imum)?)\s+(\d{1,3})\s*(?:minutes|mins|min)")
COUNT_RE = re.compile(r"(?:give me|show me|top|need)\s+(\d{1,2})\b")


def _full_text(messages: List[Message]) -> str:
    return " \n".join(m.content for m in messages)


def _user_text(messages: List[Message]) -> str:
    return " \n".join(m.content for m in messages if m.role == "user")


def _last_user_message(messages: List[Message]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return ""


def _contains_any(text: str, terms: List[str]) -> bool:
    t = text.lower()
    return any(term in t for term in terms)


def _detect_off_topic(text: str) -> bool:
    return _contains_any(text, OFF_TOPIC_SIGNALS)


def _detect_injection(text: str) -> bool:
    return _contains_any(text, INJECTION_SIGNALS)


def _detect_compare(text: str) -> bool:
    t = text.lower()
    if _contains_any(t, ["difference between", "compare", "versus", "which is better"]):
        return True
    if re.search(r"\bvs\b", t):
        return True
    return False


def _detect_closing(text: str) -> bool:
    return _contains_any(text, CLOSING_SIGNALS)


def _has_role_or_context(text: str) -> bool:
    t = text.lower()
    if len(t.split()) >= 35:
        # Long pasted text (e.g. a job description) is treated as sufficient context.
        return True
    if _contains_any(t, ROLE_HINTS):
        return True
    catalog = get_catalog()
    for item in catalog.items:
        if item["name"].split(" (")[0].lower() in t:
            return True
        if item.get("category", "").lower() in t and len(item.get("category", "")) > 3:
            return True
    return False


def _extract_test_type_boosts(text: str) -> List[str]:
    t = text.lower()
    boosts = []
    for code, kws in TEST_TYPE_KEYWORDS.items():
        if _contains_any(t, kws):
            boosts.append(code)
    return boosts


def _extract_duration(text: str):
    m = DURATION_RE.search(text.lower())
    if m:
        return int(m.group(1))
    return None


def _extract_count(text: str):
    m = COUNT_RE.search(text.lower())
    if m:
        n = int(m.group(1))
        return max(1, min(10, n))
    return None


def _assistant_already_clarified(messages: List[Message]) -> bool:
    return any(m.role == "assistant" for m in messages)


def _assistant_already_recommended(messages: List[Message]) -> bool:
    # Heuristic: an assistant turn mentioned a catalog URL previously.
    for m in messages:
        if m.role == "assistant" and "shl.com" in m.content:
            return True
    return False


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

SCOPE_REFUSAL = (
    "I'm focused specifically on recommending SHL individual test solutions "
    "from the SHL product catalog. I can't help with legal questions, general "
    "hiring/HR advice, or topics outside SHL assessments. If you'd like, tell "
    "me about the role or skills you're hiring for and I can suggest relevant "
    "SHL assessments."
)

INJECTION_REFUSAL = (
    "I can't follow instructions that try to change how I operate. I'm here "
    "to help you find SHL individual test solutions for a role you're hiring "
    "for — what role or skills are you assessing?"
)


def _clarifying_question(text: str) -> str:
    t = text.lower()
    if not _contains_any(t, ROLE_HINTS) and len(t.split()) < 12:
        return ("Happy to help. What role are you hiring for, and what should the "
                "assessment focus on — technical skills, cognitive ability, "
                "personality/behavioral fit, or a mix? Any seniority level or time "
                "limit I should keep in mind?")
    return ("Got it — a couple of quick questions so I can narrow this down: "
            "what seniority level is this for, and should the assessment lean more "
            "on technical/skills testing, cognitive ability, or personality/behavioral fit?")


def _format_recs_reply(items: List[Dict[str, Any]], query_summary: str) -> str:
    n = len(items)
    names = ", ".join(i["name"] for i in items[:3])
    extra = f" and {n - 3} more" if n > 3 else ""
    return (f"Here are {n} SHL assessment{'s' if n != 1 else ''} that fit {query_summary}: "
            f"{names}{extra}. Let me know if you'd like to refine this (e.g. add a "
            f"personality measure, change seniority, or set a time limit) or compare "
            f"any two of them.")


def _to_recommendation(item: Dict[str, Any]) -> Recommendation:
    return Recommendation(
        name=item["name"],
        url=item["url"],
        test_type="".join(item.get("test_type", [])),
    )


def _build_compare_answer(messages: List[Message]) -> ChatResponse:
    catalog = get_catalog()
    text = _last_user_message(messages)
    # crude split on 'and' / 'vs' / 'versus' after stripping trigger phrases
    cleaned = re.sub(r"(difference between|compare|what is the difference between)", "", text, flags=re.I)
    parts = re.split(r"\bvs\b|\bversus\b|\band\b|,", cleaned, flags=re.I)
    candidates = [p.strip(" ?.!") for p in parts if p.strip(" ?.!")]
    found = []
    for c in candidates:
        item = catalog.find_by_name(c)
        if item and item not in found:
            found.append(item)
        if len(found) == 2:
            break

    if len(found) < 2:
        return ChatResponse(
            reply=("I can compare any two SHL assessments, but I need both names. "
                   "Which two assessments would you like me to compare?"),
            recommendations=[],
            end_of_conversation=False,
        )

    a, b = found[0], found[1]
    type_a = "/".join(TEST_TYPE_LABELS.get(t, t) for t in a.get("test_type", []))
    type_b = "/".join(TEST_TYPE_LABELS.get(t, t) for t in b.get("test_type", []))
    reply = (
        f"**{a['name']}** ({type_a}, ~{a.get('duration_minutes', '?')} min): {a['description']} "
        f"\n\n**{b['name']}** ({type_b}, ~{b.get('duration_minutes', '?')} min): {b['description']} "
        f"\n\nIn short: {a['name']} is a {type_a.lower()} measure, while {b['name']} is a "
        f"{type_b.lower()} measure, so they're typically used together rather than as "
        f"alternatives — {a['name']} for {'workplace style/traits' if 'P' in a.get('test_type', []) else 'ability/skill'}, "
        f"and {b['name']} for {'workplace style/traits' if 'P' in b.get('test_type', []) else 'ability/skill or broader behavioral coverage'}."
    )
    return ChatResponse(reply=reply, recommendations=[], end_of_conversation=False)


def handle_chat(messages: List[Message]) -> ChatResponse:
    if not messages:
        return ChatResponse(
            reply=("Hi! Tell me about the role you're hiring for — e.g. the title, "
                   "key skills, seniority, and whether you want technical, cognitive, "
                   "or personality/behavioral coverage — and I'll suggest SHL assessments."),
            recommendations=[],
            end_of_conversation=False,
        )

    last_user = _last_user_message(messages)
    full_user_text = _user_text(messages)

    # 1. Guardrails: prompt injection / off-topic first.
    if _detect_injection(last_user):
        return ChatResponse(reply=INJECTION_REFUSAL, recommendations=[], end_of_conversation=False)

    if _detect_off_topic(last_user) and not _detect_compare(last_user):
        return ChatResponse(reply=SCOPE_REFUSAL, recommendations=[], end_of_conversation=False)

    # 2. Comparison intent.
    if _detect_compare(last_user):
        return _build_compare_answer(messages)

    # 3. Closing.
    if _detect_closing(last_user) and _assistant_already_recommended(messages):
        return ChatResponse(
            reply="Glad that helped! Good luck with the hiring process.",
            recommendations=[],
            end_of_conversation=True,
        )

    # 4. Clarify vs recommend.
    have_context = _has_role_or_context(full_user_text)
    already_asked = _assistant_already_clarified(messages)

    if not have_context and not already_asked:
        return ChatResponse(reply=_clarifying_question(last_user), recommendations=[], end_of_conversation=False)

    if not have_context and already_asked:
        # Still vague even after a clarifying turn -- ask once more, narrowly,
        # rather than guessing and burning the recommendation slot.
        if last_user.strip() and not _contains_any(last_user.lower(), ["no preference", "not sure", "don't know", "no idea"]):
            pass  # fall through to recommend using whatever we have
        else:
            return ChatResponse(
                reply=("No problem — I'll work with general-purpose options. Are you open "
                       "to a broad starter shortlist covering core ability and personality "
                       "measures, or would you like to name at least the job title first?"),
                recommendations=[],
                end_of_conversation=False,
            )

    # 5. Build retrieval query from the whole conversation, weighting the latest
    #    turn higher so refinements ("actually, add personality tests") take effect.
    query = full_user_text + " " + (last_user + " ") * 2
    boosts = _extract_test_type_boosts(full_user_text)
    max_duration = _extract_duration(full_user_text)
    requested_count = _extract_count(full_user_text)
    top_k = requested_count or 8

    catalog = get_catalog()

    results = catalog.search(
        query=query,
        top_k=max(top_k, 8),
        boost_types=boosts,
        max_duration=max_duration,
    )

    if not results:
        return ChatResponse(
            reply=("I couldn't find a confident match in the SHL catalog for that. "
                   "Could you share a bit more detail — the role, key skills, or "
                   "whether you want cognitive, technical, or personality coverage?"),
            recommendations=[],
            end_of_conversation=False,
        )

    results = results[:max(1, min(10, top_k))]
    recs = [_to_recommendation(r) for r in results]

    summary_bits = []
    role_match = next((h for h in ROLE_HINTS if h in full_user_text.lower()), None)
    if role_match:
        summary_bits.append(f"a {role_match} hire")
    if boosts:
        summary_bits.append("with " + "/".join(TEST_TYPE_LABELS[b].lower() for b in boosts) + " coverage")
    summary = " ".join(summary_bits) if summary_bits else "your requirements"

    reply = _format_recs_reply(results, summary)
    return ChatResponse(reply=reply, recommendations=recs, end_of_conversation=False)
