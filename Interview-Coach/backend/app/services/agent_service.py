import asyncio
import json
import logging
import random
import re
from typing import Dict, List, Optional

from .sap_client import SAPAIClient

logger = logging.getLogger(__name__)

INTERVIEW_TYPE_LABELS = {
    "technical": "technical and coding",
    "management": "leadership and management",
    "behavioral": "behavioral (STAR-method)",
    "salary_negotiation": "salary negotiation and compensation",
}


class AgentService:
    """
    Orchestrates the three AI agents (GPT, Claude, Gemini) for:
      1. Company analysis
      2. Sequential question generation (GPT → Claude → Gemini)
      3. Parallel answer evaluation
      4. Consolidated feedback synthesis
      5. Session summary
    """

    def __init__(self, sap_client: SAPAIClient, config: dict):
        self.client = sap_client
        self.models = config["models"]
        self.claude_thinking = config.get("claude_thinking", {})
        self.gen = config["generation"]
        self.interview_cfg = config["interview"]

    # ------------------------------------------------------------------
    # Company Analysis
    # ------------------------------------------------------------------

    async def analyze_company(self, company_name: str, interview_type: str) -> str:
        """Use GPT to produce a company context paragraph for question framing."""
        itype_label = INTERVIEW_TYPE_LABELS.get(interview_type, interview_type)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert talent-acquisition researcher with deep knowledge of "
                    "companies, their cultures, and interview processes worldwide."
                ),
            },
            {
                "role": "user",
                "content": (
                    f'Analyze the company "{company_name}" for interview preparation.\n\n'
                    f"Consider:\n"
                    f"1. The company's industry, domain and size\n"
                    f"2. Their technology stack and approach (if known)\n"
                    f"3. Culture and values (innovation-driven, process-driven, consulting, etc.)\n"
                    f"4. What skills/qualities they prioritise in candidates\n"
                    f"5. How their {itype_label} interviews are typically structured and what they test\n\n"
                    f"Write 4-5 focused sentences that will help craft highly relevant interview questions. "
                    f"Highlight what makes their interviews unique and any domain-specific knowledge that matters."
                ),
            },
        ]
        return await self.client.complete(
            model=self.models["gpt"],
            messages=messages,
            temperature=self.gen["temperature_analysis"],
        )

    # ------------------------------------------------------------------
    # Question Generation Pipeline
    # ------------------------------------------------------------------

    async def generate_questions(
        self,
        company_name: str,
        job_title: str,
        job_description: str,
        years_experience: int,
        interview_type: str,
        company_analysis: str,
    ) -> List[Dict]:
        """
        Parallel question generation:
          Stage 1  – GPT generates all 6 questions (single call preserves coherence)
          Stage 2-3 – Split into two halves; Claude→Gemini runs on both concurrently

        Halving the payload for each refinement call AND running them in parallel
        reduces total wall-clock time by ~50% vs the old sequential approach.
        """
        logger.info("Stage 1: GPT generating initial 6 questions for %s", company_name)
        initial = await self._gpt_generate(
            company_name, job_title, job_description, years_experience, interview_type, company_analysis
        )

        # Pre-assign agents so callers can use them immediately (partial-ready support)
        agents = ["gpt", "gpt", "claude", "claude", "gemini", "gemini"]
        random.shuffle(agents)

        logger.info("Stages 2-3: Parallel Claude→Gemini refinement on both halves")
        half_a, half_b = await asyncio.gather(
            self._refine_half(
                initial[:3], company_name, job_title, job_description, interview_type, company_analysis
            ),
            self._refine_half(
                initial[3:], company_name, job_title, job_description, interview_type, company_analysis
            ),
        )
        final = half_a + half_b

        result = []
        for idx, q in enumerate(final[:6]):
            result.append(
                {
                    "question_id": idx + 1,
                    "question": q.get("question", ""),
                    "difficulty": q.get("difficulty", "medium"),
                    "rationale": q.get("rationale", ""),
                    "assigned_agent": agents[idx],
                    "answer": None,
                    "evaluations": {},
                    "consolidated_feedback": None,
                    "avg_score": None,
                    "status": "pending",
                }
            )
        return result

    async def _refine_half(
        self,
        questions: List[Dict],
        company_name: str,
        job_title: str,
        job_description: str,
        interview_type: str,
        company_analysis: str,
    ) -> List[Dict]:
        """Run Claude refinement then Gemini finalization on a batch of ~3 questions."""
        refined = await self._claude_refine(
            questions, company_name, job_title, job_description, interview_type, company_analysis
        )
        return await self._gemini_finalise(refined, company_name, job_title, interview_type)

    async def _gpt_generate(
        self, company_name, job_title, job_description, years_experience, interview_type, company_analysis
    ):
        itype_label = INTERVIEW_TYPE_LABELS.get(interview_type, interview_type)
        # Truncate to avoid oversized prompts / timeouts
        jd = job_description[:2000] + ("…" if len(job_description) > 2000 else "")
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a highly experienced {itype_label} interviewer at {company_name}. "
                    f"You craft challenging, deeply relevant interview questions tailored to the "
                    f"company's specific domain and the candidate's experience level."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate exactly 6 {itype_label} interview questions.\n\n"
                    f"Candidate Profile:\n"
                    f"- Job Title: {job_title}\n"
                    f"- Years of Experience: {years_experience}\n"
                    f"- Job Description: {jd}\n\n"
                    f"Company Context:\n"
                    f"- Company: {company_name}\n"
                    f"- Analysis: {company_analysis}\n\n"
                    f"Requirements:\n"
                    f"- Questions must reflect {company_name}'s specific domain, culture, and priorities\n"
                    f"- Calibrate for {years_experience} years of experience\n"
                    f"- Mix of difficulties: 2 easy, 3 medium, 1 hard\n"
                    f"- Be concrete and specific — avoid generic questions\n\n"
                    f"Return ONLY a valid JSON array (no markdown, no explanation):\n"
                    f'[{{"question_id": 1, "question": "...", "difficulty": "easy|medium|hard", "rationale": "..."}}]'
                ),
            },
        ]
        response = await self.client.complete(
            model=self.models["gpt"],
            messages=messages,
            temperature=self.gen["temperature_questions"],
        )
        return self._parse_questions(response)

    async def _claude_refine(
        self, questions, company_name, job_title, job_description, interview_type, company_analysis
    ):
        itype_label = INTERVIEW_TYPE_LABELS.get(interview_type, interview_type)
        jd = job_description[:2000] + ("…" if len(job_description) > 2000 else "")
        questions_json = json.dumps(questions, indent=2)
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a senior interview coach with deep expertise in {company_name}'s "
                    f"hiring process. You review and sharpen interview questions for maximum "
                    f"impact and relevance."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Review and improve these 6 {itype_label} interview questions for {company_name}.\n\n"
                    f"Current Questions:\n{questions_json}\n\n"
                    f"Job Title: {job_title}\n"
                    f"Job Description: {jd}\n"
                    f"Company Analysis: {company_analysis}\n\n"
                    f"Improvement goals:\n"
                    f"1. Sharpen clarity and specificity — remove any vagueness\n"
                    f"2. Add company-specific context where possible\n"
                    f"3. Ensure questions genuinely probe what matters at {company_name}\n"
                    f"4. Adjust difficulty labels if miscalibrated\n"
                    f"5. Make behavioral questions use concrete scenario framing\n\n"
                    f"Return ONLY a valid JSON array with exactly 6 improved questions:\n"
                    f'[{{"question_id": 1, "question": "...", "difficulty": "easy|medium|hard", "rationale": "..."}}]'
                ),
            },
        ]
        response = await self.client.complete(
            model=self.models["claude"],
            messages=messages,
            temperature=self.gen["temperature_questions"],
        )
        return self._parse_questions(response)

    async def _gemini_finalise(self, questions, company_name, job_title, interview_type):
        itype_label = INTERVIEW_TYPE_LABELS.get(interview_type, interview_type)
        questions_json = json.dumps(questions, indent=2)
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are the lead interviewer at {company_name} responsible for final "
                    f"approval of all interview questions. You ensure they are precise, "
                    f"strategically ordered, and collectively provide comprehensive evaluation."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Perform the final review of these 6 {itype_label} interview questions.\n\n"
                    f"Questions:\n{questions_json}\n\n"
                    f"Final review checklist:\n"
                    f"1. Eliminate any redundancy between questions\n"
                    f"2. Ensure good progression: easier → harder\n"
                    f"3. Polish language: professional, clear, unambiguous\n"
                    f"4. Confirm each question has a clearly evaluable answer\n"
                    f"5. Verify the 6 questions together provide comprehensive coverage\n\n"
                    f"Return ONLY the final valid JSON array with exactly 6 questions:\n"
                    f'[{{"question_id": 1, "question": "...", "difficulty": "easy|medium|hard", "rationale": "..."}}]'
                ),
            },
        ]
        response = await self.client.complete(
            model=self.models["gemini"],
            messages=messages,
            temperature=self.gen["temperature_questions"],
        )
        return self._parse_questions(response)

    # ------------------------------------------------------------------
    # Answer Evaluation
    # ------------------------------------------------------------------

    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        company_name: str,
        job_title: str,
        interview_type: str,
    ) -> Dict:
        """All three agents evaluate the answer concurrently; returns their individual results."""
        tasks = [
            self._single_evaluate(self.models["gpt"], question, answer, company_name, job_title, interview_type),
            self._single_evaluate(self.models["claude"], question, answer, company_name, job_title, interview_type),
            self._single_evaluate(self.models["gemini"], question, answer, company_name, job_title, interview_type),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        evaluations = {}
        for agent, result in zip(["gpt", "claude", "gemini"], results):
            if isinstance(result, Exception):
                logger.warning("Evaluation by %s failed: %s", agent, result)
                evaluations[agent] = {"score": 5, "feedback": "Evaluation temporarily unavailable."}
            else:
                evaluations[agent] = result

        return evaluations

    async def _single_evaluate(self, model, question, answer, company_name, job_title, interview_type):
        itype_label = INTERVIEW_TYPE_LABELS.get(interview_type, interview_type)
        safe_answer = answer.strip() if answer and answer.strip() else "[No answer provided]"

        messages = [
            {
                "role": "system",
                "content": (
                    f"You are an expert interviewer at {company_name} evaluating a candidate "
                    f"for a {job_title} position."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Evaluate this {itype_label} interview answer:\n\n"
                    f"Question: {question}\n\n"
                    f"Candidate's Answer: {safe_answer}\n\n"
                    f"Provide:\n"
                    f"1. A score from 1-10 (1=very poor, 5=average, 10=exceptional)\n"
                    f"2. Brief, constructive feedback (2-3 sentences)\n\n"
                    f"Return ONLY valid JSON (no markdown):\n"
                    f'{{"score": <integer 1-10>, "feedback": "<feedback text>"}}'
                ),
            },
        ]
        response = await self.client.complete(
            model=model,
            messages=messages,
            temperature=self.gen["temperature_evaluation"],
        )
        return self._parse_evaluation(response)

    # ------------------------------------------------------------------
    # Consolidated Feedback
    # ------------------------------------------------------------------

    async def generate_consolidated_feedback(
        self,
        question: str,
        answer: str,
        evaluations: Dict,
        company_name: str,
        job_title: str,
        interview_type: str,
    ) -> str:
        """Synthesise three evaluations into a single, actionable feedback paragraph."""
        gpt_e = evaluations.get("gpt", {})
        claude_e = evaluations.get("claude", {})
        gemini_e = evaluations.get("gemini", {})

        scores = [e.get("score", 0) for e in [gpt_e, claude_e, gemini_e] if isinstance(e, dict)]
        avg_score = sum(scores) / len(scores) if scores else 0

        safe_answer = answer.strip() if answer and answer.strip() else "[No answer provided]"
        messages = [
            {
                "role": "system",
                "content": "You are a senior interview coach providing constructive, actionable feedback.",
            },
            {
                "role": "user",
                "content": (
                    f"Synthesise feedback from three interviewers into one consolidated response.\n\n"
                    f"Context: {company_name} | {job_title} | {INTERVIEW_TYPE_LABELS.get(interview_type, interview_type)}\n\n"
                    f"Question: {question}\n\n"
                    f"Candidate's Answer: {safe_answer}\n\n"
                    f"Individual Evaluations:\n"
                    f"- GPT (Score: {gpt_e.get('score', 'N/A')}/10): {gpt_e.get('feedback', 'N/A')}\n"
                    f"- Claude (Score: {claude_e.get('score', 'N/A')}/10): {claude_e.get('feedback', 'N/A')}\n"
                    f"- Gemini (Score: {gemini_e.get('score', 'N/A')}/10): {gemini_e.get('feedback', 'N/A')}\n\n"
                    f"Consensus Score: {avg_score:.1f}/10\n\n"
                    f"Write a consolidated feedback (4-5 sentences) that:\n"
                    f"1. States the overall performance level\n"
                    f"2. Highlights the main strengths\n"
                    f"3. Identifies the key areas for improvement\n"
                    f"4. Gives one specific, actionable tip\n\n"
                    f"Be direct and honest — if the answer was poor, say so clearly and explain exactly why. "
                    f"Do not soften weak answers with filler praise. If it was good, acknowledge it specifically."
                ),
            },
        ]
        return await self.client.complete(
            model=self.models["gpt"],
            messages=messages,
            temperature=self.gen["temperature_feedback"],
        )

    # ------------------------------------------------------------------
    # Session Summary
    # ------------------------------------------------------------------

    async def generate_session_summary(self, session: Dict) -> str:
        """Generate an overall performance summary for a completed session."""
        setup = session.get("setup", {})
        questions = session.get("questions", [])
        answered = [q for q in questions if q.get("status") == "evaluated"]
        not_attended = [q for q in questions if q.get("status") == "not_attended"]

        if not answered:
            return "No questions were answered in this session."

        avg_score = sum(q.get("avg_score", 0) for q in answered) / len(answered)

        q_summary = "\n".join(
            [
                f"Q{q['question_id']} [{q.get('difficulty','medium')}]: {q['question'][:100]}…\n"
                f"  Score: {q.get('avg_score', 0):.1f}/10 | "
                f"Candidate's answer: {(q.get('answer') or '[no answer]')[:200]}… | "
                f"Evaluator feedback: {(q.get('consolidated_feedback') or '')[:150]}…"
                for q in answered
            ]
        )

        not_attended_note = (
            f"\n\nNote: {len(not_attended)} question(s) were not attended at all."
            if not_attended else ""
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a brutally honest, no-nonsense senior hiring manager and interview coach. "
                    "Your job is to give candidates the hard truth about their performance — not to make them feel good. "
                    "If their answers were weak, vague, or showed gaps, say so directly. "
                    "False encouragement is harmful. Candidates need to know exactly where they stand "
                    "and precisely what they must do to improve. Be specific, be critical, be constructive."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Write a performance verdict for this interview session. Do NOT soften the truth.\n\n"
                    f"Interview Context:\n"
                    f"- Company: {setup.get('company_name')}\n"
                    f"- Role: {setup.get('job_title')}\n"
                    f"- Interview Type: {INTERVIEW_TYPE_LABELS.get(setup.get('interview_type', ''), setup.get('interview_type', ''))}\n"
                    f"- Candidate Experience: {setup.get('years_experience')} years\n"
                    f"- Overall average score: {avg_score:.1f}/10\n"
                    f"- Questions answered: {len(answered)} of {len(questions)}"
                    f"{not_attended_note}\n\n"
                    f"Per-Question Breakdown:\n{q_summary}\n\n"
                    f"Instructions for the summary:\n"
                    f"1. VERDICT: State clearly whether this performance would pass or fail a real interview at {setup.get('company_name')}. "
                    f"   Do not hedge. If the score is below 5/10, say they would very likely be rejected.\n"
                    f"2. WHAT WENT WRONG: List the specific weaknesses exposed by their answers — "
                    f"   vague thinking, missing concepts, lack of depth, poor structure, etc. Be concrete.\n"
                    f"3. KNOWLEDGE GAPS: Name the exact topics, frameworks, or skills the candidate needs to study. "
                    f"   Reference the actual questions and answers as evidence.\n"
                    f"4. IMPROVEMENT PLAN: Give 3-5 specific, actionable steps to improve — "
                    f"   e.g. study topic X, practice format Y, read resource Z. No generic advice.\n"
                    f"5. REALITY CHECK: End with an honest assessment of readiness. "
                    f"   If they need 2 months of prep, say so. Do not encourage false confidence.\n\n"
                    f"Tone: Direct, professional, tough but constructive. No platitudes. No 'great potential' filler. "
                    f"Format: Plain paragraphs with section headers (##). No bullet spam."
                ),
            },
        ]
        return await self.client.complete(
            model=self.models["claude"],
            messages=messages,
            temperature=self.gen["temperature_summary"],
        )

    # ------------------------------------------------------------------
    # JSON Parsing Helpers
    # ------------------------------------------------------------------

    def _parse_questions(self, response: str) -> List[Dict]:
        """Extract a JSON array of questions from the model response."""
        cleaned = re.sub(r"```(?:json)?\s*", "", response).replace("```", "").strip()
        start = cleaned.find("[")
        end = cleaned.rfind("]") + 1
        if start != -1 and end > start:
            cleaned = cleaned[start:end]

        try:
            items = json.loads(cleaned)
            if isinstance(items, list):
                normalised = []
                for i, q in enumerate(items[:6]):
                    normalised.append(
                        {
                            "question_id": q.get("question_id", i + 1),
                            "question": str(q.get("question", "")),
                            "difficulty": q.get("difficulty", "medium"),
                            "rationale": str(q.get("rationale", "")),
                        }
                    )
                return normalised
        except json.JSONDecodeError:
            pass

        # Fallback: extract numbered lines as questions
        return self._fallback_questions(response)

    def _parse_evaluation(self, response: str) -> Dict:
        """Extract score and feedback from a model evaluation response."""
        cleaned = re.sub(r"```(?:json)?\s*", "", response).replace("```", "").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            cleaned = cleaned[start:end]

        try:
            data = json.loads(cleaned)
            score = data.get("score", 5)
            if isinstance(score, str):
                m = re.search(r"\d+", score)
                score = int(m.group()) if m else 5
            return {
                "score": min(10, max(1, int(score))),
                "feedback": str(data.get("feedback", "")),
            }
        except (json.JSONDecodeError, ValueError):
            pass

        # Regex fallback
        score_match = re.search(r'"?score"?\s*:\s*(\d+)', response)
        score = int(score_match.group(1)) if score_match else 5
        return {"score": min(10, max(1, score)), "feedback": "Evaluation completed."}

    def _fallback_questions(self, text: str) -> List[Dict]:
        """Last-resort: extract lines that look like questions."""
        questions = []
        for line in text.split("\n"):
            line = line.strip()
            if re.match(r"^(\d+[\.\)]\s+|[-•]\s+)", line) and len(line) > 20:
                q_text = re.sub(r"^(\d+[\.\)]\s+|[-•]\s+)", "", line)
                questions.append(
                    {
                        "question_id": len(questions) + 1,
                        "question": q_text,
                        "difficulty": "medium",
                        "rationale": "",
                    }
                )
                if len(questions) >= 6:
                    break
        return questions or [
            {"question_id": i + 1, "question": f"Question {i + 1}", "difficulty": "medium", "rationale": ""}
            for i in range(6)
        ]
