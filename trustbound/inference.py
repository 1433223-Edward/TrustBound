"""Vultr-only HTTP client with bounded requests and a credential-free call ledger."""
from contextvars import ContextVar
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
import socket
import time
from urllib import error, request

from .admission import AdmissionError, reserve_live_attempt, model_request_transition
from .model_journal import JournalError
from .config import load_local_env

# Loaded once on backend import; fresh clients read the resulting process settings.
load_local_env()

BASE_URL = "https://api.vultrinference.com/v1"
DEFAULT_MODEL = "deepseek-v4.1-flash-1017"


class InferenceError(Exception):
    """Only sanitized error codes may cross into application reports."""


def _reserve_global_live_attempt(source, outputs):
    if source == "VULTR_LIVE_HTTP":
        try:
            reserve_live_attempt(outputs)
        except (AdmissionError, JournalError) as error:
            raise InferenceError(error.code if isinstance(error, AdmissionError) else str(error)) from None


# One task scope covers all fresh clients without sharing agent message contexts.
_TASK_BUDGET = ContextVar("trustbound_task_budget", default=None)

class TaskInferenceBudget:
    def __init__(self, max_requests=14, max_output_tokens=14336):
        if not 1 <= max_requests <= 14 or not 1 <= max_output_tokens <= 14336:
            raise ValueError("Invalid task inference budget")
        self.max_requests, self.max_output_tokens = max_requests, max_output_tokens
        self.calls, self.reserved_tokens = [], 0

    def reserve(self, entry, source):
        # Reserve before transport, including retries and failures; never refund an
        # ambiguous request whose provider-side billing is unknown.
        if len(self.calls) >= self.max_requests or self.reserved_tokens + entry["max_completion_tokens"] > self.max_output_tokens:
            raise InferenceError("TASK_INFERENCE_BUDGET_EXHAUSTED")
        _reserve_global_live_attempt(source, entry["max_completion_tokens"])
        self.reserved_tokens += entry["max_completion_tokens"]
        entry["source"] = source
        self.calls.append(entry)

    def to_dict(self):
        live = [c for c in self.calls if c["source"] == "VULTR_LIVE_HTTP"]
        def tokens(key):
            if not live or any(not c.get("usage") or type(c["usage"].get(key)) is not int for c in live):
                return None
            return sum(c["usage"][key] for c in live)
        costs = [c.get("estimated_usd") for c in live]
        return {"max_requests": self.max_requests, "max_output_tokens": self.max_output_tokens,
                "reserved_output_tokens": self.reserved_tokens, "request_count": len(self.calls),
                "live_request_count": len(live), "offline_request_count": len(self.calls)-len(live),
                "prompt_tokens": tokens("prompt_tokens"), "completion_tokens": tokens("completion_tokens"),
                "estimated_usd": str(sum(Decimal(c) for c in costs)) if costs and all(c is not None for c in costs) else None,
                "billing_status": "ESTIMATED_NOT_INVOICE" if costs and all(c is not None for c in costs) else "UNKNOWN",
                "calls": self.calls}

@contextmanager
def task_inference_budget(budget):
    token = _TASK_BUDGET.set(budget)
    try:
        yield budget
    finally:
        _TASK_BUDGET.reset(token)


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
    def __init__(self, api_key=None, *, transport=http_json, timeout=30, max_attempts=2, output_limit=1024, input_limit=12000):
        self._key = api_key if api_key is not None else os.environ.get("VULTR_INFERENCE_API_KEY", "")
        if not 1 <= timeout <= 60 or not 1 <= max_attempts <= 2:
            raise ValueError("Invalid request budget")
        if type(output_limit) is not int or not 1 <= output_limit <= 4096:
            raise ValueError("Invalid output token limit")
        self.output_limit = output_limit
        if type(input_limit) is not int or not 1 <= input_limit <= 48000:
            raise ValueError('Invalid input size limit')
        self.input_limit = input_limit
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

    def complete(self, model, messages, max_tokens, *, json_mode=False, reasoning_tokens=None, response_schema=None):
        if not self.configured:
            raise InferenceError("MISSING_VULTR_INFERENCE_API_KEY")
        if not 1 <= max_tokens <= self.output_limit or len(json.dumps(messages)) > self.input_limit:
            raise InferenceError("REQUEST_BUDGET_EXCEEDED")
        payload = {"model": model["id"], "messages": messages,
                   "max_completion_tokens": max_tokens, "temperature": 0}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if reasoning_tokens is not None:
            if (model.get("reasoning", {}).get("supports_max_tokens") is not True
                    or type(reasoning_tokens) is not int or not 1 <= reasoning_tokens < max_tokens):
                raise InferenceError("UNSUPPORTED_REASONING_BUDGET")
            payload["reasoning"] = {"max_tokens": reasoning_tokens}
        if response_schema is not None:
            if "structured_outputs" not in model.get("supported_parameters", []):
                raise InferenceError("UNSUPPORTED_STRUCTURED_OUTPUT")
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "adversarial_challenges", "strict": True, "schema": response_schema}}
        for attempt in range(1, self.max_attempts + 1):
            entry = {"attempt": attempt, "model": model["id"], "max_completion_tokens": max_tokens,
                     "started_at": datetime.now(timezone.utc).isoformat(),
                     "status": "PENDING", "usage": None, "estimated_usd": None,
                     "billing_status": "UNKNOWN"}
            if reasoning_tokens is not None:
                entry["reasoning_max_tokens"] = reasoning_tokens
            entry["response_format"] = payload.get("response_format", {}).get("type", "text")
            budget = _TASK_BUDGET.get()
            if budget is not None:
                budget.reserve(entry, self.source)
            else:
                _reserve_global_live_attempt(self.source, max_tokens)
            self.calls.append(entry)
            if self.source == "VULTR_LIVE_HTTP":
                model_request_transition("SENT", entry)
            try:
                response = self.transport("POST", "/chat/completions", payload,
                                          self._key, self.timeout)
            except error.HTTPError as exc:
                entry["status"] = f"HTTP_{exc.code}"
                if self.source == "VULTR_LIVE_HTTP":
                    model_request_transition("UNKNOWN_BILLING", entry)
                # Only an explicit rate-limit rejection is retried. Timeouts/5xx may
                # already be billable, so retrying those could duplicate paid work.
                if exc.code == 429 and attempt < self.max_attempts:
                    time.sleep(0.2)
                    continue
                raise InferenceError(entry["status"]) from None
            except (TimeoutError, socket.timeout):
                entry["status"] = "TIMEOUT"
                if self.source == "VULTR_LIVE_HTTP":
                    model_request_transition("UNKNOWN_BILLING", entry)
                raise InferenceError("TIMEOUT_BILLING_UNKNOWN") from None
            except error.URLError as exc:
                entry["status"] = "TIMEOUT" if isinstance(exc.reason, TimeoutError) else "API_FAILURE"
                if self.source == "VULTR_LIVE_HTTP":
                    model_request_transition("UNKNOWN_BILLING", entry)
                raise InferenceError(entry["status"] + "_BILLING_UNKNOWN") from None
            except Exception:
                entry["status"] = "API_FAILURE"
                if self.source == "VULTR_LIVE_HTTP":
                    model_request_transition("UNKNOWN_BILLING", entry)
                raise InferenceError("API_FAILURE_BILLING_UNKNOWN") from None
            if self.source == "VULTR_LIVE_HTTP":
                model_request_transition("RESPONSE_RECEIVED", entry)
            try:
                usage = response.get("usage")
                entry["usage"] = {key: usage[key] for key in (
                    "prompt_tokens", "completion_tokens", "total_tokens")
                    if key in usage and type(usage[key]) is int} if isinstance(usage, dict) else None
                entry["estimated_usd"] = estimated_cost(entry["usage"], model.get("pricing", {}))
                entry["billing_status"] = "ESTIMATED" if entry["estimated_usd"] is not None else "UNKNOWN"
                # Retain numerical diagnostics only; never read or persist reasoning text.
                details = usage.get("completion_tokens_details", {}) if isinstance(usage, dict) else {}
                reasoning_count = details.get("reasoning_tokens") if isinstance(details, dict) else None
                entry["reasoning_tokens"] = reasoning_count if type(reasoning_count) is int and reasoning_count >= 0 else None
                choice = response["choices"][0]
                # Keep provider identity and termination metadata even on rejection.
                entry["response_model"] = str(response.get("model", ""))[:200].replace(self._key, "[REDACTED]")
                entry["provider_request_id"] = str(response.get("id", ""))[:200].replace(self._key, "[REDACTED]")
                entry["finish_reason"] = str(choice.get("finish_reason", ""))[:80].replace(self._key, "[REDACTED]")
                content = choice["message"].get("content")
                entry["content_is_string"] = type(content) is str
                entry["content_chars"] = len(content) if type(content) is str else None
                if (choice["finish_reason"] != "stop" or type(content) is not str
                        or not content or response.get("model") != model["id"]):
                    raise ValueError("Invalid response")
                entry["status"] = "COMPLETED"
                if self.source == "VULTR_LIVE_HTTP":
                    model_request_transition("RESPONSE_RECEIVED", entry)
                return content.replace(self._key, "[REDACTED]")
            except (KeyError, TypeError, IndexError, ValueError, AttributeError):
                entry["status"] = "INVALID_RESPONSE"
                if self.source == "VULTR_LIVE_HTTP":
                    model_request_transition("RESPONSE_RECEIVED", entry)
                raise InferenceError("INVALID_RESPONSE") from None
