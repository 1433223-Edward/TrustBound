"""Vultr-only HTTP client with bounded requests and a credential-free call ledger."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
import socket
import time
from urllib import error, request

BASE_URL = "https://api.vultrinference.com/v1"
DEFAULT_MODEL = "deepseek-v4.1-flash-1017"


class InferenceError(Exception):
    """Only sanitized error codes may cross into application reports."""


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_json(method, path, payload, api_key, timeout):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = request.Request(BASE_URL + path, method=method, headers=headers,
                          data=json.dumps(payload).encode() if payload is not None else None)
    with request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise InferenceError("RESPONSE_TOO_LARGE")
        return json.loads(raw)


def select_model(catalog, requested=DEFAULT_MODEL):
    for model in catalog.get("data", []):
        if model.get("id") == requested:
            if "text" not in model.get("architecture", {}).get("output_modalities", []):
                raise InferenceError("MODEL_NOT_TEXT")
            return model
    raise InferenceError("MODEL_NOT_IN_LIVE_CATALOG")


def estimated_cost(usage, pricing):
    try:
        counts = [usage["prompt_tokens"], usage["completion_tokens"]]
        if any(type(count) is not int or count < 0 for count in counts):
            return None
        rates = [Decimal(pricing["prompt"]), Decimal(pricing["completion"])]
        if any(not rate.is_finite() or rate < 0 for rate in rates):
            return None
        return str(sum(count * rate for count, rate in zip(counts, rates)))
    except (KeyError, TypeError, InvalidOperation):
        return None


class VultrClient:
    def __init__(self, api_key=None, *, transport=http_json, timeout=30, max_attempts=2):
        self._key = api_key if api_key is not None else os.environ.get("VULTR_INFERENCE_API_KEY", "")
        if not 1 <= timeout <= 60 or not 1 <= max_attempts <= 2:
            raise ValueError("Invalid request budget")
        self.transport, self.timeout, self.max_attempts = transport, timeout, max_attempts
        self.source = "VULTR_LIVE_HTTP" if transport is http_json else "OFFLINE_TEST"
        self.calls = []

    @property
    def configured(self):
        return bool(self._key.strip())

    def catalog(self):
        try:
            return self.transport("GET", "/models?format=openrouter", None, "", self.timeout)
        except Exception:
            raise InferenceError("CATALOG_UNAVAILABLE") from None

    def complete(self, model, messages, max_tokens, *, json_mode=False):
        if not self.configured:
            raise InferenceError("MISSING_VULTR_INFERENCE_API_KEY")
        if not 1 <= max_tokens <= 1024 or len(json.dumps(messages)) > 12000:
            raise InferenceError("REQUEST_BUDGET_EXCEEDED")
        payload = {"model": model["id"], "messages": messages,
                   "max_completion_tokens": max_tokens, "temperature": 0}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        for attempt in range(1, self.max_attempts + 1):
            entry = {"attempt": attempt, "model": model["id"], "max_completion_tokens": max_tokens,
                     "started_at": datetime.now(timezone.utc).isoformat(),
                     "status": "PENDING", "usage": None, "estimated_usd": None,
                     "billing_status": "UNKNOWN"}
            self.calls.append(entry)
            try:
                response = self.transport("POST", "/chat/completions", payload,
                                          self._key, self.timeout)
            except error.HTTPError as exc:
                entry["status"] = f"HTTP_{exc.code}"
                # Only an explicit rate-limit rejection is retried. Timeouts/5xx may
                # already be billable, so retrying those could duplicate paid work.
                if exc.code == 429 and attempt < self.max_attempts:
                    time.sleep(0.2)
                    continue
                raise InferenceError(entry["status"]) from None
            except (TimeoutError, socket.timeout):
                entry["status"] = "TIMEOUT"
                raise InferenceError("TIMEOUT_BILLING_UNKNOWN") from None
            except error.URLError as exc:
                entry["status"] = "TIMEOUT" if isinstance(exc.reason, TimeoutError) else "API_FAILURE"
                raise InferenceError(entry["status"] + "_BILLING_UNKNOWN") from None
            except Exception:
                entry["status"] = "API_FAILURE"
                raise InferenceError("API_FAILURE_BILLING_UNKNOWN") from None
            try:
                usage = response.get("usage")
                entry["usage"] = {key: usage[key] for key in (
                    "prompt_tokens", "completion_tokens", "total_tokens")
                    if key in usage and type(usage[key]) is int} if isinstance(usage, dict) else None
                entry["estimated_usd"] = estimated_cost(entry["usage"], model.get("pricing", {}))
                entry["billing_status"] = "ESTIMATED" if entry["estimated_usd"] is not None else "UNKNOWN"
                choice = response["choices"][0]
                content = choice["message"]["content"]
                if (choice["finish_reason"] != "stop" or type(content) is not str
                        or not content or response.get("model") != model["id"]):
                    raise ValueError("Invalid response")
                entry["status"] = "COMPLETED"
                return content.replace(self._key, "[REDACTED]")
            except (KeyError, TypeError, IndexError, ValueError, AttributeError):
                entry["status"] = "INVALID_RESPONSE"
                raise InferenceError("INVALID_RESPONSE") from None
