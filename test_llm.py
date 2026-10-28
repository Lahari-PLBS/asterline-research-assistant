# test_llm.py - quick check that the model and the keys work
from pydantic import BaseModel
from llm import ask


class Answer(BaseModel):
    capital: str


print(ask(Answer, 'Answer briefly.', 'What is the capital of France?'))