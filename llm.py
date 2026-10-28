# llm.py - the only place that talks to the language model.
import os
from functools import lru_cache
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()  # reads the .env file so the API keys become environment variables


@lru_cache(maxsize=1)  # build the model object once and reuse it
def get_llm():
    provider = os.getenv('LLM_PROVIDER', 'gemini')
    model = os.getenv('LLM_MODEL', 'gemini-3.8-flash')

    # temperature=0 makes the answers as repeatable as possible
    if provider == 'gemini':
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, temperature=0)
    if provider == 'openai':
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0)
    if provider == 'anthropic':
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0)
    raise ValueError('Unknown LLM_PROVIDER: ' + provider)


# If the provider is busy (rate limit) or fails, wait and try again.
# Waits grow longer each time (about 4s, 8s, 16s, 32s). After 5 tries we give up.
@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=40), reraise=True)
def ask(schema, system_prompt, user_prompt):
    '''Ask the model and get back a filled-in `schema` object (a Pydantic class).'''
    model = get_llm().with_structured_output(schema)
    result = model.invoke([('system', system_prompt), ('human', user_prompt)])
    if result is None:  # sometimes the model returns nothing usable, so we treat it as an error and retry
        raise ValueError('The model returned an empty result')
    return result