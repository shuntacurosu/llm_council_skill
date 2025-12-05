"""Prompt templates for LLM Council."""

# Stage 1: Initial response prompt
STAGE1_PROMPT = """You are a council member evaluating the following request:

{user_query}

Provide your individual response. Be thorough, accurate, and consider multiple perspectives."""

# Stage 2: Ranking prompt
STAGE2_RANKING_PROMPT = """You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized as A, B, C, D, E):

{responses_text}

Your task:
1. Briefly evaluate each response (A, B, C, D, E)
2. Provide your final ranking at the end

CRITICAL: You MUST end your response with EXACTLY this format:

FINAL RANKING:
1. A
2. B
3. C
4. D
5. E

(Replace with your actual ranking order. Use ONLY single letters A, B, C, D, E)

Now evaluate and rank:"""

# Stage 3: Chairman synthesis prompt
STAGE3_SYNTHESIS_PROMPT = """You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

# Code work specific prompts
CODE_STAGE1_PROMPT = """You are a council member working on the following code task:

{user_query}

Current working directory: {worktree_path}

Analyze the request and make the necessary code changes. Provide:
1. Your analysis of what needs to be done
2. The specific changes you would make
3. Your reasoning for these changes"""

CODE_STAGE2_REVIEW_PROMPT = """You are reviewing different code change proposals for the following task:

Original Task: {user_query}

Here are the proposed changes from different models. Each proposal is labeled with a SINGLE LETTER:
- Proposal A
- Proposal B
- Proposal C
- Proposal D
- Proposal E

{changes_text}

Your task:
1. Briefly evaluate each proposal (mention them as A, B, C, D, E)
2. Provide your final ranking at the end

═══════════════════════════════════════════════════════════════
CRITICAL FORMATTING REQUIREMENT - READ CAREFULLY:

You MUST end your response with a ranking section in EXACTLY this format:

FINAL RANKING:
1. A
2. B
3. C
4. D
5. E

RULES:
- Use ONLY the letters A, B, C, D, E (these are the ONLY valid proposal labels)
- Do NOT use any other letters like S, R, N, I, M, G, P, etc.
- Do NOT use model names or numbers
- Each letter must appear exactly once
- The order represents best (1) to worst (5)

EXAMPLE of CORRECT format:
FINAL RANKING:
1. C
2. A
3. E
4. B
5. D

═══════════════════════════════════════════════════════════════

Now evaluate and rank the proposals:"""

CODE_STAGE3_SYNTHESIS_PROMPT = """You are the Chairman of an LLM Council for code review. Multiple AI models have proposed code changes and reviewed each other's work.

Original Task: {user_query}

STAGE 1 - Individual Proposals:
{stage1_text}

STAGE 2 - Peer Reviews:
{stage2_text}

Your task as Chairman is to create the final, best code changes that should be applied. Consider:
- The strengths of each proposal
- The peer reviews and identified issues
- Best practices and code quality

Provide the final code changes that represent the council's collective decision."""
