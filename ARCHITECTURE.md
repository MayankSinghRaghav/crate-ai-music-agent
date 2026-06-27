# Crate — Architecture

Crate is an **AI discovery companion** for Spotify. Unlike a recommender (which optimises the *next play*), Crate is an **agent with memory** that optimises **adoption** — turning a first play into a lasting favourite. These diagrams render natively in a GitHub README (Mermaid).

## 1. System architecture (runtime)

```mermaid
flowchart LR
    U([Listener]) --> WEB["Next.js web app<br/>Today's Dig · comfort dial · missions<br/>(Vercel)"]
    WEB <-->|REST JSON| API["FastAPI<br/>agent runtime + API"]

    subgraph AI["AI services"]
      CLAUDE["Claude API<br/>bridges · mission plans · taste summaries"]
      EMB["OpenAI embeddings<br/>text-embedding-3-large"]
    end

    subgraph DATA["Data layer (Supabase / Postgres)"]
      PG[("Postgres<br/>users · events · adoption · missions")]
      VEC[("Vector store<br/>pgvector — Pinecone-swappable")]
    end

    CAT["Catalog source<br/>seed JSON — Spotify-API-swappable"]

    API --> CLAUDE
    API --> EMB
    API <--> PG
    API <--> VEC
    API --> CAT
    EMB -. embeds catalog + taste .-> VEC
```

## 2. The agent loop (the heart of Crate)

A recommender returns a ranked list. Crate runs a **closed loop** on every `/loop/tick` (and before each dig):

```mermaid
flowchart LR
    P["PLAN<br/>choose a stretch via vector band<br/>scaled by the comfort dial"] --> A["ACT<br/>generate grounded bridges ·<br/>serve the dig · re-serve high-potential tracks"]
    A --> O["OBSERVE<br/>ingest plays · recompute adoption<br/>(≥4 days across ≥3 weeks, unprompted)"]
    O --> D["ADAPT<br/>update taste memory ·<br/>nudge comfort on high skips · mission progress"]
    D --> P
```

## 3. Request flow — `GET /dig`

```mermaid
sequenceDiagram
    participant U as Listener
    participant W as Next.js
    participant API as FastAPI
    participant V as Vector store
    participant C as Claude
    participant DB as Postgres

    U->>W: open Crate (pick comfort)
    W->>API: GET /dig?user_id&comfort
    API->>DB: load taste_profile + history
    API->>V: query band(comfort), exclude known/rejected
    V-->>API: candidate tracks
    API->>C: write grounded bridge per candidate
    C-->>API: bridge + shared attributes
    API->>DB: insert discovery_events (surface = dig)
    API-->>W: greeting + 3–5 {track, bridge}
    W-->>U: Today's Dig
```

## 4. AI Review Discovery Engine (how the insights were sourced)

The product above was justified by an **insight pipeline** (n8n-orchestrated) that mined public review/forum data — the same engine described in the strategy deck.

```mermaid
flowchart LR
    SRC["Sources<br/>App/Play Store · Reddit · X · YouTube · Product Hunt"] --> ING["Ingest<br/>(n8n, daily)"]
    ING --> CLEAN["Clean & dedupe<br/>embedding cosine"]
    CLEAN --> CLUS["Cluster<br/>BERTopic"]
    CLUS --> TAG["Tag with Claude<br/>topic · sentiment · unmet need"]
    TAG --> OPP["Opportunity backlog<br/>+ dashboard"]
```

## North Star
**Discovery Adoption Rate** — % of monthly actives who adopt ≥1 newly-discovered artist into long-term rotation (played on **≥4 distinct days across ≥3 weeks, unprompted**), with **engagement non-inferiority** as a guardrail.
