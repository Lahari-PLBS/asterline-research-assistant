# llm.py - the only place that talks to the language model.
# It tries the main model first. If that fails, it uses the fallback model.
import os
import time
from functools import lru_cache
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

# After the main model fails, we skip it until this time (so we do not wait through retries on every call)
main_blocked_until = 0


@lru_cache(maxsize=4)   # build each model object once and reuse it
def get_llm(provider, model):
    if provider == 'gemini':
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, temperature=0)
    if provider == 'ollama':
        from langchain_ollama import ChatOllama
        # num_ctx = how much text the model can read at once (the default is too small for our prompts)
        # return ChatOllama(model=model, temperature=0, num_ctx=8192)
        return ChatOllama(model=model, temperature=0, num_ctx=8192, client_kwargs={'timeout': 300})
    if provider == 'openai':
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0)
    if provider == 'anthropic':
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0)
    raise ValueError('Unknown provider: ' + provider)


# Wait and retry a few times (about 4s, 8s) before giving up on one model
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30), reraise=True)
def ask_with(provider, model, schema, system_prompt, user_prompt):
    llm = get_llm(provider, model).with_structured_output(schema)
    result = llm.invoke([('system', system_prompt), ('human', user_prompt)])
    if result is None:   # the model returned nothing usable, so retry
        raise ValueError('The model returned an empty result')
    return result


def ask(schema, system_prompt, user_prompt):
    '''Ask the model and get back a filled-in `schema` object (a Pydantic class).'''
    global main_blocked_until
    main_provider = os.getenv('LLM_PROVIDER', 'gemini')
    main_model = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    fallback_provider = os.getenv('FALLBACK_PROVIDER')
    fallback_model = os.getenv('FALLBACK_MODEL')

    # Try the main model, unless it failed very recently
    if time.time() >= main_blocked_until:
        try:
            return ask_with(main_provider, main_model, schema, system_prompt, user_prompt)
        except Exception:
            if not fallback_provider:
                raise   # no backup configured, so report the error
            print('Main model failed. Using fallback:', fallback_provider, fallback_model)
            main_blocked_until = time.time() + 300   # skip the main model for 5 minutes

    return ask_with(fallback_provider, fallback_model, schema, system_prompt, user_prompt)