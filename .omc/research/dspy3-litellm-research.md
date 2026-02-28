# DSPy 3.x, LiteLLM, MIPROv2, and uv Research

**Research date:** 2026-02-28
**Purpose:** Implementation reference for english-inspector backend using DSPy + LiteLLM

---

## 1. DSPy 3.x — Latest Stable Version

### Version
- **Latest stable:** `3.1.3` (released 2026-02-05)
- **PyPI package name:** `dspy` (install as `pip install dspy`)
  - Note: `dspy-ai` is a legacy package name; prefer `dspy`
- **Python requirement:** Python 3.10–3.14
- **License:** MIT
- **Source:** https://pypi.org/project/dspy/

### Installation

```bash
pip install dspy
# or with uv:
uv add dspy
```

For optional Anthropic extras:
```bash
pip install 'dspy[anthropic]'
```

---

## 2. DSPy 3.x — Core API Reference

### 2.1 Import Pattern

```python
import dspy

# All core classes are available from the top-level dspy namespace:
# dspy.Signature, dspy.Module, dspy.Predict, dspy.ChainOfThought
# dspy.ReAct, dspy.LM, dspy.configure, dspy.Example
# dspy.MIPROv2, dspy.evaluate
```

**Source:** https://dspy.ai/

### 2.2 LM Configuration

`dspy.LM` wraps LiteLLM internally. The model string follows the LiteLLM `provider/model-name` convention.

```python
import dspy

# Configure with OpenAI
lm = dspy.LM("openai/gpt-4o", api_key="sk-...")
dspy.configure(lm=lm)

# Configure with Anthropic
lm = dspy.LM("anthropic/claude-3-5-sonnet-20240620", api_key="sk-ant-...")
dspy.configure(lm=lm)

# Configure with Google Gemini
lm = dspy.LM("gemini/gemini-2.5-pro-preview-03-25", api_key="AIza...")
dspy.configure(lm=lm)

# Configure via environment variables (preferred for production)
import os
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
lm = dspy.LM("anthropic/claude-3-5-sonnet-20240620")
dspy.configure(lm=lm)

# With extra parameters
lm = dspy.LM(
    model="openai/gpt-4o",
    temperature=0.7,
    max_tokens=4096,
    cache=True,          # default True — caches responses
    num_retries=3,       # default 3 — exponential backoff
)
dspy.configure(lm=lm)
```

#### `dspy.LM` Constructor Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `model` | `str` | required | `"provider/model-name"` format via LiteLLM |
| `model_type` | `'chat' \| 'text' \| 'responses'` | `'chat'` | Completion style |
| `temperature` | `float \| None` | `None` | Sampling temperature |
| `max_tokens` | `int \| None` | `None` | Max tokens per response |
| `cache` | `bool` | `True` | Response caching |
| `callbacks` | `list[BaseCallback] \| None` | `None` | Pre/post request hooks |
| `num_retries` | `int` | `3` | Retry attempts with exponential backoff |
| `api_key` | `str` | `None` | API key (prefer env vars) |

**Important:** For OpenAI reasoning models (`o1`, `o3`, `o4`, `gpt-5` families), DSPy enforces `temperature=1.0` or `None` and `max_tokens >= 16000` or `None`. Violations raise `ValueError`.

**Source:** https://dspy.ai/api/models/LM/

### 2.3 Signature

Signatures define the input/output contract for a DSPy module. Two styles are supported.

#### String Signature (inline)

```python
# Single input -> single output
predictor = dspy.Predict("question -> answer")

# Multiple inputs -> multiple outputs
predictor = dspy.Predict("context, question -> answer, confidence")

# With type annotations in string form
predictor = dspy.Predict("sentence -> sentiment: str")
predictor = dspy.Predict("question -> answer: float")
```

#### Class-based Signature (recommended for complex cases)

```python
class GrammarCheck(dspy.Signature):
    """Check English grammar and return corrected text with explanations."""

    text: str = dspy.InputField(desc="The English text to check")
    context: str = dspy.InputField(desc="Optional context", default="")

    corrected_text: str = dspy.OutputField(desc="Grammatically corrected version")
    errors: list[str] = dspy.OutputField(desc="List of grammar errors found")
    explanation: str = dspy.OutputField(desc="Explanation of corrections made")
```

**Source:** https://dspy.ai/

### 2.4 Module

All DSPy programs inherit from `dspy.Module`. The `forward()` method defines the computation.

```python
class EnglishInspector(dspy.Module):
    def __init__(self):
        super().__init__()
        # Declare sub-modules as instance attributes
        self.analyze = dspy.ChainOfThought(GrammarCheck)
        self.score = dspy.Predict("text, errors -> score: float, feedback: str")

    def forward(self, text: str, context: str = "") -> dspy.Prediction:
        analysis = self.analyze(text=text, context=context)
        scored = self.score(text=text, errors=analysis.errors)
        return dspy.Prediction(
            corrected_text=analysis.corrected_text,
            errors=analysis.errors,
            explanation=analysis.explanation,
            score=scored.score,
            feedback=scored.feedback,
        )
```

**Source:** https://dspy.ai/

### 2.5 Predict

`dspy.Predict` is the base inference module — it invokes the LM once with the signature, without chain-of-thought reasoning.

```python
# Using string signature
classifier = dspy.Predict("sentence -> sentiment: str")
result = classifier(sentence="The weather is lovely today.")
print(result.sentiment)  # e.g. "positive"

# Using class signature
checker = dspy.Predict(GrammarCheck)
result = checker(text="She go to school every day.", context="")
print(result.corrected_text)
print(result.errors)
```

**Source:** https://dspy.ai/

### 2.6 ChainOfThought

`dspy.ChainOfThought` extends `Predict` by injecting a `reasoning` field before the output fields. This forces the LM to reason step-by-step before answering.

```python
# String signature
reasoner = dspy.ChainOfThought("question -> answer: float")
pred = reasoner(question="What is 15% of 240?")
print(pred.reasoning)   # "15% of 240 = 0.15 * 240 = 36"
print(pred.answer)      # 36.0

# Class signature
checker = dspy.ChainOfThought(GrammarCheck)
result = checker(text="He don't like coffee.", context="")
print(result.reasoning)       # step-by-step grammar analysis
print(result.corrected_text)  # "He doesn't like coffee."
print(result.errors)          # ["Subject-verb agreement: 'don't' -> 'doesn't'"]
```

**Source:** https://dspy.ai/

---

## 3. DSPy + LiteLLM Integration

DSPy calls LiteLLM internally for all LM requests. You do **not** need to import or configure LiteLLM separately — just pass the `provider/model-name` string to `dspy.LM`.

```python
import dspy
import os

# Set API keys via environment (recommended)
os.environ["OPENAI_API_KEY"] = "sk-..."
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
os.environ["GEMINI_API_KEY"] = "AIza..."

# DSPy uses LiteLLM internally -- just pass provider/model string
lm = dspy.LM("anthropic/claude-3-5-sonnet-20240620")
dspy.configure(lm=lm)

# To use a different LM for a specific module call:
with dspy.context(lm=dspy.LM("openai/gpt-4o-mini")):
    result = my_module(text="hello")
```

### Using Multiple LMs (prompt model vs task model)

```python
# For MIPROv2: use a powerful model for prompt generation,
# cheaper model for the actual task
prompt_lm = dspy.LM("openai/gpt-4o")
task_lm = dspy.LM("openai/gpt-4o-mini")

optimizer = dspy.MIPROv2(
    metric=my_metric,
    prompt_model=prompt_lm,  # used to generate instruction candidates
    task_model=task_lm,      # used to run the student program
    auto="medium",
)
```

**Source:** https://dspy.ai/learn/programming/language_models/

---

## 4. LiteLLM

### Version
- **Latest stable:** `1.81.16` (released 2026-02-26)
- **PyPI:** https://pypi.org/project/litellm/
- **Python requirement:** Python 3.9–3.13
- **License:** MIT

### Installation

```bash
pip install litellm
# or with uv:
uv add litellm
```

### Model Name Format

LiteLLM uses `provider/model-name` strings. The provider prefix routes the request to the correct API.

```python
from litellm import completion

# OpenAI
response = completion(model="openai/gpt-4o", messages=[...])
response = completion(model="openai/gpt-4o-mini", messages=[...])
response = completion(model="openai/o3-mini", messages=[...])

# Anthropic
response = completion(model="anthropic/claude-3-5-sonnet-20240620", messages=[...])
response = completion(model="anthropic/claude-3-opus-20240229", messages=[...])
response = completion(model="anthropic/claude-3-haiku-20240307", messages=[...])

# Google Gemini
response = completion(model="gemini/gemini-2.5-flash", messages=[...])
response = completion(model="gemini/gemini-2.5-pro-preview-03-25", messages=[...])

# Google Vertex AI
response = completion(model="vertex_ai/gemini-1.5-pro", messages=[...])
```

### API Key Configuration

```python
import os

# Per-provider environment variables
os.environ["OPENAI_API_KEY"] = "sk-..."
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
os.environ["GEMINI_API_KEY"] = "AIza..."

# Or pass directly to completion()
response = completion(
    model="anthropic/claude-3-5-sonnet-20240620",
    api_key="sk-ant-...",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Supported Model Name Strings (Key Models)

#### OpenAI
| Model | String |
|---|---|
| GPT-4o | `openai/gpt-4o` |
| GPT-4o mini | `openai/gpt-4o-mini` |
| o3-mini | `openai/o3-mini` |
| o3 | `openai/o3` |
| GPT-4 Turbo | `openai/gpt-4-turbo` |

#### Anthropic Claude
| Model | String |
|---|---|
| Claude 3.5 Sonnet | `anthropic/claude-3-5-sonnet-20240620` |
| Claude 3.7 Sonnet | `anthropic/claude-3-7-sonnet-20250219` |
| Claude 3 Haiku | `anthropic/claude-3-haiku-20240307` |
| Claude 3 Opus | `anthropic/claude-3-opus-20240229` |
| Claude Sonnet 4 | `anthropic/claude-sonnet-4-20250514` |
| Claude Opus 4 | `anthropic/claude-opus-4-20250514` |
| Claude Sonnet 4.5 | `anthropic/claude-sonnet-4-5-20250929` |

#### Google
| Model | String |
|---|---|
| Gemini 2.5 Flash | `gemini/gemini-2.5-flash` |
| Gemini 2.5 Pro | `gemini/gemini-2.5-pro-preview-03-25` |
| Vertex Gemini 1.5 Pro | `vertex_ai/gemini-1.5-pro` |

**Sources:**
- https://docs.litellm.ai/docs/providers/anthropic
- https://docs.litellm.ai/docs/providers/openai
- https://docs.litellm.ai/docs/providers

---

## 5. MIPROv2 Optimizer

MIPROv2 (Multiprompt Instruction PRoposal Optimizer v2) jointly optimizes both **instructions** and **few-shot examples** for each predictor in a DSPy program using Bayesian Optimization.

### How It Works

1. **Bootstrap stage:** Samples examples from `trainset`, runs your program, keeps traces where output scores well on the metric.
2. **Proposal stage:** Uses a `prompt_model` to generate instruction candidates, informed by the data, code, and bootstrapped traces.
3. **Search stage:** Runs Bayesian Optimization (`num_trials` trials) to find the best combination of instructions + few-shot examples across all predictors.

**Source:** https://dspy.ai/api/optimizers/MIPROv2/

### Constructor API

```python
optimizer = dspy.MIPROv2(
    metric=my_metric_fn,           # required: callable(example, prediction, trace=None) -> float
    prompt_model=None,             # LM for generating instruction candidates (defaults to configured LM)
    task_model=None,               # LM for running the student program (defaults to configured LM)
    teacher_settings=None,         # dict of settings for the teacher program
    max_bootstrapped_demos=4,      # max few-shot examples generated from training data
    max_labeled_demos=4,           # max labeled examples included in candidates
    auto="light",                  # "light" | "medium" | "heavy" | None
    num_candidates=None,           # number of instruction candidates per predictor (set when auto=None)
    num_threads=None,              # parallelism for evaluation
    max_errors=None,               # max errors before aborting
    seed=9,                        # random seed for reproducibility
    init_temperature=1.0,          # temperature for instruction generation
    verbose=False,
    track_stats=True,
    log_dir=None,                  # path to save optimization logs
    metric_threshold=None,         # minimum metric score to accept a candidate
)
```

### compile() API

```python
optimized_program = optimizer.compile(
    student=my_module,             # the DSPy module to optimize
    trainset=train_examples,       # list of dspy.Example objects
    teacher=None,                  # optional teacher program (defaults to student)
    valset=None,                   # validation set (defaults to 20% of trainset)
    num_trials=None,               # number of Bayesian optimization trials (set by auto if None)
    max_bootstrapped_demos=None,   # override constructor setting
    max_labeled_demos=None,        # override constructor setting
    seed=None,                     # override constructor seed
    minibatch=True,                # use minibatches during trial evaluation
    minibatch_size=35,             # size of each minibatch
    minibatch_full_eval_steps=5,   # evaluate full valset every N steps
    program_aware_proposer=True,   # use program code when generating instructions
    data_aware_proposer=True,      # use data analysis when generating instructions
    view_data_batch_size=10,       # examples shown to proposer during data analysis
    tip_aware_proposer=True,       # use random tips for instruction diversity
    fewshot_aware_proposer=True,   # use bootstrapped examples when proposing
    provide_traceback=None,        # include error tracebacks in proposer context
)
```

### auto Parameter Guide

| Value | Use case | Approx. budget |
|---|---|---|
| `"light"` | Quick iteration, small datasets | ~few dozen trials |
| `"medium"` | Balanced quality/cost | ~100 trials |
| `"heavy"` | Maximum quality | ~200+ trials |
| `None` | Manual control via `num_trials` + `num_candidates` | Custom |

### Dataset Size Recommendations

| Dataset size | Recommended optimizer |
|---|---|
| ~10 examples | `BootstrapFewShot` |
| 50+ examples | `BootstrapFewShotWithRandomSearch` |
| 200+ examples | `MIPROv2` (full power) |
| Any size, 0-shot only | `MIPROv2` with `max_bootstrapped_demos=0, max_labeled_demos=0` |

### Creating a Training Set

```python
import dspy

# dspy.Example accepts keyword arguments; .with_inputs() marks which fields are inputs
# (as opposed to output/label fields)
trainset = [
    dspy.Example(
        text="She go to school every day.",
        corrected_text="She goes to school every day.",
        errors=["Subject-verb agreement: 'go' -> 'goes'"],
    ).with_inputs("text"),
    dspy.Example(
        text="I has a cat.",
        corrected_text="I have a cat.",
        errors=["Subject-verb agreement: 'has' -> 'have'"],
    ).with_inputs("text"),
    # ... more examples
]

# Simple question/answer format
trainset = [
    dspy.Example(question="What is 2+2?", answer="4").with_inputs("question"),
    dspy.Example(question="Capital of France?", answer="Paris").with_inputs("question"),
]

# With hints (supervised learning with extra context)
trainset = [
    dspy.Example(text=item["text"], hint=item["hint"]).with_inputs("text", "hint")
    for item in raw_data
]
```

### Metric Function Format

```python
def my_metric(example: dspy.Example, prediction: dspy.Prediction, trace=None) -> float:
    """
    Args:
        example: ground truth from trainset
        prediction: output from the DSPy module forward() call
        trace: internal DSPy trace (used by optimizers; None during plain evaluation)
    Returns:
        float score (higher = better); commonly 0.0 or 1.0 for binary metrics
    """
    # Binary exact match
    if prediction.corrected_text.strip().lower() == example.corrected_text.strip().lower():
        return 1.0
    # Partial credit: overlap of detected errors
    expected_errors = set(example.errors)
    predicted_errors = set(prediction.errors) if prediction.errors else set()
    overlap = len(expected_errors & predicted_errors)
    return overlap / max(len(expected_errors), 1)

# Built-in metric: exact match on answer field
from dspy.evaluate import answer_exact_match
# answer_exact_match(example, prediction, trace=None) -> bool
```

### Alternative Import for MIPROv2

```python
# Top-level (preferred in DSPy 3.x)
import dspy
optimizer = dspy.MIPROv2(metric=..., auto="medium")

# Legacy / explicit import also works
from dspy.teleprompt import MIPROv2
optimizer = MIPROv2(metric=..., auto="medium")
```

### Complete End-to-End MIPROv2 Example

```python
import dspy
import os

# 1. Configure LMs
os.environ["OPENAI_API_KEY"] = "sk-..."
task_lm = dspy.LM("openai/gpt-4o-mini")
prompt_lm = dspy.LM("openai/gpt-4o")
dspy.configure(lm=task_lm)

# 2. Define Signature
class GrammarCorrector(dspy.Signature):
    """Correct English grammar errors in the given text."""
    text: str = dspy.InputField(desc="Text with possible grammar errors")
    corrected_text: str = dspy.OutputField(desc="Grammatically correct version")
    errors_found: list[str] = dspy.OutputField(desc="List of errors identified")

# 3. Define Module
class GrammarModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.correct = dspy.ChainOfThought(GrammarCorrector)

    def forward(self, text: str):
        return self.correct(text=text)

# 4. Build training set (minimum ~20 examples; 200+ for best MIPROv2 results)
raw_data = [
    {"text": "She go to school.", "corrected_text": "She goes to school.", "errors_found": ["subject-verb agreement"]},
    {"text": "I has a cat.", "corrected_text": "I have a cat.", "errors_found": ["subject-verb agreement"]},
    {"text": "He don't like it.", "corrected_text": "He doesn't like it.", "errors_found": ["subject-verb agreement"]},
    # ... more examples
]
trainset = [
    dspy.Example(**d).with_inputs("text")
    for d in raw_data
]

# 5. Define metric
def grammar_metric(example, prediction, trace=None):
    correct = prediction.corrected_text.strip().lower() == example.corrected_text.strip().lower()
    return 1.0 if correct else 0.0

# 6. Run MIPROv2 optimization
optimizer = dspy.MIPROv2(
    metric=grammar_metric,
    prompt_model=prompt_lm,
    task_model=task_lm,
    auto="medium",
    num_threads=8,
    seed=42,
)

program = GrammarModule()
optimized_program = optimizer.compile(
    student=program,
    trainset=trainset,
    minibatch=True,
    minibatch_size=25,
)

# 7. Save and load the optimized program
optimized_program.save("grammar_optimizer_v1.json")

loaded_program = GrammarModule()
loaded_program.load("grammar_optimizer_v1.json")

# 8. Use the optimized program
result = optimized_program(text="She go to school every day.")
print(result.corrected_text)   # "She goes to school every day."
print(result.errors_found)     # ["subject-verb agreement: 'go' -> 'goes'"]
```

**Sources:**
- https://dspy.ai/api/optimizers/MIPROv2/
- https://dspy.ai/learn/optimization/optimizers/
- https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/MIPROv2.md

---

## 6. uv Package Manager

### Overview
- Written in Rust; drop-in replacement for pip + venv + pip-tools
- **Docs:** https://docs.astral.sh/uv/
- **GitHub:** https://github.com/astral-sh/uv

### Installation (if not already present)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv

# Verify
uv --version
```

### Key Commands

#### Project Initialization

```bash
# Create a new project
uv init my-project
cd my-project

# Or initialize in an existing directory
cd existing-project
uv init
```

Creates: `.gitignore`, `.python-version`, `README.md`, `main.py`, `pyproject.toml`, `.venv/`, `uv.lock`

#### Adding Dependencies

```bash
# Add a package (updates pyproject.toml + uv.lock + installs into .venv)
uv add dspy
uv add litellm
uv add dspy litellm python-dotenv   # multiple at once

# With version constraint
uv add 'dspy>=3.1.0'
uv add 'litellm>=1.80.0'

# From git
uv add git+https://github.com/stanfordnlp/dspy.git

# Dev dependency
uv add --dev pytest ruff mypy

# Migrate from requirements.txt
uv add -r requirements.txt
```

#### Virtual Environment

```bash
# uv auto-creates .venv on first `uv add` or `uv sync`
# To create explicitly:
uv venv

# With specific Python version:
uv venv --python 3.11
uv venv --python 3.12
```

#### Running Scripts

```bash
# Run a Python script (auto-syncs environment first)
uv run main.py
uv run python -c "import dspy; print(dspy.__version__)"

# Run a tool
uv run pytest
uv run ruff check .

# Run any command in the project environment
uv run -- python scripts/train.py
```

#### Syncing and Locking

```bash
# Sync environment to match lockfile (installs all deps)
uv sync

# Update lockfile without installing
uv lock

# Update a specific package to latest
uv lock --upgrade-package dspy
```

#### pyproject.toml Format (uv projects)

```toml
[project]
name = "english-inspector-backend"
version = "0.1.0"
description = "English grammar inspection using DSPy + LiteLLM"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "dspy>=3.1.3",
    "litellm>=1.81.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.3.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Sources:**
- https://docs.astral.sh/uv/
- https://docs.astral.sh/uv/guides/projects/
- https://docs.astral.sh/uv/reference/cli/

---

## 7. Quick-Start: english-inspector Backend

Full wiring example combining all of the above:

```python
# backend/src/inspector.py
import os
import dspy
from dotenv import load_dotenv

load_dotenv()

# LM Configuration
# DSPy uses LiteLLM internally; set API keys via env vars
lm = dspy.LM(
    model="anthropic/claude-3-5-sonnet-20240620",
    temperature=0.3,
    max_tokens=2048,
    cache=True,
)
dspy.configure(lm=lm)


# Signature
class InspectEnglish(dspy.Signature):
    """Analyze English text for grammar, spelling, and style errors."""

    text: str = dspy.InputField(desc="English text to inspect")
    level: str = dspy.InputField(
        desc="Learner level: beginner | intermediate | advanced",
        default="intermediate",
    )

    corrected_text: str = dspy.OutputField(desc="Corrected version of the text")
    errors: list[str] = dspy.OutputField(
        desc="List of errors in 'type: original -> corrected' format"
    )
    explanation: str = dspy.OutputField(
        desc="Clear explanation of all corrections for the learner"
    )
    score: float = dspy.OutputField(desc="Grammar score from 0.0 (worst) to 1.0 (perfect)")


# Module
class EnglishInspector(dspy.Module):
    def __init__(self):
        super().__init__()
        self.inspect = dspy.ChainOfThought(InspectEnglish)

    def forward(self, text: str, level: str = "intermediate") -> dspy.Prediction:
        return self.inspect(text=text, level=level)


# Metric (for MIPROv2 optimization)
def inspection_metric(example: dspy.Example, prediction: dspy.Prediction, trace=None) -> float:
    """Score how well the prediction matches ground truth."""
    score = 0.0
    if hasattr(example, "corrected_text") and example.corrected_text:
        if prediction.corrected_text.strip() == example.corrected_text.strip():
            score += 0.5
    if hasattr(example, "errors") and example.errors:
        expected = set(example.errors)
        predicted = set(prediction.errors) if prediction.errors else set()
        overlap = len(expected & predicted)
        score += 0.5 * (overlap / max(len(expected), 1))
    return score


# MIPROv2 Optimization
def optimize(trainset: list[dspy.Example], save_path: str = "optimized_inspector.json"):
    prompt_lm = dspy.LM("openai/gpt-4o")

    optimizer = dspy.MIPROv2(
        metric=inspection_metric,
        prompt_model=prompt_lm,
        auto="medium",
        num_threads=8,
        seed=42,
    )

    program = EnglishInspector()
    optimized = optimizer.compile(
        student=program,
        trainset=trainset,
        minibatch=True,
        minibatch_size=25,
    )
    optimized.save(save_path)
    return optimized


# Usage
if __name__ == "__main__":
    inspector = EnglishInspector()
    result = inspector(text="She go to school every day.", level="beginner")
    print("Corrected:", result.corrected_text)
    print("Errors:", result.errors)
    print("Score:", result.score)
    print("Explanation:", result.explanation)
```

### uv Project Setup Commands

```bash
# 1. Initialize project
uv init english-inspector-backend
cd english-inspector-backend

# 2. Add dependencies
uv add dspy litellm python-dotenv

# 3. Add dev dependencies
uv add --dev pytest ruff

# 4. Run the inspector
uv run python src/inspector.py

# 5. Run tests
uv run pytest tests/
```

---

## 8. Version Compatibility Matrix

| Package | Version | Python | Notes |
|---|---|---|---|
| `dspy` | `3.1.3` | `>=3.10, <3.15` | Stable as of 2026-02-05 |
| `litellm` | `1.81.16` | `>=3.9, <4.0` | Stable as of 2026-02-26 |
| `uv` | latest | — | Always install latest |

DSPy 3.x uses LiteLLM internally. You do not need to pin a specific LiteLLM version unless you have a conflict — DSPy's own `pyproject.toml` pins its LiteLLM dependency.

---

## 9. Key Gotchas and Notes

1. **Package name:** Install as `pip install dspy` (not `dspy-ai`). The `dspy-ai` package is a legacy name; prefer `dspy`.

2. **LiteLLM is internal to DSPy:** DSPy calls LiteLLM under the hood. Pass `provider/model-name` to `dspy.LM()` — no separate LiteLLM configuration is needed unless you are using the LiteLLM proxy server.

3. **API keys via env vars:** Preferred approach is `os.environ["ANTHROPIC_API_KEY"] = "..."` or a `.env` file with `python-dotenv`. Keys can also be passed as `dspy.LM(api_key=...)` but this risks accidental logging.

4. **MIPROv2 dataset size:** Minimum ~20 examples for meaningful optimization. Recommended 200+ for `auto="medium"` or `auto="heavy"`. With fewer than 20 examples, use `BootstrapFewShot` instead.

5. **MIPROv2 import:** `dspy.MIPROv2` is available at the top level. Alternative: `from dspy.teleprompt import MIPROv2`.

6. **Saving/loading optimized programs:** Use `program.save("path.json")` and `program.load("path.json")`. The JSON stores the optimized instructions and few-shot examples — not model weights.

7. **Cache behavior:** DSPy caches LM responses by default (`cache=True`). Set `cache=False` during development if you want fresh responses every time.

8. **uv auto-creates .venv:** Running `uv add` or `uv sync` automatically creates and maintains `.venv`. You do not need to activate the venv manually when using `uv run`.

9. **Reasoning models special handling:** For `o3`, `o4`, `gpt-5` family models, DSPy enforces `temperature=None` and `max_tokens=None` (or >= 16000). Do not set these manually for reasoning models or DSPy will raise `ValueError`.

10. **`dspy.configure` is global:** Calling `dspy.configure(lm=lm)` sets the default LM for all modules in the process. Use `dspy.context(lm=other_lm)` as a context manager for temporary overrides.

---

## 10. Sources

| Resource | URL |
|---|---|
| DSPy PyPI | https://pypi.org/project/dspy/ |
| DSPy Official Docs | https://dspy.ai/ |
| DSPy LM API Reference | https://dspy.ai/api/models/LM/ |
| DSPy Language Models Guide | https://dspy.ai/learn/programming/language_models/ |
| DSPy Optimizers Guide | https://dspy.ai/learn/optimization/optimizers/ |
| MIPROv2 API Reference | https://dspy.ai/api/optimizers/MIPROv2/ |
| MIPROv2 Deep Dive (GitHub) | https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/MIPROv2.md |
| LiteLLM PyPI | https://pypi.org/project/litellm/ |
| LiteLLM Getting Started | https://docs.litellm.ai/docs/ |
| LiteLLM Anthropic Provider | https://docs.litellm.ai/docs/providers/anthropic |
| LiteLLM OpenAI Provider | https://docs.litellm.ai/docs/providers/openai |
| LiteLLM All Providers | https://docs.litellm.ai/docs/providers |
| uv Docs | https://docs.astral.sh/uv/ |
| uv Projects Guide | https://docs.astral.sh/uv/guides/projects/ |
| uv CLI Reference | https://docs.astral.sh/uv/reference/cli/ |
| DSPy GitHub | https://github.com/stanfordnlp/dspy |
