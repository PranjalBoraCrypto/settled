# Settled

**An adjudication oracle for ambiguous prediction-market questions, built on GenLayer.**

- **Live app:** https://pranjalboracrypto.github.io/settled/
- **Contract on Testnet Bradbury:** [`0xf02e9d00659f44F4245e371D1A493F1260406C8f`](https://explorer-bradbury.genlayer.com/address/0xf02e9d00659f44F4245e371D1A493F1260406C8f)

---

## The problem

Prediction markets rarely fail at pricing. They fail at **resolution**.

A market is written in advance, in English, about a future that hasn't happened yet. When it
does happen, reality almost never arrives in the shape the wording anticipated. Someone then
has to read a source and decide what it means — and that is a judgement no deterministic
chain can perform. `keccak256` cannot tell you whether a press release constitutes an
announcement.

So the industry outsources it: to a multisig, to a committee, or to token-weighted voting
where the correct answer is whatever the largest holder decides it is. All three are slow,
capturable, and have produced settlements a reasonable person would call wrong.

## What Settled does

It puts the reading itself on-chain.

A market names three things: a **question**, the **criteria** that settle it, and a **source**.
Calling `resolve()` opens a non-deterministic block in which every validator independently
fetches that source, runs a language model over it, and forms its own verdict.

The network only settles if they agree.

```
OPEN ──resolve()──▶ RESOLVED ──dispute()──▶ DISPUTED ──adjudicate()──▶ FINAL
```

All four transitions are implemented. On testnet the first three are demonstrated on-chain;
the fourth went undetermined, which is documented below rather than hidden.

A resolved market can be disputed once. `adjudicate()` re-runs the entire judgement with the
objection placed in front of the validators, and that result is final — an optimistic oracle
whose appeal is decided by re-reading the evidence rather than by whoever holds the most
tokens.

## Why this needs GenLayer specifically

Worth scrutinising, because "uses an LLM" is not the same as "needs GenLayer."

The consensus check is not a hash comparison. It is five validators each running inference
over a live web page and having to arrive at the same answer. That only works if the protocol
can reach agreement over non-deterministic operations — which is what GenLayer's optimistic
democracy provides and no other chain does. Remove GenLayer and what's left is one server
calling a model API and asking you to trust it, which is the centralised-oracle problem this
was built to solve.

Two design decisions follow from taking that seriously.

**1. Agreement is checked programmatically, not by another model.**

The obvious approach is `gl.eq_principle.prompt_comparative`: hand the leader's answer and the
validator's answer to a judge model and ask whether they match. That spends an inference call
to compare three possible values, and a judge model can be talked into "close enough."

Because the outcome is a closed enum, agreement is decided by string equality instead:

```python
def validate(leader_result) -> bool:
    if not isinstance(leader_result, gl.vm.Return):
        return False
    own = judge()                                    # this validator's own reading
    return leader_result.calldata["outcome"] == own["outcome"]

verdict = gl.vm.run_nondet_unsafe(judge, validate)
```

Each validator reads the source itself and compares only the decision. Rationale and quoted
evidence are free to differ, and always do.

**2. The outcome is three-valued.**

`YES`, `NO`, `UNRESOLVED`. An oracle that cannot say *I don't know* is one that guesses under
pressure. If the source is silent or ambiguous, that is recorded honestly — and if validators
genuinely cannot agree, the transaction goes **undetermined**, nothing is written, and the
market stays open. For an oracle, no answer beats a wrong answer.

## What actually happened on testnet

Both of those claims were tested on Bradbury rather than asserted.

**A market that settled.** [`polymarket-definition`](https://pranjalboracrypto.github.io/settled/)
asked whether a source describes Polymarket as a prediction market, against the Wikipedia
article. The validators agreed on `YES`, recording the reasoning *"The source text explicitly
and repeatedly describes Polymarket as a prediction market"* and quoting the article directly:

> Polymarket is an American cryptocurrency-based prediction market

**A market that refused to settle.** `gl-bradbury-live` asked a comparable question against
GenLayer's own documentation site. Four leader rotations later the network
[decided *Undetermined*](https://explorer-bradbury.genlayer.com/tx/0x14f9624d245fb5c776749265181b14e5221f3c1445dbabdf97c4f5c592fd011a)
and wrote nothing. The leader's reading was sound; the validators simply did not all reach the
same answer.

The cause turned out to be the source, not the contract. That documentation site renders in
the browser, so five validators fetching it independently received different amounts of it —
and a validator handed a half-rendered page honestly answers `UNRESOLVED` while the leader
says `YES`. They were not malfunctioning. They were disagreeing about what they had read.

**An appeal that could not be agreed either.** The settled market was then disputed with the
objection *"the source is a Wikipedia article, not Polymarket's own website, so it may not
reflect how the company describes itself."* The dispute recorded fine. The `adjudicate()` call
that followed went undetermined, and the market sits at `DISPUTED` in the app today.

That result is worth more than a tidy `FINAL` would have been. Resolution asks validators to
read a fact; adjudication asks them to weigh an **argument** against that fact. The first
converges easily — five models agree that a page saying "Polymarket is a prediction market"
says what it says. The second is genuinely contestable, and the network contested it. An
appeals process where appeals are harder to settle than original judgements is not a broken
appeals process; it is an honest one, and it points at the obvious next design: appeals should
carry a bond and a narrower question, not the whole judgement re-opened.

**That is the most useful thing this project learned, and it generalises:** for an oracle,
source *determinism* matters as much as source *authority*. A page that returns identical
bytes to every reader is a usable source; one that is assembled per-request is not, however
authoritative it looks. The market left open in the app is deliberately left that way as the
demonstration.

## Repository

| Path | What it is |
| --- | --- |
| `settled.py` | The intelligent contract. GenLayer SDK v0.2.x. |
| `index.html` | The dApp. One static file, no build step, no framework. |
| `genlayer-js.browser.js` | `genlayer-js@1.1.8` pre-bundled for the browser (see below). |
| `DEPLOY.md` | Deploy and run it yourself. |

## Notes on the build

**No build step, and no CDN either.** `genlayer-js` is pure ESM whose only external dependency
is `viem`, so it *can* be loaded from a CDN — but a submission that breaks when a CDN has a bad
day isn't much of a submission. The SDK is bundled once with esbuild and the artifact committed.
The page is then genuinely static: `index.html` plus one local module.

```bash
npm install genlayer-js@1.1.8 esbuild
npx esbuild entry.js --bundle --format=esm --platform=browser --minify \
  --outfile=genlayer-js.browser.js
```

**`client.connect()` is deliberately not used.** It requests the GenLayer MetaMask Snap, which
fails on wallets without Snap support and isn't needed for reads or writes. The app performs
the EIP-1193 chain switch itself and passes `provider: window.ethereum` to the client.

**The app verifies writes by reading state back, never by trusting the receipt.** An
undetermined transaction returns a receipt that looks successful while changing nothing. After
every `resolve()` or `adjudicate()` the app re-reads the market and confirms the status
actually moved; if it didn't, it says so plainly instead of reporting success. Slow
transactions are reported as slow, not as failures — consensus over a live page can take a
long time, and telling a user it failed invites them to pay for it twice.

**The contract is written against the SDK source, not the documentation.** GenLayer's docs
contain errors that are load-bearing if copied: `gl.UserError` doesn't exist (it's
`gl.vm.UserError`), `prompt_non_comparative` has no `input` parameter, and the web response
field is `.status`, not `.status_code`. Every API call here was checked against
`genlayer-py-std` at tag `v0.2.16`.

**Builtin exceptions are never raised.** They crash the WASM runtime with a generic exit code,
discard the message, and break consensus. Every failure path raises `gl.vm.UserError`, with
constant strings — error messages are compared for strict equality between leader and
validator, so interpolating a varying value causes spurious consensus failures.

**Storage never crosses into a non-deterministic block.** Storage objects are proxies that
cannot survive the sub-VM boundary; touching one inside a nondet block raises, the block fails,
and the symptom looks like a consensus problem rather than the storage bug it is. Every value
the judgement needs is hoisted into a plain local string before the closure is built.

## Known limits

- Resolution reads **one** source. A serious deployment wants several and a quorum across them;
  the contract is structured so that's an additive change to `_make_judge`.
- Page text is truncated to 12,000 characters. A source burying the decisive fact below that
  resolves `UNRESOLVED`.
- No stake or bond gates a frivolous dispute, and adjudication re-opens the whole judgement
  rather than the narrow point in contention. Both are why the appeal in the log below could
  not reach consensus, and both are the obvious next milestone.
- Resolution is slow — real inference on five validators over a live page. The UI is built
  around that rather than pretending otherwise.

---

Built for the GenLayer Foundation Portal, Builder → Projects.
The loading spinner is reused from a sibling submission to the *Design the GenLayer Spinner*
mission — it animates the same consensus mechanic this contract runs on.
