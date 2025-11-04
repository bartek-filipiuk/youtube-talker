# Real-World Conversation Testing Plan

## Test Environment
- **Channel**: przeprogramowani (5 Polish videos about AI/programming)
- **URL**: `http://localhost:4321/channels/przeprogramowani/chat`
- **Tool**: Chrome DevTools MCP

## Test Objectives
1. Validate intent classification accuracy in real frontend
2. Assess response quality and contextual appropriateness
3. Test conversation flow and intelligence
4. Verify all RAG flows work end-to-end

---

## Test Scenario: Progressive Conversation (10 Questions)

### Phase 1: Discovery (2 questions)

**Q1: "what videos are here?"**
- **Intent**: `metadata`
- **Expected**: List all 5 videos from channel
- **Validates**: Metadata listing, channel context

**Q2: "find videos about AI"**
- **Intent**: `metadata_search`
- **Expected**: Search and return matching videos (should find multiple)
- **Validates**: Vector search, semantic matching

---

### Phase 2: Exact Title Recognition (2 questions)

**Q3: "tell me about 19% WOLNIEJ PRZEZ AI? Jak AI wpływa na programistów - zaskakujące badanie!"**
- **Intent**: `qa` (exact title with special chars)
- **Expected**: Direct answer from video content, no search step
- **Validates**: Exact title recognition fix (0% → 100%)

**Q4: "summarize 10x LEPSZY PROGRAMISTA? Programowanie z AI od startu do mety projektu - jak robić to dobrze?"**
- **Intent**: `qa` (exact title with question mark)
- **Expected**: Summary from transcript, immediate response
- **Validates**: Punctuation handling in exact titles

---

### Phase 3: Partial Title & Search (2 questions)

**Q5: "give me summary of 10x lepszy video"**
- **Intent**: `metadata_search_and_summarize`
- **Expected**: Find video, then ask what to know OR provide summary
- **Validates**: Partial title matching, compound intent

**Q6: "what does the testy z Claude video say?"**
- **Intent**: `metadata_search_and_summarize`
- **Expected**: Find "Wprowadź testy z Claude..." video, provide context
- **Validates**: Fuzzy matching with partial title

---

### Phase 4: Content Questions (2 questions)

**Q7: "jak AI wpływa na wydajność programistów?"** (Polish: "how does AI affect programmer productivity?")
- **Intent**: `qa`
- **Expected**: Answer from relevant video content
- **Validates**: Topic-based QA, multilingual query

**Q8: "what are the main tips for programming with AI?"**
- **Intent**: `qa`
- **Expected**: Extract tips from relevant videos
- **Validates**: Cross-video context retrieval

---

### Phase 5: Advanced Features (2 questions)

**Q9: "find the video about 19% slower and create linkedin post about it"**
- **Intent**: `linkedin`
- **Expected**: Prioritize LinkedIn creation, use video context
- **Validates**: LinkedIn priority fix, compound intent handling

**Q10: "yo what else is on this channel?"** (informal)
- **Intent**: `metadata`
- **Expected**: List remaining/all videos, handle slang
- **Validates**: Informal language robustness

---

## Evaluation Criteria

For each response, I will assess:

1. **Intent Classification**
   - ✅ Correct intent chosen
   - ✅ Confidence score (expect 0.85-0.98)

2. **Response Quality**
   - ✅ No errors or "something went wrong" messages
   - ✅ Contextually appropriate (not generic)
   - ✅ Actually uses video content (not hallucinated)
   - ✅ Natural language, not robotic

3. **Conversation Intelligence**
   - ✅ Maintains context across messages
   - ✅ Smooth flow (no abrupt topic jumps)
   - ✅ Asks clarifying questions when needed
   - ✅ Provides helpful follow-up suggestions

4. **Technical Validation**
   - ✅ WebSocket connection stable
   - ✅ Response latency acceptable (<5s for QA)
   - ✅ Proper HTML formatting in responses
   - ✅ No console errors in DevTools

---

## Execution Steps

1. Open Chrome DevTools MCP
2. Navigate to `http://localhost:4321/channels/przeprogramowani/chat`
3. Take initial snapshot to verify page loaded
4. Execute questions 1-10 sequentially
5. For each question:
   - Take snapshot before sending
   - Fill message input with question text
   - Click send button
   - Wait for response (use wait_for if needed)
   - Take snapshot of response
   - Document intent, response quality, observations
6. After all 10 questions, summarize findings

---

## Success Criteria

**Pass**:
- 9/10 questions with correct intent
- 9/10 questions with high-quality responses
- No system errors or crashes
- Natural conversation flow

**Fail**:
- <80% correct intent classification
- >2 error responses
- System crashes or WebSocket failures
- Robotic/generic responses

---

**Created**: 2025-11-04
**Status**: Ready for execution
