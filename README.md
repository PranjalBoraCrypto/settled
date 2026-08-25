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

### Both readings, and the fact that they differ

The interesting claim is not that one digest matches. It is that the source
**moved between two readings**, and the chain recorded both. Reproduce both:

```bash
BASE=https://raw.githubusercontent.com/PranjalBoraCrypto/settled/main

# 0960f3815bf588ec2e27bd1cc646111a75f33c754e3215ff88f600b7f8b77d76
curl -s $BASE/feed.before.json | keccak-256sum

# 83cd5291cfd2c1d644015037bdd09a1276c3c4fda085511fbdd78094846a08e5
curl -s $BASE/feed.json        | keccak-256sum
```

`feed.before.json` is committed for exactly this reason. It is the byte-identical
content the source served when `snapshot()` ran, and without it the earlier digest
is a number you would have to take on faith. Two reproducible hashes and one
on-chain `source_changed: true` is the whole argument:

- the validators agreed on what the source said **before** anyone knew the answer,
- they agreed on what it said **after**,
- and the contract noticed, on-chain, that those were not the same thing.

Nothing here asks you to believe the operator. Both files are in this repository;
hash them yourself.

---

## What review asked for

The first submission came back with two limitations. Both are addressed, and each
links to the thing that shows it.

### 1. “The finding is not yet bound to a market settlement or payout.”

`payout.py` is a parimutuel pool that stakes native GEN on a market and pays out
on the oracle's finding. `settle()` reads the oracle and records what it said. It
takes no human input and has no override.

It does apply **one** rule of its own, and it is deliberate: if a market was
disputed and the appeal came back `UNRESOLVED`, the first-pass verdict stands
rather than the market voiding. That is not a loophole, it closes one — voiding
refunds everyone, which is a free exit for whoever is losing, so stalling an
appeal would otherwise be a way to cancel a bet you were losing. Stalling now
reinstates the answer the staller was trying to escape.

A verdict becomes spendable only when **two independent locks** open:

- **The oracle's lifecycle** reaches `FINAL` — the dispute window elapsed
  unchallenged, or an appeal was heard and decided.
- **The chain finalizes that decision.** Every read in `payout.py` that releases
  money goes through `StorageType.LATEST_FINAL`. A resolution that could still be
  reorganised is not visible to the payout contract at all.

Those are different guarantees. The first says the humans have stopped arguing;
the second says the chain has stopped moving. On Bradbury the second costs
somewhere between about 29 and about 40 minutes — it is not a fixed window — and
the site shows it as a countdown rather than letting a refusal look like a fault.
The countdown is labelled an estimate, because nothing in the browser can read
finalized chain state to confirm it.

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

Run twice, on two independent markets. The second — `payout-demo-3` — is linked
transaction by transaction below, because a claim with no link behind it is a
claim.

| # | Step | Wallet | What happened | On-chain |
| --- | --- | --- | --- | --- |
| 1 | **Filed** | creator | A question with a 20-minute embargo, fixed before anything about the answer was known. | [`0x723ef9a1…`](https://explorer-bradbury.genlayer.com/tx/0x723ef9a1dc2497301159a17d6241caf0220b2e39d9e552e18db719b0f06bec34) |
| 2 | **Attested** | creator | Every validator fetched the source and agreed on `5a3d690aa3c15005…` exactly. | [`0x754da744…`](https://explorer-bradbury.genlayer.com/tx/0x754da744b90628208e9d82c80fa443af1c946ea6e559fae0de5e78bbd330f9b5) |
| 3 | **Pool opened** | creator | The payout contract re-checked the oracle's own parameters before accepting money. | [`0x5f094bd6…`](https://explorer-bradbury.genlayer.com/tx/0x5f094bd642cb07c7a63e9e4b64aaa735fd395ee93329f51a84b8b66f80741d94) |
| 4 | **Staked YES** | backer A | 0.0030 GEN. | [`0xf4caf0f5…`](https://explorer-bradbury.genlayer.com/tx/0xf4caf0f5ea9d081bb5dc9c49048fa87ca4f891adb1c590bf43256dea5da34939) |
| 5 | **Staked NO** | backer B | 0.0010 GEN. Uneven on purpose — it makes the payout obviously right rather than a coin flip. | [`0x7966c49d…`](https://explorer-bradbury.genlayer.com/tx/0x7966c49dd9604dae9e260659b39c5c773937cc1d02d941682db565b13532691f) |
| — | *The event* | — | `run2.json` edited from `"pending"` to `"confirmed"`. | — |
| 6 | **Ruled** | creator | Validators read it independently and returned **YES**, quoting `"status": "confirmed"`. Digest now `c751bad651fe8d40…` — **the source moved between the two readings**, recorded on-chain. | [`0xb9136c86…`](https://explorer-bradbury.genlayer.com/tx/0xb9136c86cd54723d8463c34b40f7c6c276b0e13d98da7c73d6a383ad78cc199f) |
| 7 | **Closed** | creator | Dispute window elapsed unchallenged. | [`0x5f8981f8…`](https://explorer-bradbury.genlayer.com/tx/0x5f8981f82793a18c22c0db414e537d7649f66667502dc6b19794ff0599aa97e9) |
| — | **Settle refused** | creator | Tried before the chain had finalized the close. **`ACCEPTED (ERROR)`** — the second lock, refusing. | [`0x200c06a9…`](https://explorer-bradbury.genlayer.com/tx/0x200c06a9c4111afc55bd1236cbffbc9dd100af908aa8fbc9a74cd0091bf4a08e) |
| 8 | **Settled** | creator | Retried after finality. Payout read the oracle at finalized state and fixed the result. | [`0xe771a125…`](https://explorer-bradbury.genlayer.com/tx/0xe771a125b0897f59781236890bf6887891f5ab48f374d65abf81c16250d65db0) |
| 9 | **Claimed** | backer A | Withdrew **0.0040 GEN** — its own stake plus the losing side's. | [`0x99524142…`](https://explorer-bradbury.genlayer.com/tx/0x995241424008b86db52660822aa4c6a6b47c39596e901549df61aede0c8e1417) |

**The refused settle is not an embarrassment, it is the point.** A verdict that
the humans have stopped arguing about is still not spendable until the chain has
stopped moving. Row 8 is the same call, unchanged, succeeding once that was true.

**Check any row against its arguments rather than against this table.** Open a
transaction, press **Show data → Decoded**, and the explorer prints exactly what
was called:

```json
{"args": ["payout-demo-3", "YES"], "method": "back"}
```

That is row 4. Every row can be read the same way, which means nothing here has to
be taken on the strength of a label I wrote. Each transaction also carries a
**Transaction Journey** — submitted, activation, leader proposal, vote commit, all
votes committed, leader reveal, vote reveal, decided, finalized. That is why a
payout takes minutes rather than seconds: it is not one node executing a transfer,
it is a validator set agreeing that the transfer should happen.

### Both readings reproduce

The two digests the validators recorded are not assertions. Both files are in
this repository and both hash to what is on-chain:

```bash
BASE=https://raw.githubusercontent.com/PranjalBoraCrypto/settled/main

# 5a3d690aa3c15005acbd030482b93e88103606e36f729e14b4dd8d8443afdb1f  (step 2)
curl -s $BASE/run2.before.json | keccak-256sum

# c751bad651fe8d40547e400229b548cf81fb84ca7807db56b258df8f4f3c1da0  (step 6)
curl -s $BASE/run2.json        | keccak-256sum
```

Two reproducible hashes, taken at two moments, differing — and a contract that
noticed. That is the entire claim, and none of it requires trusting the operator.

### The first run

`payout-demo-10975` ran the same lifecycle earlier against `feed.json`, digests
`0960f3815bf588ec…` → `83cd5291cfd2c1d6…`, and also paid out 0.0040 GEN. Its
files are committed too (`feed.before.json`, `feed.json`), so its digests
reproduce the same way.

### Rules refusing, on-chain

| What was attempted | Result |
| --- | --- |
| A market whose source was a `bit.ly` link | [`0x8407a415…`](https://explorer-bradbury.genlayer.com/tx/0x8407a415c50b8e14f05fd9cc708601e42a8c107eab7eb6b0545cf3ed5317f745) — *"link shorteners are not accepted as sources"* |
| A market creator staking on its own market | refused — *"the market creator cannot stake on their own market"* — observed during the run, transaction not recorded here |
| Staking after the book closed | refused — the embargo had lifted — observed during the run, transaction not recorded here |

The losing side is shown honestly rather than quietly: connected with the NO
backer's wallet, the site marks the position in red, states that it backed NO
against a YES finding, and offers nothing to claim. That view needs that wallet,
so it is a design note rather than something a reader can verify from here — the
checkable part is the stakes and the settlement, both linked above.

---

## The rules

The two contracts refuse in **67 distinct sentences**, raised at 92 places in the
source:

```bash
grep -c 'raise gl.vm.UserError' settled.py payout.py    # 57 + 35 = 92
```

**All 67 are catalogued** — grouped, searchable, and most explained at length — on the live
site under **[The rules](https://pranjalboracrypto.github.io/settled/#rules)**.
Not a selection of the interesting ones: the whole set, because an incomplete
list invites you to assume the omissions do not exist.

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
| [`check_names.py`](check_names.py) | Proves every name used inside a consensus block is bound in that block's own scope — the failure that got v1 rejected, caught in under a second. |
| [`check_mirror.py`](check_mirror.py) | Fails if the page's copy of the entry rules has drifted from the contract's — values, sentences, **and the order they fire in**. |
| [`feed.json`](feed.json) | The **first** run's source, **as it reads now** — hashes to the digest recorded at `resolve()`. |
| [`feed.before.json`](feed.before.json) | The same source **as it read at `snapshot()`**, before the event. Hashes to the earlier digest. Committed so both readings can be checked, not just the later one. |
| [`run2.json`](run2.json) · [`run2.before.json`](run2.before.json) | The **second** run's source, after and before its event. Both hash to the digests recorded on-chain for `payout-demo-3`. |
| [`genlayer-js.browser.js`](genlayer-js.browser.js) | The GenLayer client, bundled and committed so the page has no build step and no CDN. |

---

## What broke when we attacked it

Four rounds of adversarial review, each told to find ways to steal or lock money.
Around twenty-five findings. [`DESIGN.md`](DESIGN.md) has them all; the shape of
them:

- **Funds could be locked forever, three separate ways.** Every timing parameter
  is now bounded at both ends, in both contracts, and the payout contract
  independently re-checks all three of the oracle's — at both ends, which is six
  separate refusals.
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

- **One of the 67 refusals cannot fire, and over-long URLs are silently truncated.**
  `create_market` sanitises the source URL with a helper that already clamps it to
  300 characters, then tests whether it exceeds 300 — which it no longer can. A
  400-character URL is not rejected; it is cut to 300 and stored, pointing
  somewhere else. Found while auditing the rule catalogue, after deployment. It is
  listed on the site as unreachable rather than removed, because a catalogue that
  claims to be complete has to include the embarrassing entries too.

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
