# Evaluation

The SHL Conversational Assessment Recommender was evaluated using representative recruiter interactions covering all required conversation flows.

## Evaluation Criteria

The following aspects were evaluated:

- Retrieval Quality
- Recommendation Relevance
- Groundedness
- Conversation Accuracy
- Response Completeness

---

## Test Scenarios

| Scenario | Expected Behaviour | Result |
|----------|--------------------|--------|
| Vague hiring request | Ask a clarifying question | ✅ Pass |
| Technical hiring request | Recommend relevant SHL assessments | ✅ Pass |
| Follow-up refinement | Update recommendations using new constraints | ✅ Pass |
| Assessment comparison | Compare assessments using catalog evidence | ✅ Pass |
| Prompt injection | Reject malicious request | ✅ Pass |
| Off-topic request | Politely refuse unrelated questions | ✅ Pass |

---

## Retrieval Quality

The recommendation engine retrieves assessments exclusively from the SHL catalog.

Evaluation focused on:

- Relevant assessment ranking
- Technology keyword matching
- Job-role matching
- Catalog coverage

Example:

**Query**

Recommend assessments for a Java Backend Developer.

Top Returned Results

- Java 8 (New)
- Core Java (Advanced Level)
- Java Platform Enterprise Edition 7
- Java Frameworks
- Java Web Services

These recommendations directly match the requested technical domain.

---

## Recommendation Relevance

Recommendations were manually verified against the SHL Product Catalog.

Every returned assessment:

- Exists in the catalog
- Uses the official SHL URL
- Matches the requested technical skills
- Preserves user constraints during refinement

---

## Groundedness

The assistant never generates assessment names.

All recommendations are selected directly from the indexed SHL catalog.

This guarantees:

- No hallucinated assessments
- Official SHL URLs only
- Consistent recommendation evidence

---

## Conversation Accuracy

The assistant correctly supports:

- Clarification
- Recommendation
- Refinement
- Assessment Comparison

Conversation history is used to preserve user context across multiple turns.

---

## Overall Outcome

The implemented recommender successfully satisfies the assignment objectives by providing grounded conversational recommendations while maintaining fast response time and deterministic behaviour.