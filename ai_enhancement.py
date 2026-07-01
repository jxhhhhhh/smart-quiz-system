#!/usr/bin/env python3
"""
Smart Quiz System - AI Enhancement Module
Integrates OpenAI-compatible API for intelligent question analysis,
tagging, and explanation generation.

支持 DeepSeek / OpenAI / Qwen 等兼容 API。
"""

import json
from abc import ABC, abstractmethod
from typing import Dict
from database import DatabaseManager
import config

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class AIClient(ABC):
    """Abstract base class for AI clients."""

    @abstractmethod
    def analyze_question(self, question_text: str) -> Dict:
        pass

    @abstractmethod
    def get_question_explanation(self, question_text: str, answer: str = None) -> Dict:
        pass


class OpenAIClient(AIClient):
    """OpenAI-compatible client implementation (v1.x SDK)."""

    def __init__(self, api_key: str = None, base_url: str = None,
                 model: str = None):
        if OpenAI is None:
            raise ImportError("openai 库未安装，请执行: pip install openai")

        self.api_key = api_key or config.AI_API_KEY
        if not self.api_key:
            raise ValueError("API key is missing.")

        self.model = model or config.AI_DEFAULT_MODEL
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=base_url or config.AI_DEFAULT_BASE_URL,
        )

    def analyze_question(self, question_text: str) -> Dict:
        prompt = f"""分析以下题目，返回 JSON 对象：
题目：{question_text}

字段：
1. question_type: 题型（如：单选题、多选题、判断题、填空题、简答题）
2. knowledge_points: 知识点列表
3. difficulty: 难度（1=基础, 2=应用, 3=综合）
4. subject: 学科分类

只返回 JSON，不要其他文字。"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是题目分析专家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            result = response.choices[0].message.content.strip()
            # 提取 JSON（兼容 markdown 代码块）
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
            return json.loads(result.strip())
        except Exception as e:
            return {"error": str(e)}

    def get_question_explanation(self, question_text: str, answer: str = None) -> Dict:
        answer_prompt = f"，正确答案是 {answer}" if answer else ""
        prompt = f"""解释以下题目{answer_prompt}：
题目：{question_text}

请给出清晰的解释和正确答案的推理过程。
返回 JSON 对象，字段："explanation"（字符串）。"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位有帮助的老师。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            result = response.choices[0].message.content.strip()
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
            return json.loads(result.strip())
        except Exception as e:
            return {"error": str(e)}


class QuestionAIEnhancementService:
    """Service to batch enhance questions in the database."""

    def __init__(self, api_key: str = None, base_url: str = None,
                 model: str = "deepseek-chat"):
        self.client = OpenAIClient(api_key=api_key, base_url=base_url, model=model)
        self.db = DatabaseManager()

    def enhance_question(self, question_id: int, content: str,
                         options: str, answer: str):
        analysis = self.client.analyze_question(content)
        if "error" in analysis:
            raise RuntimeError(analysis["error"])

        explanation = self.client.get_question_explanation(content, answer)

        tags = analysis.get("knowledge_points", [])
        if isinstance(tags, list):
            tags = ", ".join(str(t) for t in tags)

        self.db.execute(
            "UPDATE questions SET ai_enhanced = 1, tags = ?, subject = ? WHERE id = ?",
            (tags, analysis.get("subject", ""), question_id)
        )
        self.db.commit()

    def batch_enhance_all_questions(self):
        questions = self.db.execute(
            "SELECT id, question_content, options, correct_answer "
            "FROM questions WHERE ai_enhanced = 0"
        ).fetchall()
        success_count = 0
        for q in questions:
            try:
                self.enhance_question(
                    q['id'], q['question_content'],
                    q['options'], q['correct_answer']
                )
                success_count += 1
            except Exception as e:
                print(f"Failed to enhance question {q['id']}: {e}")
        return {"success_count": success_count}

    def close(self):
        self.db.close()
