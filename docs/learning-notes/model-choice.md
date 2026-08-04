# Decision: Qwen2.5-3B-Instruct (Q4_K_M) over alternatives

## Choice

Serving the agent with `qwen2.5:3b-instruct-q4_K_M` via Ollama, GPU-offloaded
to the RTX 3050 (4GB VRAM). Confirmed at Phase 1: 2.2GB resident, 100% GPU,
~63.5 tokens/sec eval rate.

## Alternatives considered

- **Qwen2.5-7B-Instruct (Q4)** — the blueprint's own designated "stretch"
  option. Roughly double the parameters, generally stronger reasoning and
  SQL generation, but doesn't fully fit in 4GB VRAM at Q4 — it would split
  across GPU/CPU, which is slower and, combined with only ~2GB of typically
  free system RAM, risks disk-swap stalls mid-demo. **Checked, not just
  assumed, during Phase 5b:** at the time of that check, `nvidia-smi` showed
  3.6GB VRAM free (fine), but `Get-CimInstance Win32_OperatingSystem` showed
  only ~457MB of system RAM free out of 8GB total — far below the
  blueprint's own "~4GB+ free" bar for attempting this stretch option. The
  7B vs. 3B comparison below is therefore still reasoned, not measured on
  this hardware in this session; the measurement that *was* taken was
  "is it even safe to try right now," and the answer was no.
- **Llama 3.1 8B** — already pulled locally (4.9GB) from earlier
  experimentation. Strong general-purpose model, but at that size it
  doesn't fit in 4GB VRAM either, so it's subject to the same GPU/CPU-split
  risk as Qwen2.5-7B, without a specific SQL-generation advantage that
  would justify the risk for this project's scope.
- **Phi-3** (also already pulled locally, 2.2GB) — comparable size class to
  Qwen2.5-3B and would likely also fit in VRAM. Not chosen because Qwen2.5
  has a stronger track record specifically on structured-output/tool-calling
  tasks (which this project depends on directly for reliable `tool_calls`
  emission), whereas Phi-3's strengths are more general reasoning/coding.
- **A full-precision (unquantized) model at any size** — would need far
  more VRAM than 4GB has to offer for any model large enough to be useful
  here; not viable on this hardware regardless of parameter count.

## Reasoning for the pick

- Fits entirely in the 4GB VRAM budget with room left for the KV cache,
  which is what keeps every tool-calling round trip GPU-bound instead of
  falling back to slow CPU/disk-swap inference — confirmed empirically
  (100% GPU, no CPU split).
- Qwen2.5's instruct-tuned line has solid, well-documented tool-calling
  support, which this project leans on directly: the agent's entire loop
  depends on the model reliably emitting structured `tool_calls` rather
  than describing actions in prose (this actually surfaced as a real issue
  during Phase 3 testing — see
  `docs/learning-notes/self-correction-behavior.md`).
- Reliability was prioritized over raw capability per Section 1's
  constraints — a model that runs smoothly end-to-end beats a stronger
  model that risks stalling mid-demo.

## What would change under a different problem statement

- On a machine with more VRAM (e.g. 8GB+), Qwen2.5-7B or Llama 3.1 8B would
  likely give better SQL correctness on harder multi-join questions, and
  would be the better default rather than a "stretch" option.
- If the project's goal were specifically SQL-generation accuracy rather
  than demonstrating the agentic ReAct pattern, a SQL-specialized model
  (e.g. SQLCoder or a fine-tuned text-to-SQL model) would likely outperform
  a general-purpose instruct model of similar size — but that trades away
  the "general-purpose agent that happens to use SQL tools" story this
  project is telling, and would reintroduce fine-tuning/training scope that
  Section 0 explicitly rules out for this project.
- If budget allowed a paid API (explicitly ruled out here), a hosted
  frontier model would remove the quantization/VRAM tradeoff question
  entirely, at the cost of the $0 budget constraint and the offline-only
  reliability property.
