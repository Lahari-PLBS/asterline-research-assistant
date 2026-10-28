# test_ollama.py - checks that Python can talk to Ollama and get a structured answer
from pydantic import BaseModel
from langchain_ollama import ChatOllama


class Answer(BaseModel):
    capital: str


# num_ctx = how much text the model can read at once. Ollama's default (2048) is too small for our prompts.
llm = ChatOllama(model='llama3.1:8b', temperature=0, num_ctx=8192)
print(llm.with_structured_output(Answer).invoke('What is the capital of France?'))
3. 