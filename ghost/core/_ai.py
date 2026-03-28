"""Shared AI call helper - Anthropic primary, OpenRouter, OpenAI fallback.

Priority chain: Anthropic -> OpenRouter -> OpenAI.
All calls use streaming disabled + tight timeouts for speed.
"""

import ghost.config as cfg

# Latest model IDs for OpenRouter (March 2026)
OPENROUTER_MODEL_MAP = {
    # Anthropic
    "claude-sonnet": "anthropic/claude-sonnet-4.6",
    "claude-opus": "anthropic/claude-opus-4.6",
    "claude-haiku": "anthropic/claude-haiku-4.5",
    # OpenAI
    "gpt-5.4": "openai/gpt-5.4",
    "gpt-5.4-mini": "openai/gpt-5.4-mini",
    "gpt-5.3": "openai/gpt-5.3-codex",
    "gpt-5.2": "openai/gpt-5.2",
    "gpt-4o": "openai/gpt-4o",
    # Google
    "gemini-pro": "google/gemini-3.1-pro",
    "gemini-flash": "google/gemini-3.1-flash-lite",
    # DeepSeek
    "deepseek": "deepseek/deepseek-v3.2",
    "deepseek-v3": "deepseek/deepseek-v3.2",
    # Meta
    "llama": "meta-llama/llama-4-maverick",
    "llama-4": "meta-llama/llama-4-maverick",
    "llama-scout": "meta-llama/llama-4-scout",
}

# Timeout for AI calls (seconds) - keep things snappy
_HTTP_TIMEOUT = 120.0


def ai_call(system: str, user: str, model: str = "") -> str:
    """Call AI with system + user prompt. Returns text response."""
    model = model or cfg.DEFAULT_MODEL
    _last_error = ""

    # Try Anthropic first (direct API, lowest latency)
    if cfg.ANTHROPIC_API_KEY:
        try:
            return _call_anthropic(system, user, model)
        except Exception as e:
            _last_error = f"Anthropic: {e}"
            if not cfg.OPENROUTER_API_KEY and not cfg.OPENAI_API_KEY:
                raise RuntimeError(f"Anthropic API failed: {e}")
    else:
        _last_error = "No Anthropic key"

    # Try OpenRouter second (access to any model)
    if cfg.OPENROUTER_API_KEY:
        try:
            return _call_openrouter(system, user, model)
        except Exception as e:
            _last_error = f"OpenRouter: {e}"
            if not cfg.OPENAI_API_KEY:
                raise RuntimeError(f"OpenRouter API failed: {e}")

    # Fallback to OpenAI
    if cfg.OPENAI_API_KEY:
        return _call_openai(system, user, model)

    raise RuntimeError(
        f"All AI providers failed. Last error: {_last_error}\n"
        "Set ANTHROPIC_API_KEY, OPENROUTER_API_KEY, or OPENAI_API_KEY."
    )


def _call_anthropic(system: str, user: str, model: str) -> str:
    import anthropic

    client = anthropic.Anthropic(
        api_key=cfg.ANTHROPIC_API_KEY,
        base_url="https://api.anthropic.com",  # Force direct - bypass any local proxy
        timeout=_HTTP_TIMEOUT,
    )
    # Resolve model name - latest Anthropic API IDs
    api_model = model
    if "sonnet" in model and "/" not in model and "4" not in model:
        api_model = "claude-sonnet-4-6"
    elif "opus" in model and "/" not in model and "4" not in model:
        api_model = "claude-opus-4-6"
    elif "haiku" in model and "/" not in model and "4" not in model:
        api_model = "claude-haiku-4-5"

    response = client.messages.create(
        model=api_model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _call_openrouter(system: str, user: str, model: str) -> str:
    """Call OpenRouter API - OpenAI-compatible endpoint, any model."""
    from openai import OpenAI

    client = OpenAI(
        api_key=cfg.OPENROUTER_API_KEY,
        base_url=cfg.OPENROUTER_BASE_URL,
        timeout=_HTTP_TIMEOUT,
    )

    api_model = _resolve_openrouter_model(model)

    response = client.chat.completions.create(
        model=api_model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        extra_headers={
            "HTTP-Referer": "https://github.com/ghost-dev/ghost-dev",
            "X-Title": "ghost.dev",
        },
    )
    return response.choices[0].message.content or ""


def _call_openai(system: str, user: str, model: str) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=cfg.OPENAI_API_KEY,
        timeout=_HTTP_TIMEOUT,
    )
    # Map to latest OpenAI model if user passed a Claude name
    if "claude" in model.lower() or "sonnet" in model.lower():
        api_model = "gpt-5.4"
    elif "gpt" in model.lower():
        api_model = model
    else:
        api_model = "gpt-5.4"

    response = client.chat.completions.create(
        model=api_model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


def _resolve_openrouter_model(model: str) -> str:
    """Resolve a friendly model name to an OpenRouter model ID."""
    # Already a full OpenRouter model ID (contains /)
    if "/" in model:
        return model

    # Check our shorthand map (case-insensitive partial match)
    model_lower = model.lower()
    for key, value in OPENROUTER_MODEL_MAP.items():
        if key in model_lower:
            return value

    # Default: prefix with anthropic/ for claude models
    if "claude" in model_lower:
        return f"anthropic/{model}"

    return model
