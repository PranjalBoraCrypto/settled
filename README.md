# Settled

**An adjudication oracle for ambiguous prediction-market questions, built on GenLayer.**

- Live app: `https://YOUR-USERNAME.github.io/settled/`
- Contract on Testnet Bradbury: `https://explorer-bradbury.genlayer.com/address/YOUR_CONTRACT_ADDRESS`

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
capturable, and have produced settlements that a reasonable person would call wrong.

## What Settled does

It puts the reading itself on-chain.

A market names three things: a **question**, the **criteria** that settle it, and a **source**.
Calling `resolve()` opens a non-deterministic block in which every validator independently
fetches that source, runs a language model over it, and forms its own verdict.

The network only settles if they agree.

```
OPEN ──resolve()──▶ RESOLVED ──dispute()──▶ DISPUTED ──adjudicate()──▶ FINAL
```

A resolved market can be disputed once. `adjudicate()` re-runs the entire judgement with the
objection placed in front of the validators, and that result is final. It's an optimistic
oracle whose appeal is decided by re-reading the evidence rather than by whoever holds the
most tokens.

## Why this needs GenLayer specifically

This is the part worth scrutinising, because "uses an LLM" is not the same as "needs GenLayer."

The consensus check is not a hash comparison. It is five validators each running inference
over a live web page and having to arrive at the same answer. That only works if the protocol
can reach agreement over non-deterministic operations — which is precisely what GenLayer's
optimistic democracy provides and what no other chain does.

Two design decisions follow from taking that seriously:

**1. Agreement is checked programmatically, not by another model.**

The obvious approach is `gl.eq_principle.prompt_comparative`, which hands the leader's answer
and the validator's answer to a judge model and asks whether they match. That spends an
inference call to compare three possible values, and a judge model can be talked into "close
enough."

Because the outcome is a closed enum, agreement is decided by string equality instead:

```python
def validate(leader_result) -> bool:
    if not isinstance(leader_result, gl.vm.Return):
        return False
    own = judge()                                    # this validator's own reading
    return leader_result.calldata["outcome"] == own["outcome"]

verdict = gl.vm.run_nondet_unsafe(judge, validate)
```

Each validator reads the source itself and compares only the decision. The rationale and the
quoted evidence are free to differ, and always will. Deterministic, cheaper, and impossible
to argue with.

**2. The outcome is three-valued.**

`YES`, `NO`, `UNRESOLVED`. An oracle that cannot say *I don't know* is an oracle that guesses
under pressure. If the source is silent or ambiguous, the honest answer is recorded as such —
and if the validators genuinely cannot agree, the transaction goes **undetermined**, nothing
is written, and the market stays open. For an oracle, no answer beats a wrong answer, and the
UI surfaces that state explicitly rather than hiding it as an error.

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
day isn't much of a submission. The SDK is bundled once with esbuild and the artifact is
committed. The page is then genuinely static: `index.html` plus one local module, servable from
GitHub Pages with nothing else running anywhere.

To regenerate it:

```bash
npm install genlayer-js@1.1.8 esbuild
npx esbuild entry.js --bundle --format=esm --platform=browser --minify \
  --outfile=genlayer-js.browser.js
```

**`client.connect()` is deliberately not used.** It requests the GenLayer MetaMask Snap, which
fails on wallets without Snap support and isn't needed for reads or writes. The app does the
EIP-1193 chain switch by hand and passes `provider: window.ethereum` straight to the client.

**The contract is written against the SDK source, not the documentation.** GenLayer's docs
contain several errors that are load-bearing if you copy them: `gl.UserError` doesn't exist
(it's `gl.vm.UserError`), `prompt_non_comparative` has no `input` parameter, and the web
response field is `.status`, not `.status_code`. Every API call here was checked against
`genlayer-py-std` at tag `v0.2.16`.

**Builtin exceptions are never raised.** They crash the WASM runtime with a generic exit code,
discard the message, and break consensus. Every failure path raises `gl.vm.UserError`, and
error strings are kept constant — messages are compared for strict equality between leader and
validator, so interpolating a varying value into one causes spurious consensus failures.

**Storage never crosses into a non-deterministic block.** Storage objects are proxies that
can't survive the sub-VM boundary; touching one inside a nondet block raises, the block fails,
and the symptom looks like a consensus problem rather than the storage bug it is. Every value
the judgement needs is hoisted into a plain local string before the closure is built.

## Known limits

- Resolution reads **one** source. A serious deployment would want several and a quorum across
  them; the contract is structured so that's an additive change to `_make_judge`.
- Page text is truncated to 12,000 characters. A source that buries the decisive fact below
  that will resolve `UNRESOLVED`.
- There is no stake, bond, or economic cost to opening a frivolous dispute. That's the obvious
  next milestone, not an oversight.
- `resolve()` is slow — real inference on five validators over a live page. The UI is built
  around that rather than pretending it's instant.

---

Built for the GenLayer Foundation Portal, Builder → Projects.
The loading spinner is reused from a sibling submission to the *Design the GenLayer Spinner*
mission — it animates the same consensus mechanic this contract runs on.
