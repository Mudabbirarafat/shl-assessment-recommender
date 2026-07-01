# Approach Document — SHL Conversational Assessment Recommender

## 1. Architecture

The solution is implemented as a stateless **FastAPI** application exposing two REST endpoints:

- `GET /health` – Health check endpoint.
- `POST /chat` – Conversational assessment recommendation endpoint.

The application is stateless. Every request contains the complete conversation history, allowing the system to reconstruct context without maintaining server-side sessions or a database. The assessment catalog and retrieval index are initialized once during application startup to keep response latency low.

```
messages[]
      │
      ▼
Intent Detection & Dialogue Manager
      │
 ┌────┼───────────────┬─────────────┐
 │    │               │             │
Clarify Recommend  Compare     Refuse
      │
      ▼
TF-IDF Retrieval Engine
      │
      ▼
Ranked SHL Assessments
      │
      ▼
JSON Response
```

The system uses a local catalog (`data/catalog_full.json`) containing **377 SHL Individual Assessments**. Each record includes assessment name, official SHL URL, assessment type, description, job levels, supported languages, approximate duration, remote testing availability and adaptive testing information.

The catalog is loaded once during startup and indexed for efficient retrieval.

---

# 2. Retrieval Design

The recommendation engine uses a lightweight **TF-IDF + Cosine Similarity** retrieval pipeline implemented from scratch using **NumPy**.

Each assessment is indexed using:

- Assessment Name
- Description
- Assessment Type
- Job Levels
- Languages
- Duration
- Remote Availability
- Adaptive Testing Support

User queries undergo:

- Lowercasing
- Tokenization
- Stop-word removal
- TF-IDF vectorization
- Cosine similarity ranking

Additional domain-specific score boosts are applied for technology-focused hiring queries such as Java, Python, React and SQL to improve recommendation relevance.

The retrieval engine always returns recommendations exclusively from the SHL assessment catalog, ensuring that no assessment names or URLs are generated outside the available catalog.

---

# 3. Conversational Behaviour

The dialogue manager supports the four required conversational behaviours.

### Clarification

When insufficient hiring information is available, the assistant asks targeted follow-up questions instead of making assumptions.

Example:

> "I'm hiring."

↓

"What role are you hiring for? Are you looking for technical, cognitive, personality or a combination of assessments?"

---

### Recommendation

After enough context is available, the assistant retrieves and ranks relevant SHL assessments.

Each recommendation includes:

- Assessment Name
- Official SHL URL
- Assessment Type

---

### Refinement

The API is stateless and receives the complete conversation history with every request.

When users modify requirements such as:

- adding personality assessments
- changing seniority
- introducing duration constraints

the recommendation list is regenerated using the updated conversation context.

---

### Comparison

Users can compare two SHL assessments.

Comparison responses are generated solely from catalog information including:

- Assessment Type
- Description
- Duration
- Job Levels
- Languages
- Remote Testing
- Adaptive Testing

No external knowledge is used during comparison.

---

# 4. Safety and Grounding

The system includes lightweight safety checks before generating recommendations.

It rejects:

- Prompt injection attempts
- Requests unrelated to SHL assessments
- Questions outside the supported scope

All recommendations remain grounded in the official SHL catalog and only official SHL product URLs are returned.

---

# 5. Design Choices

A deterministic retrieval-based dialogue manager was selected instead of relying entirely on an LLM.

This design offers several advantages:

- Predictable responses
- Faster execution
- Lower deployment cost
- Reduced hallucination risk
- Fully grounded recommendations

The architecture also keeps latency low by avoiding external API calls during recommendation generation.

---

# 6. Challenges and Iterations

Several improvements were introduced during development.

### Expanded Catalog

The initial prototype used a limited catalog.

The final implementation indexes **377 SHL assessments**, significantly improving recommendation coverage.

### Improved Retrieval

Additional domain-specific token boosting was introduced to better rank technical assessments for roles such as Java Developer, Python Developer and React Developer.

### Better Dialogue Handling

Clarification logic was refined to avoid repeatedly asking follow-up questions while still gathering sufficient information before making recommendations.

### Grounded Responses

Recommendation generation was restricted entirely to catalog evidence, ensuring that every returned assessment corresponds to an official SHL product.

---

# 7. Evaluation

The recommender was evaluated using representative conversational scenarios.

| Scenario | Expected Behaviour |
|----------|--------------------|
| Vague hiring request | Ask clarifying question |
| Technical hiring request | Return relevant assessments |
| Recommendation refinement | Update recommendation list |
| Assessment comparison | Compare using catalog evidence |
| Prompt injection | Reject request |
| Off-topic conversation | Safe refusal |

Evaluation focused on:

- Retrieval Quality
- Recommendation Relevance
- Groundedness
- Response Accuracy
- Conversation Quality

Responses were manually verified against the SHL catalog to ensure recommendations remained accurate and grounded.

---

# 8. Technology Stack

- Python 3.12
- FastAPI
- Pydantic
- NumPy
- Uvicorn

The project also includes an experimental semantic retrieval module using Sentence Transformers and FAISS. While this module was explored during development, the submitted recommendation pipeline uses the TF-IDF retrieval engine to provide stable and deterministic recommendations.

---

# 9. AI Assistance

AI tools were used to accelerate development, debugging and documentation.

The implementation was developed with assistance from ChatGPT and Claude for architectural discussions, retrieval design, debugging support and documentation drafting. All recommendation logic, API behaviour and retrieval pipeline were verified against the SHL catalog before submission.