"""Prompt templates for LLM Council."""

# Stage 1: Initial response prompt
STAGE1_PROMPT = """You are a council member evaluating the following request:

{user_query}

Provide your individual response. Be thorough, accurate, and consider multiple perspectives."""

# Stage 2: Ranking prompt
STAGE2_RANKING_PROMPT = """You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

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

Here are the proposed changes from different models (anonymized):

{changes_text}

Your task:
1. Evaluate each proposal's correctness, completeness, and code quality
2. Identify strengths and weaknesses of each approach
3. Provide a final ranking

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the proposals from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the proposal label (e.g., "1. Proposal A")

Now provide your evaluation and ranking:"""

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
