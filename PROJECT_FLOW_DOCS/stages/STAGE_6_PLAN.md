 Stage 6: LangGraph Flows - 3 PR Strategy                           │
     │                                                                    │
     │ PR #12: Core Nodes (Router + Generator)                            │
     │                                                                    │
     │ Goal: Build the two remaining nodes needed by all flows            │
     │                                                                    │
     │ Files to Create:                                                   │
     │ 1. app/rag/nodes/router_node.py                                    │
     │   - classify_intent(state: GraphState) -> GraphState               │
     │   - Uses query_router.jinja2 template                              │
     │   - Calls                                                          │
     │ llm_client.ainvoke_gemini_structured(IntentClassification)         │
     │   - Returns: "chitchat" | "qa" | "linkedin"                        │
     │ 2. app/rag/nodes/generator.py                                      │
     │   - generate_response(state: GraphState) -> GraphState             │
     │   - Checks state["intent"]                                         │
     │   - Renders appropriate template (chitchat_flow, rag_qa, or        │
     │ linkedin_post_generate)                                            │
     │   - Calls llm_client.ainvoke_claude() for text generation          │
     │   - Stores response and metadata in state                          │
     │ 3. tests/unit/test_router_node.py (8+ tests)                       │
     │   - Test chitchat classification                                   │
     │   - Test Q&A classification                                        │
     │   - Test LinkedIn classification                                   │
     │   - Test edge cases (empty query, missing history)                 │
     │ 4. tests/unit/test_generator.py (8+ tests)                         │
     │   - Test chitchat generation                                       │
     │   - Test Q&A generation                                            │
     │   - Test LinkedIn generation                                       │
     │   - Test missing graded_chunks                                     │
     │   - Test metadata tracking                                         │
     │                                                                    │
     │ Acceptance Criteria:                                               │
     │ - All tests passing (16+ tests)                                    │
     │ - 100% coverage for both nodes                                     │
     │ - Compatible with existing GraphState                              │
     │                                                                    │
     │ ---                                                                │
     │ PR #13: Simple Flows (Chitchat + Q&A)                              │
     │                                                                    │
     │ Goal: Implement the two simpler flows to establish patterns        │
     │                                                                    │
     │ Files to Create:                                                   │
     │ 1. app/rag/graphs/__init__.py                                      │
     │ 2. app/rag/graphs/flows/__init__.py                                │
     │ 3. app/rag/graphs/flows/chitchat_flow.py                           │
     │   - Build simple graph: router → generator (no RAG)                │
     │   - Export compiled graph or function                              │
     │   - No retrieval/grading nodes                                     │
     │ 4. app/rag/graphs/flows/qa_flow.py                                 │
     │   - Build full RAG graph: retrieve → grade → generate              │
     │   - Connect existing nodes from Stage 5 + new generator            │
     │   - Export compiled graph                                          │
     │ 5. tests/unit/test_chitchat_flow.py (5+ tests)                     │
     │   - Test flow execution with mocked generator                      │
     │   - Test state updates                                             │
     │   - Test edge cases                                                │
     │ 6. tests/unit/test_qa_flow.py (5+ tests)                           │
     │   - Test flow execution with mocked nodes                          │
     │   - Test state transitions                                         │
     │   - Test empty graded_chunks scenario                              │
     │                                                                    │
     │ Acceptance Criteria:                                               │
     │ - Both flows execute successfully                                  │
     │ - Unit tests passing (10+ tests)                                   │
     │ - Flows use RetryPolicy as per LANGCHAIN_RETRY.md                  │
     │                                                                    │
     │ ---                                                                │
     │ PR #14: LinkedIn Flow + Main Router + Integration Tests            │
     │                                                                    │
     │ Goal: Complete the orchestration and validate end-to-end           │
     │                                                                    │
     │ Files to Create:                                                   │
     │ 1. app/rag/graphs/flows/linkedin_flow.py                           │
     │   - Build RAG graph: retrieve → grade → generate (with topic       │
     │ extraction)                                                        │
     │   - Handle template (based on Question 2 answer)                   │
     │   - Export compiled graph                                          │
     │ 2. app/rag/graphs/router.py                                        │
     │   - Build main graph with conditional routing                      │
     │   - Route to appropriate flow based on intent                      │
     │   - Export run_graph(user_query, user_id, conversation_history)    │
     │ function                                                           │
     │   - (Signature depends on Question 1 answer)                       │
     │ 3. tests/unit/test_linkedin_flow.py (5+ tests)                     │
     │   - Test LinkedIn flow with mocked nodes                           │
     │   - Test topic extraction                                          │
     │   - Test template integration (if applicable)                      │
     │ 4. tests/integration/test_rag_flows.py (8+ tests)                  │
     │   - Test chitchat flow end-to-end                                  │
     │   - Test Q&A flow with real Qdrant/DB                              │
     │   - Test LinkedIn flow end-to-end                                  │
     │   - Test router classification                                     │
     │   - Test state transitions                                         │
     │   - Test error handling                                            │
     │                                                                    │
     │ Acceptance Criteria:                                               │
     │ - All flows integrated in main router                              │
     │ - Integration tests passing (8+ tests)                             │
     │ - End-to-end validation successful                                 │
     │ - Compatible with Phase 7 (WebSocket) expectations                 │
     │                                                                    │
     │ ---                                                                │
     │ Dependencies & Blockers                                            │
     │                                                                    │
     │ - Before PR #12: Need answers to 4 questions above                 │
     │ - Before PR #13: PR #12 must be merged                             │
     │ - Before PR #14: PR #13 must be merged                             │
     │                                                                    │
     │ Estimated Test Count                                               │
     │                                                                    │
     │ - PR #12: 16+ unit tests                                           │
     │ - PR #13: 10+ unit tests                                           │
     │ - PR #14: 13+ tests (5 unit + 8 integration)                       │
     │ - Total: 39+ tests for Stage 6                                     │
     │                                                                    │
     │ Key Decisions Needed (4 Questions Above)                           │
     │                                                                    │
     │ 1. Where to fetch conversation_history? (impacts run_graph()       │
     │ signature)                                                         │
     │ 2. How to handle LinkedIn templates in MVP? (impacts Phase 6/8     │
     │ split)                                                             │
     │ 3. RetryPolicy strategy? (all nodes vs selective)                  │
     │ 4. Flow architecture pattern? (separate graphs vs single graph)