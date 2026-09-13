"""Bounded server-graded task evidence, not video surveillance or an LMS."""
from copy import deepcopy
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    prompt: str = Field(min_length=1, max_length=1000)
    kind: Literal["single", "multiple", "rating", "short_text", "long_text"] = "single"
    choices: list[str] = Field(default_factory=list, max_length=20)
    correct: list[int] | None = None
    required: bool = True


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    questions: list[Question] = Field(min_length=1, max_length=30)
    passing_score: int = Field(default=100, ge=0, le=100)
    max_attempts: int = Field(default=3, ge=1, le=20)


class Checkpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    position: str = Field(min_length=1, max_length=50)
    prompt: str = Field(min_length=1, max_length=1000)
    expected: str = Field(min_length=1, max_length=100)


class Checkpoints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[Checkpoint] = Field(min_length=1, max_length=20)
    minimum_correct: int | None = Field(default=None, ge=1)
    case_sensitive: bool = False
    max_attempts: int = Field(default=3, ge=1, le=20)

    @model_validator(mode="after")
    def bounded(self):
        if self.minimum_correct and self.minimum_correct > len(self.items):
            raise ValueError("Checkpoint threshold exceeds checkpoint count")
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("Checkpoint IDs must be unique")
        return self


def validate_config(kind, config):
    result = deepcopy(config)
    if kind == "quiz" and "assessment" not in result:
        raise ValueError("Quiz questions are required")
    if "assessment" in result:
        assessment = Assessment.model_validate(result["assessment"])
        if len({q.id for q in assessment.questions}) != len(assessment.questions):
            raise ValueError("Question IDs must be unique")
        for q in assessment.questions:
            if any(not choice.strip() or len(choice) > 500 for choice in q.choices):
                raise ValueError("Choices must contain bounded text")
            if q.kind in {"single", "multiple"} and len(q.choices) < 2:
                raise ValueError("Choice questions need at least two choices")
            if kind == "quiz":
                if q.kind not in {"single", "multiple"} or not q.correct:
                    raise ValueError("Automatically graded quizzes require objective choice questions")
                if any(i < 0 or i >= len(q.choices) for i in q.correct) or len(set(q.correct)) != len(q.correct):
                    raise ValueError("Correct choice indexes are invalid")
                if q.kind == "single" and len(q.correct) != 1:
                    raise ValueError("Single choice needs one correct answer")
            elif q.correct is not None:
                raise ValueError("Surveys have no correct/preferred answers")
        result["assessment"] = assessment.model_dump()
    if "checkpoints" in result:
        result["checkpoints"] = Checkpoints.model_validate(result["checkpoints"]).model_dump()
    return result


def participant_config(config):
    result = deepcopy(config)
    for q in result.get("assessment", {}).get("questions", []):
        q.pop("correct", None)
    for checkpoint in result.get("checkpoints", {}).get("items", []):
        checkpoint.pop("expected", None)
    return result


def grade(task, answers, attempt):
    config = task.task_config or {}
    assessment, checkpoints = config.get("assessment"), config.get("checkpoints")
    if not assessment and not checkpoints:
        if answers:
            raise HTTPException(422, "This task has no structured questions")
        return {}
    settings = assessment or checkpoints
    if attempt > settings.get("max_attempts", 3):
        raise HTTPException(409, "Attempt limit reached; contact the organizer")
    questions = settings.get("questions", settings.get("items", []))
    if set(answers) - {q['id'] for q in questions}:
        raise HTTPException(422, "Unknown answer IDs")
    correct = 0
    for q in questions:
        answer = answers.get(q['id'])
        if checkpoints:
            if not isinstance(answer, str) or len(answer) > 100:
                raise HTTPException(422, "Enter a bounded checkpoint code for every checkpoint")
            actual, expected = answer.strip(), q['expected'].strip()
            correct += actual == expected if settings.get('case_sensitive') else actual.casefold() == expected.casefold()
            continue
        if answer is None and not q.get('required', True) and task.task_type == 'survey':
            continue
        kind = q['kind']
        if kind in {'single', 'multiple'}:
            if not isinstance(answer, list) or any(type(i) is not int or i < 0 or i >= len(q['choices']) for i in answer):
                raise HTTPException(422, "Invalid choice answer")
            if len(answer) != len(set(answer)) or kind == 'single' and len(answer) != 1 or q.get('required', True) and not answer:
                raise HTTPException(422, "Select the required choice(s)")
            correct += task.task_type == 'quiz' and set(answer) == set(q['correct'])
        elif kind == 'rating':
            if type(answer) is not int or not 1 <= answer <= 5:
                raise HTTPException(422, "Rating must be between 1 and 5")
        elif not isinstance(answer, str) or not answer.strip() or len(answer) > (500 if kind == 'short_text' else 5000):
            raise HTTPException(422, "Provide a bounded text response")
    if task.task_type == 'survey':
        return {"passed": True, "attempt": attempt, "kind": "survey", "message": "Response recorded; no opinion is graded"}
    score = correct * 100 // len(questions)
    passed = correct >= (settings.get('minimum_correct') or len(questions)) if checkpoints else score >= settings['passing_score']
    return {"passed": passed, "score": score, "attempt": attempt,
            "kind": "checkpoints" if checkpoints else "quiz", "attempts_remaining": settings.get('max_attempts', 3) - attempt}
