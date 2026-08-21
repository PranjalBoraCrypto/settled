# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

# Settled — an adjudication oracle for ambiguous prediction-market questions.
#
# Prediction markets do not usually fail at pricing. They fail at resolution:
# a question turns out to be ambiguous, the source says something the question
# did not anticipate, and settling it needs a reading of natural language that
# no deterministic chain can perform. Today that gap is filled by human voting,
# which is slow, capturable, and has produced some famously contested outcomes.
#
# Settled puts that judgement on-chain. A market names a question, the criteria
# that settle it, and a source. Resolution runs inside a non-deterministic block:
# each validator independently fetches the source, reads it, and forms its own
# verdict. Consensus is then checked PROGRAMMATICALLY on the outcome enum alone —
# validators must agree on YES / NO / UNRESOLVED, and are free to disagree about
# how they worded their reasoning. If they cannot agree, the transaction goes
# undetermined and the market simply stays open, which is the correct failure
# mode for an oracle: no answer beats a wrong answer.
#
# A resolved market can be disputed once. Adjudication re-runs the whole
# judgement with the disputer's objection placed in front of the validators, and
# the result is final. That mirrors how optimistic oracles work in practice,
# except the appeal is decided by re-reading the evidence rather than by whoever
# holds the most tokens.

from dataclasses import dataclass

from genlayer import *

# Outcome enum. Deliberately three-valued: an oracle that cannot say "I don't
# know" is an oracle that lies under pressure.
YES = "YES"
NO = "NO"
UNRESOLVED = "UNRESOLVED"
_VALID_OUTCOMES = (YES, NO, UNRESOLVED)

# Market lifecycle.
OPEN = "OPEN"
RESOLVED = "RESOLVED"
DISPUTED = "DISPUTED"
FINAL = "FINAL"

# Everything the leader returns is written to chain, so the model is held to
# tight budgets and the results are truncated again on the way in.
_MAX_PAGE_CHARS = 12000
_MAX_RATIONALE_CHARS = 400
_MAX_EVIDENCE_CHARS = 300
_MAX_QUESTION_CHARS = 500
_MAX_CRITERIA_CHARS = 1000
_MAX_REASON_CHARS = 500


@allow_storage
@dataclass
class Market:
    id: str
    question: str
    criteria: str
    source_url: str
    status: str
    outcome: str
    rationale: str
    evidence: str
    creator: str
    created_at: str
    resolved_at: str
    dispute_reason: str
    disputer: str


def _build_prompt(question: str, criteria: str, url: str, page: str, objection: str) -> str:
    """Compose the judgement prompt.

    Written to narrow the model's freedom as far as possible: the evidence is
    fixed, outside knowledge is forbidden, and the output space is three tokens.
    The less room the model has to be creative, the more often independent
    validators land on the same answer — which is the whole game here.
    """
    objection_block = ""
    if objection:
        objection_block = (
            "\nA previous resolution of this question was DISPUTED. The objection raised was:\n"
            f'"{objection}"\n'
            "Weigh this objection against the source text. It is an argument, not a fact —\n"
            "uphold it only if the source text actually supports it.\n"
        )

    return f"""You are settling a prediction market question. Decide using ONLY the source text below.

QUESTION:
{question}

RESOLUTION CRITERIA:
{criteria}
{objection_block}
SOURCE TEXT (retrieved from {url}):
---
{page}
---

Rules:
- Answer YES only if the source text states facts that clearly satisfy the criteria.
- Answer NO only if the source text states facts that clearly contradict the criteria.
- Answer UNRESOLVED if the source is silent, ambiguous, self-contradictory, or the
  event in question has not happened yet.
- Do not use any knowledge beyond the source text. Do not infer, predict or speculate.
- If the source text does not mention the subject of the question at all, the answer
  is UNRESOLVED, not NO.

Reply with a JSON object containing exactly these three keys:
  "outcome"   - one of "YES", "NO", "UNRESOLVED"
  "rationale" - one sentence, at most 40 words, explaining the decision
  "evidence"  - a short verbatim quote from the source text, at most 30 words,
                or "" if the source contains nothing relevant
"""


def _make_judge(question: str, criteria: str, url: str, objection: str):
    """Return the non-deterministic judgement closure.

    Every value it needs is passed in as a plain Python string. Storage objects
    are proxies that cannot cross into the sub-VM a non-deterministic block runs
    in; touching one in here would raise, the block would fail, and the symptom
    would look like a consensus failure rather than the storage bug it actually
    is. So nothing from `self` is captured — only strings hoisted by the caller.
    """

    def judge() -> dict:
        page = gl.nondet.web.render(url, mode="text")
        page = page[:_MAX_PAGE_CHARS]

        raw = gl.nondet.exec_prompt(
            _build_prompt(question, criteria, url, page, objection),
            response_format="json",
        )

        # The host guarantees valid JSON; it does not guarantee the keys asked
        # for. Normalise here, inside the block, so that the leader and every
        # validator apply identical coercion to whatever the model produced.
        outcome = str(raw.get("outcome", "")).strip().upper()
        if outcome not in _VALID_OUTCOMES:
            outcome = UNRESOLVED

        return {
            "outcome": outcome,
            "rationale": str(raw.get("rationale", ""))[:_MAX_RATIONALE_CHARS],
            "evidence": str(raw.get("evidence", ""))[:_MAX_EVIDENCE_CHARS],
        }

    return judge


def _make_validator(judge):
    """Return the validator predicate.

    This is the design decision that matters most in the contract. The obvious
    approach is `prompt_comparative`, which hands the leader's answer and the
    validator's answer to another LLM and asks whether they agree. That spends a
    model call to compare three possible values, and it can be talked into
    "close enough".

    Because the outcome is a closed enum, agreement can be decided by string
    equality instead. Each validator forms its own verdict independently and
    compares only the decision — the rationale and the quoted evidence are free
    to differ, which they always will. Deterministic, cheaper, and impossible to
    argue with.
    """

    def validate(leader_result) -> bool:
        if not isinstance(leader_result, gl.vm.Return):
            return False
        own = judge()
        return leader_result.calldata["outcome"] == own["outcome"]

    return validate


class Settled(gl.Contract):
    markets: TreeMap[str, Market]
    ids: DynArray[str]

    def __init__(self):
        pass

    # ---------------------------------------------------------------- writes

    @gl.public.write
    def create_market(self, market_id: str, question: str, criteria: str, source_url: str) -> None:
        market_id = market_id.strip()
        if not market_id:
            raise gl.vm.UserError("market id is required")
        if market_id in self.markets:
            raise gl.vm.UserError("market id already exists")
        if not question.strip():
            raise gl.vm.UserError("question is required")
        if not criteria.strip():
            raise gl.vm.UserError("resolution criteria are required")
        if not source_url.startswith("http"):
            raise gl.vm.UserError("source url must be a http(s) address")

        self.markets[market_id] = Market(
            id=market_id,
            question=question[:_MAX_QUESTION_CHARS],
            criteria=criteria[:_MAX_CRITERIA_CHARS],
            source_url=source_url,
            status=OPEN,
            outcome=UNRESOLVED,
            rationale="",
            evidence="",
            creator=gl.message.sender_address.as_hex,
            created_at=gl.message_raw["datetime"],
            resolved_at="",
            dispute_reason="",
            disputer="",
        )
        self.ids.append(market_id)

    @gl.public.write
    def resolve(self, market_id: str) -> None:
        """First-pass resolution. Only ever runs once per market."""
        if market_id not in self.markets:
            raise gl.vm.UserError("no such market")

        market = self.markets[market_id]
        if market.status != OPEN:
            raise gl.vm.UserError("market is not open")

        # Hoist out of storage before building the closure — see _make_judge.
        question = str(market.question)
        criteria = str(market.criteria)
        url = str(market.source_url)

        judge = _make_judge(question, criteria, url, "")
        verdict = gl.vm.run_nondet_unsafe(judge, _make_validator(judge))

        market.outcome = verdict["outcome"]
        market.rationale = verdict["rationale"]
        market.evidence = verdict["evidence"]
        market.resolved_at = gl.message_raw["datetime"]

        # An UNRESOLVED verdict is a real answer about the source, not a
        # failure, so the market still moves on and can still be disputed.
        market.status = RESOLVED

        # Read the value back out and print it. This costs nothing on-chain but
        # lands in the GenVM execution log, so if a market ever appears not to
        # have moved after an accepted transaction, the log says immediately
        # whether the write landed or the transaction went undetermined.
        print(f"resolved {market_id} -> {self.markets[market_id].outcome}")

    @gl.public.write
    def dispute(self, market_id: str, reason: str) -> None:
        """Object to a resolution. One dispute per market, then it is settled."""
        if market_id not in self.markets:
            raise gl.vm.UserError("no such market")
        if not reason.strip():
            raise gl.vm.UserError("a dispute must state a reason")

        market = self.markets[market_id]
        if market.status != RESOLVED:
            raise gl.vm.UserError("only a resolved market can be disputed")

        market.status = DISPUTED
        market.dispute_reason = reason[:_MAX_REASON_CHARS]
        market.disputer = gl.message.sender_address.as_hex

    @gl.public.write
    def adjudicate(self, market_id: str) -> None:
        """Re-judge a disputed market with the objection in evidence. Final."""
        if market_id not in self.markets:
            raise gl.vm.UserError("no such market")

        market = self.markets[market_id]
        if market.status != DISPUTED:
            raise gl.vm.UserError("market is not under dispute")

        question = str(market.question)
        criteria = str(market.criteria)
        url = str(market.source_url)
        objection = str(market.dispute_reason)

        judge = _make_judge(question, criteria, url, objection)
        verdict = gl.vm.run_nondet_unsafe(judge, _make_validator(judge))

        market.outcome = verdict["outcome"]
        market.rationale = verdict["rationale"]
        market.evidence = verdict["evidence"]
        market.resolved_at = gl.message_raw["datetime"]
        market.status = FINAL

        print(f"adjudicated {market_id} -> {self.markets[market_id].outcome}")

    # ----------------------------------------------------------------- views

    @gl.public.view
    def get_market(self, market_id: str) -> Market:
        if market_id not in self.markets:
            raise gl.vm.UserError("no such market")
        return self.markets[market_id]

    @gl.public.view
    def get_markets(self) -> dict:
        return {k: v for k, v in self.markets.items()}

    @gl.public.view
    def get_ids(self) -> list:
        return [str(i) for i in self.ids]
