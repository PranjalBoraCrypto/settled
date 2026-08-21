# Submitting Settled — everything ready to paste

## Before you submit

- [ ] Upload the two updated files (`index.html`, `README.md`) to the repo and **Commit changes**
- [ ] Open all three links below **in a private window** — reviewers check them logged out
- [ ] Confirm your Portal profile has a display name and email (submissions are blocked without)

---

## Where to go

Portal → **Builder** → **Projects** → **Submit**

Not Intelligent Contracts. Not Milestones. Projects.

Weekly limits run Monday 00:00 to Sunday 23:59 UTC, and there were **2 spots left**.

---

## The three evidence links

```
https://pranjalboracrypto.github.io/settled/
```
```
https://github.com/PranjalBoraCrypto/settled
```
```
https://explorer-bradbury.genlayer.com/address/0xf02e9d00659f44F4245e371D1A493F1260406C8f
```

Give all three. The Foundation's evidence guidelines ask for a contract address **plus** an
explorer link, publicly accessible with no login.

---

## Description — paste this whole thing

> **Settled — an adjudication oracle for ambiguous prediction-market questions.**
>
> Prediction markets rarely fail at pricing; they fail at resolution. When a market's wording
> meets reality, someone has to read a source and judge what it means — a decision no
> deterministic chain can make. That gap is filled today by token-weighted voting, which is
> slow, capturable, and has produced settlements a reasonable person would call wrong.
>
> Settled puts the reading on-chain. A market names a question, its resolution criteria, and a
> source. `resolve()` opens a non-deterministic block where every validator independently
> fetches the source, runs inference over it, and forms its own verdict. A resolved market can
> be disputed once; `adjudicate()` re-runs the judgement with the objection placed in front of
> the validators.
>
> Two design decisions. Agreement is checked **programmatically**, not by a judge model:
> because the outcome is a closed enum, `run_nondet_unsafe` compares outcomes by string
> equality while letting each validator word its reasoning freely — cheaper than
> `prompt_comparative` and impossible to talk into "close enough". And the outcome is
> **three-valued**: an ambiguous source resolves UNRESOLVED, and if validators genuinely
> disagree the transaction goes undetermined, nothing is written, and the market stays open.
>
> Both claims were tested on Bradbury rather than asserted, and the log is public. One market
> settled — validators agreed on YES and quoted the source directly. A second went undetermined
> after four leader rotations and wrote nothing, because its source was a client-rendered page
> and validators received different amounts of it; for an oracle, source determinism matters as
> much as source authority. A third result is the appeal: the settled market was disputed, the
> objection recorded on-chain, and adjudication then went undetermined too. Resolution asks
> validators to read a fact; adjudication asks them to weigh an argument against it, and the
> second is genuinely contestable. Appeals being harder to settle than original judgements is an
> honest property, not a bug — and it points at the next design, where an appeal carries a bond
> and re-opens the narrow point in contention rather than the whole judgement.
>
> Frontend is a single static HTML file with genlayer-js bundled and committed — no build step,
> no CDN, no framework. It verifies every write by reading state back off the chain rather than
> trusting the transaction receipt, because an undetermined transaction returns a receipt that
> looks successful. The contract was written against the genlayer-py-std v0.2.16 source rather
> than the docs, which contain several errors that break on copy.
>
> Live: https://pranjalboracrypto.github.io/settled/
> Code: https://github.com/PranjalBoraCrypto/settled
> Contract: https://explorer-bradbury.genlayer.com/address/0xf02e9d00659f44F4245e371D1A493F1260406C8f

---

## If there's a date field

Set it to **today**. It only accepts past or present dates.

---

## After you submit

Tell me how it goes. If it's rejected I want to see the reason — that's the most useful
information available for the next one, and there will be a next one now that the whole
pipeline is built and you know it works.
