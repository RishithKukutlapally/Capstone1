from langchain_google_genai import ChatGoogleGenerativeAI

from .config import get_api_key, get_config

def build_llm(model_name=None):
    cfg = get_config()
    return ChatGoogleGenerativeAI(
        model=model_name or cfg.llm.primary_model,
        temperature=cfg.llm.temperature,
        max_output_tokens=cfg.llm.max_output_tokens,
        timeout=cfg.llm.request_timeout_seconds,
        google_api_key=get_api_key(),
    )

def build_structured_llm(schema, model_name=None):
    cfg = get_config()
    # structured output first: with_retry returns a runnable that no longer has it
    return build_llm(model_name).with_structured_output(schema).with_retry(
        stop_after_attempt=cfg.llm.max_retries,
        wait_exponential_jitter=True,
    )

def check_quota(model_name=None):
    cfg = get_config()
    model_name = model_name or cfg.llm.primary_model
    try:
        build_llm(model_name).invoke("Reply with the single word: ok")
        return True, f"{model_name} is reachable"
    except Exception as exc:
        detail = str(exc)
        if "429" in detail or "RESOURCE_EXHAUSTED" in detail:
            return False, f"{model_name} is out of quota or credit: {detail[:160]}"
        if "404" in detail:
            return False, f"{model_name} was not found - check the name in config/config.yaml"
        return False, f"{model_name} is not reachable: {type(exc).__name__}: {detail[:160]}"
