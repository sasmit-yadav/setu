from __future__ import annotations

import importlib.util
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from services.api.settings import settings
from services.ml.flores import SOURCE_FLORES, flores_target, is_english

app = FastAPI(title="SETU ML", docs_url=None, redoc_url=None)
_CACHE: dict[str, Any] = {}

# IndicTrans2 generate bound from the model card, not a policy threshold.
_GENERATE_MAX_LENGTH = 256
_GENERATE_NUM_BEAMS = 5


class TranslateIn(BaseModel):
    text: str
    target_lang: str
    model: str = ""


class EmbedIn(BaseModel):
    texts: list[str]
    model: str = ""


def _authorized(x_internal_key: str | None) -> None:
    expected = settings.internal_ml_key.strip()
    if expected and x_internal_key != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _load_enabled() -> bool:
    return settings.setu_load_ml_models.strip() == "1"


def _translate_id() -> str:
    return settings.setu_translate_hf_id.strip()


def _embed_id() -> str:
    return settings.setu_embed_hf_id.strip()


def _translator():
    if "translator" in _CACHE:
        return _CACHE["translator"]
    name = _translate_id()
    if not _load_enabled() or not name or not _has_module("transformers"):
        _CACHE["translator"] = None
        return None
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(name, trust_remote_code=True)
    except (ImportError, OSError, RuntimeError, ValueError):
        _CACHE["translator"] = None
        return None
    _CACHE["translator"] = (tokenizer, model)
    return _CACHE["translator"]


def _processor():
    if "processor" in _CACHE:
        return _CACHE["processor"]
    if not _has_module("IndicTransToolkit"):
        _CACHE["processor"] = None
        return None
    try:
        from IndicTransToolkit.processor import IndicProcessor

        _CACHE["processor"] = IndicProcessor(inference=True)
    except (ImportError, OSError, RuntimeError, ValueError):
        _CACHE["processor"] = None
        return None
    return _CACHE["processor"]


def _embedder():
    if "embedder" in _CACHE:
        return _CACHE["embedder"]
    name = _embed_id()
    if not _load_enabled() or not name or not _has_module("sentence_transformers"):
        _CACHE["embedder"] = None
        return None
    try:
        from sentence_transformers import SentenceTransformer

        _CACHE["embedder"] = SentenceTransformer(name)
    except (ImportError, OSError, RuntimeError, ValueError):
        _CACHE["embedder"] = None
        return None
    return _CACHE["embedder"]


@app.get("/health")
def health() -> dict[str, bool | str]:
    translator = _CACHE.get("translator")
    embedder = _CACHE.get("embedder")
    return {
        "ok": True,
        "torch": _has_module("torch"),
        "toolkit": _has_module("IndicTransToolkit"),
        "translate": translator is not None,
        "embed": embedder is not None,
        "load_enabled": _load_enabled(),
        "translate_hf_id": _translate_id(),
        "embed_hf_id": _embed_id(),
        "isolation": "services.api never imports torch",
    }


@app.post("/translate")
def translate(
    body: TranslateIn,
    x_internal_key: str | None = Header(default=None),
) -> dict[str, str]:
    _authorized(x_internal_key)
    expected = _translate_id()
    if not expected:
        raise HTTPException(status_code=503, detail="models_absent")
    if body.model and body.model != expected:
        raise HTTPException(status_code=409, detail="model_mismatch")
    if is_english(body.target_lang):
        return {"text": body.text, "target_lang": body.target_lang, "model": expected}
    tgt = flores_target(body.target_lang)
    if tgt is None:
        raise HTTPException(status_code=400, detail="unsupported_target_lang")
    packed = _translator()
    if packed is None:
        raise HTTPException(status_code=503, detail="models_absent")
    processor = _processor()
    if processor is None:
        # Raw tokenizer output without IndicTransToolkit is not Malayalam /
        # Marathi — it is tagged subwords. Refusing is more honest than
        # caching that string as a "translation".
        raise HTTPException(status_code=503, detail="toolkit_absent")
    tokenizer, model = packed
    batch = processor.preprocess_batch(
        [body.text], src_lang=SOURCE_FLORES, tgt_lang=tgt
    )
    encoded = tokenizer(
        batch,
        truncation=True,
        padding="longest",
        return_tensors="pt",
    )
    generated = model.generate(
        **encoded,
        num_beams=_GENERATE_NUM_BEAMS,
        max_length=_GENERATE_MAX_LENGTH,
        num_return_sequences=1,
    )
    decoded = tokenizer.batch_decode(
        generated, skip_special_tokens=True, clean_up_tokenization_spaces=True
    )
    text = processor.postprocess_batch(decoded, lang=tgt)[0]
    return {"text": text, "target_lang": body.target_lang, "model": expected}


@app.post("/embed")
def embed(
    body: EmbedIn,
    x_internal_key: str | None = Header(default=None),
) -> dict[str, list[list[float]] | str]:
    _authorized(x_internal_key)
    expected = _embed_id()
    if not expected:
        raise HTTPException(status_code=503, detail="models_absent")
    if body.model and body.model != expected:
        raise HTTPException(status_code=409, detail="model_mismatch")
    model = _embedder()
    if model is None:
        raise HTTPException(status_code=503, detail="models_absent")
    vectors = model.encode(body.texts).tolist()
    return {"embeddings": vectors, "model": expected}
