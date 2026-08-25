# Settled

**An adjudication oracle whose verdicts move money.**

GenLayer validators independently fetch a web source, read it, and rule on what
it says. A second contract stakes real GEN on that ruling and pays out on it.

**0.0040 GEN has changed hands on Testnet Bradbury because five machines read a
JSON file and agreed on what it meant.** That is the claim, and everything below
is how to check it without taking anyone's word for it.

**[Open the live record →](https://pranjalboracrypto.github.io/settled/)**

| | |
| --- | --- |
| **Oracle** — `settled.py` | [`0x3AA27bb63D456D83fcC4d3fAC34e5e4BbD6a0138`](https://explorer-bradbury.genlayer.com/address/0x3AA27bb63D456D83fcC4d3fAC34e5e4BbD6a0138) |
| **Payout** — `payout.py` | [`0xb25975a91277754480CF6f9092e6aF7Db31e824B`](https://explorer-bradbury.genlayer.com/address/0xb25975a91277754480CF6f9092e6aF7Db31e824B) |
| Network | Testnet Bradbury · chain 4221 |
| Lint | `genvm-lint 0.11.0` — passes on both files |

The two `.py` files in this repository are **byte-identical to what is deployed
at those addresses.**

---

## Check it yourself in thirty seconds

The market `payout-demo-10975` is settled and paid out. Here is the part that
needs no trust at all.

When the validators ruled, each hashed the source they had fetched, and the
digest went on-chain:

```
83cd5291cfd2c1d644015037bdd09a1276c3c4fda085511fbdd78094846a08e5
```

That is the keccak-256 of what
[`feed.json`](https://raw.githubusercontent.com/PranjalBoraCrypto/settled/main/feed.json)
serves right now. Reproduce it:

```bash
curl -s https://raw.githubusercontent.com/PranjalBoraCrypto/settled/main/feed.json \
  | keccak-256sum
```

Or press **“Fetch the source and hash it here”** on the live site — it pulls the
source into your own browser, hashes it there, and compares.

A recorded number anyone can reproduce is evidence. A screenshot is not.

---

## What review asked for

The first submission came back with two limitations. Both are addressed, and each
links to the thing that shows it.

### 1. “The finding is not yet bound to a market settlement or payout.”

`payout.py` is a parimutuel pool that stakes native GEN on a market and pays out
on the oracle's finding. `settle()` reads the oracle and records what it said,
with no discretion of its own.

A verdict becomes spendable only when **two independent locks** open:

- **The oracle's lifecycle** reaches `FINAL` — the dispute window elapsed
  unchallenged, or an appeal was heard and decided.
- **The chain finalizes that decision.** Every read in `payout.py` that releases
  money goes through `StorageType.LATEST_FINAL`. A resolution that could still be
  reorganised is not visible to the payout contract at all.

Those are different guarantees. The first says the humans have stopped arguing;
the second says the chain has stopped moving. On Bradbury the second costs about
half an hour, and the site shows it as a countdown rather than letting a refusal
look like a fault.

**Writing this exposed a hole in v1.** There was no path from `RESOLVED` to
`FINAL` — a market that resolved and was never disputed sat there forever. Nobody
had noticed, because the question only becomes urgent when something wants to
spend the answer. `finalize()` exists because building the consumer forced it.

### 2. “Creator-selected mutable sources remain weakly authenticated.”

Sources are graded by a property that can actually be checked: **does the URL
name its own content?**

| Tier | Meaning |
| --- | --- |
| `PINNED` | The URL names its content — a commit SHA, an IPFS CID, an archive snapshot. Must hash to a digest committed at creation, or no verdict is written. |
| `MUTABLE` | Everything else. Recorded honestly as such. |

There is deliberately no middle tier for “reputable domain”. Reputation is not a
cryptographic property.

A mutable source cannot be committed to in advance — that is what makes it
mutable. So before the embargo lifts, **every validator fetches it and they must
agree on its digest exactly**. That is an observation, not an assertion.

**The first attempt at this was worse than nothing.** It let the market creator
*type* a baseline digest at creation and showed it to backers as provenance.
`create_market` is a deterministic write; it cannot fetch anything. The number
was never checked against the world. A commitment is worth the observation behind
it, so the observation is now made.

**And the snapshot earns its place twice.** Because consensus on it is
exact-digest equality, it doubles as a **determinism filter**: a source carrying a
timestamp or a rotating banner fails it, and a source validators cannot read
identically today will deadlock the verdict after the event — by which time money
is staked. `payout.py` refuses to open a pool until a market has been snapshotted.

Be precise about the direction. *Failing* the snapshot is strong evidence a market
is unstakeable. *Passing* it is not evidence a market is safe: it says the source
read identically, once, before any money existed.

---

## Why the strongest sources are the ones you must not bet on

`payout.py` refuses to open a pool on a `PINNED` market. This looks backwards for
about ten seconds.

If the bytes behind a URL are fixed at market creation, so is the answer. Anyone
willing to read the document knows the outcome before betting opens. Nothing is
being predicted; the market is a race to be last to look.

Pinned sources are for adjudicating what a fixed document says. They are the
wrong thing to bet on.

---

## The demonstration, end to end

| Step | What happened |
| --- | --- |
| **Filed** | A question with a 20-minute resolution embargo, fixed before anything about the answer was known. |
| **Attested** | Validators fetched the source and agreed on `0960f3815bf588ec…`. |
| **Staked** | 0.0030 GEN on YES, 0.0010 GEN on NO, from two different wallets. Neither is the market creator — the contract forbids it. |
| **The event** | `feed.json` edited from `"pending"` to `"confirmed"`. |
| **Ruled** | Validators read it independently and returned **YES**, quoting `"status": "confirmed"`. The digest was now `83cd5291cfd2c1d6…` — **the source had moved between the two readings**, and that is on-chain. |
| **Closed** | Dispute window elapsed unchallenged. |
| **Settled** | Payout read the oracle at finalized state and fixed the result. |
| **Claimed** | The YES backer withdrew **0.0040 GEN** — its own stake plus the losing side's. |

The losing wallet is worth looking at too: the site shows it in red, states it
backed NO against a YES finding, and offers nothing to claim.

---

## The rules

Seventy-one refusals are written into the two contracts, grouped and explained on
the live site under **[The rules](https://pranjalboracrypto.github.io/settled/#rules)**.

Most systems hide these. They are shown because a rule nobody can see is
indistinguishable from a bug — and because several were added only after an
attempt to break the contract succeeded.

---

## Files

| | |
| --- | --- |
| [`settled.py`](settled.py) | The oracle. Deployed as-is. |
| [`payout.py`](payout.py) | The consumer contract that stakes and pays. Deployed as-is. |
| [`DESIGN.md`](DESIGN.md) | Why the contracts are shaped this way, **and what broke when they were attacked.** |
| [`index.html`](index.html) | The whole interface. One file, no build step, `genlayer-js` bundled and committed. |
| [`feed.json`](feed.json) | The demonstration source. |

---

## What broke when we attacked it

Four rounds of adversarial review, each told to find ways to steal or lock money.
Around twenty-five findings. [`DESIGN.md`](DESIGN.md) has them all; the shape of
them:

- **Funds could be locked forever, three separate ways.** Every timing parameter
  is now bounded at both ends, in both contracts, and the payout contract
  independently re-checks all four of the oracle's.
- **A losing bet could be cancelled for free.** An outage during an appeal made
  every validator agree the market was unresolvable — which refunds everyone.
- **The escape hatch was itself a theft path.** A jam now falls back to the
  first-pass verdict rather than voiding it, so stalling reinstates the answer the
  staller was trying to escape.
- **A “safety feature” turned out to be a weapon.** `close_early()` let anyone shut
  the book once the source moved — and freezing a parimutuel is worth money to
  whoever is already winning. *A defence that pays its attacker more than its user
  is not a defence.* Deleted.
- **A feature silently never worked.** A missing name inside a consensus block
  raised `NameError`, was swallowed identically on every node, and reported a
  plausible outage forever. Only executing the contract found it.

**The last round deleted rather than added**, because both money-moving findings
were in mechanisms introduced while fixing earlier rounds. That is the general
lesson: each fix is new surface, and surface is where bugs live.

---

## Known limits

Stated rather than left to be discovered. Full list in [`DESIGN.md`](DESIGN.md).

- **A mutable source is published by somebody, and that somebody can lie.** The
  creator is barred from staking and everything is recorded before anyone stakes,
  but a publisher colluding with a backer through a second key is made *visible*,
  not prevented. This is the irreducible trust in an oracle that reads one source.
- **Nothing knows when the event actually happens.** If the embargo lands after
  the source publishes, the answer is public while the book is open.
- **Whoever calls `resolve()` picks the instant the source is read**, and on a live
  source the instant can pick the answer. Bounded windows make that hours rather
  than unlimited; they do not remove it.
- **Disputing is free.** The profitable versions are closed, but nothing prices the
  attempt. The fix is a bond forfeited when the original outcome is upheld, which
  needs the oracle to custody value. **An unbonded appeal is not really an
  appeal**, and this is the next piece of work.
- **Prompt injection is mitigated, not eliminated.** Every party-supplied field is
  JSON-escaped, and the prompt names them untrusted. A persuasive argument written
  *inside* a field is still an argument the model reads. Note the shape of the
  risk: a successful persuasion is deterministic, so every validator is convinced
  identically and consensus passes unanimously. **Agreement is not truth.**
- **A single source has no redundancy.** Reading several independent sources and
  taking the majority would move the cost of forcing a deadlock from “run one
  flaky endpoint” to “control most of them”. Settled reads one.

---

## Notes for anyone reading the code

- **Line 2 of each contract must stay blank.** The runtime concatenates
  consecutive leading comment lines into `runner.json`; deleting it folds the
  header into that object and the contract will not deploy.
- **The non-deterministic functions are defined inline**, not returned from a
  factory — `genvm-lint` matches the qualified name of the function passed to
  `run_nondet` against the scope where the `gl.nondet.*` calls were found.
- **Written against the SDK source, not the docs**, which contain errors that are
  load-bearing if copied: `gl.UserError` does not exist (it is `gl.vm.UserError`),
  and the web response field is `.status`, not `.status_code`.
- **Contract source goes on-chain and there is a size ceiling.** These files were
  half prose and would not deploy, which is why the reasoning lives in
  [`DESIGN.md`](DESIGN.md).

---

Built for the GenLayer Foundation Portal, Builder → Projects.
