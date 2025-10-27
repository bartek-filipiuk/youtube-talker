# RAG Pipeline Optimization Checklist

## ✅ Key Techniques to Speed Up RAG (Retrieval-Augmented Generation)

### 1. Pre-embedding & fast vector retrieval  
- Pre-compute embeddings for your documents (chunks) ahead of time rather than embedding at query time.  
- Use an Approximate Nearest Neighbour (ANN) index (e.g., HNSW, Faiss, optimized Elasticsearch) to reduce retrieval latency. :contentReference[oaicite:0]{index=0}  
- Limit search scope: e.g., segment your index by domain or namespace so you don’t search the full corpus for every query.  

### 2. Chunking documents & limiting context for LLM  
- Split large documents into manageable chunks so you minimise token usage in the prompt. :contentReference[oaicite:1]{index=1}  
- Select a reasonable “top k” of retrieved chunks (e.g., 3-5) rather than passing many fragments to the LLM. This reduces both prompt size and response latency.  

### 3. Two-stage retrieval / re-ranking  
- First, retrieve a larger set of candidates (e.g., top 20) via fast retrieval. Then, apply a lightweight re-ranking (e.g., cross-encoder or heuristic) and pick top 3-5 for generation. :contentReference[oaicite:2]{index=2}  
- This approach improves relevance while controlling generation cost (and hence latency).  

### 4. Optimize the LLM / prompt / token usage  
- Keep your prompt concise and focused; avoid including unnecessary context or verbose instructions that increase token count. :contentReference[oaicite:3]{index=3}  
- Use streaming (if supported) so the user sees first tokens earlier while the rest of the generation continues.  
- Consider using a lighter model or lower‐temperature / fewer output tokens if latency is critical.  

### 5. Profile & measure bottlenecks  
- Break down your RAG pipeline latency into components: embedding query time, vector search time, generation time. :contentReference[oaicite:4]{index=4}  
- Establish performance targets (e.g., 95th percentile < 500 ms) and monitor each segment (embedding, retrieval, ranking, generation).  
- Use instrumentation / logs to identify where you lose most time, then focus optimization effort there.  

### 6. Accept trade-offs for speed when acceptable  
- If ultra-high accuracy isn’t critical, reduce retrieval depth (smaller top k) or use a faster embedding model with slightly lower recall. :contentReference[oaicite:5]{index=5}  
- Use metadata filtering: e.g., only recent documents, only authoritative sources, to reduce retrieval load. :contentReference[oaicite:6]{index=6}  

---
