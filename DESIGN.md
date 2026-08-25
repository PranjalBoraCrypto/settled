# Settled — design notes

Why the contracts are shaped the way they are, and what broke when we attacked
them. This document exists because the reasoning used to live in the contract
files as comments, and the contract grew past what the chain would accept. The
prose came out; none of it was discarded.

---

## What review asked for

The first version was returned with:

> The main limitation is that the finding is not yet bound to a market
> settlement or payout, and creator-selected mutable sources remain weakly
> authenticated. A stronger version should connect final outcomes to a consumer
> contract and add explicit source provenance or immutable evidence commitments.

Two things. This is how each is answered, and what answering them exposed.

---

## 1. Binding the verdict to money

`payout.py` is a parimutuel pool that stakes native GEN on a market and pays out
on the oracle's finding. Nothing about it is decorative: `settle()` reads the
oracle and records what it said, with no discretion of its own.

A verdict becomes spendable only when **two independent locks** open.

**The first lock is the oracle's own lifecycle.** A finding must reach `FINAL`,
which happens either because its dispute window elapsed unchallenged, or because
an appeal was heard and decided.

**The second lock is chain finality.** Every read in `payout.py` that releases
money goes through `StorageType.LATEST_FINAL`. A resolution that could still be
reorganised is not visible to the payout contract at all.

Those are different guarantees. The first says the humans have stopped arguing;
the second says the chain has stopped moving. On Bradbury the second costs about
half an hour, and the live site shows it as a countdown rather than letting a
refusal look like a fault.

### The hole this exposed

v1 had no path from `RESOLVED` to `FINAL`. A market that resolved and was never
disputed sat in `RESOLVED` forever. Nobody had noticed because nothing needed to
know when a verdict was safe to spend — the question only becomes urgent when
something wants to spend it. `finalize()` exists because writing the consumer
forced the question.

---

## 2. Authenticating the source

Sources are graded by a property that can actually be checked: **does the URL
name its own content?**

| Tier | Meaning | Example |
| --- | --- | --- |
| `PINNED` | The URL names its content. Changing the bytes requires changing the URL. | a `raw.githubusercontent.com` path with a 40-hex commit SHA; an IPFS CID; a `web.archive.org` snapshot with the `id_` modifier |
| `MUTABLE` | Everything else. Recorded honestly as such. | a live JSON endpoint, a branch reference, a documentation page |

There is deliberately no middle tier for "reputable domain". Reputation is not a
cryptographic property, and pretending otherwise would be the exact weakness this
is meant to remove.

A pinned source must hash to a digest committed at creation, or **no verdict is
written at all**. The digest is checked in `resolve()` and in `adjudicate()`, and
the model never sees a byte the digest did not cover — the prompt slice is taken
from inside the hashed window, and a pinned body larger than that window is
refused rather than partially committed.

### The commitment that was worth nothing

A mutable source cannot be committed to in advance; that is what makes it
mutable. The first attempt to fix this let the market creator **type** a
"baseline" digest at creation and displayed it to backers as provenance.

`create_market` is a deterministic write. It cannot fetch anything. So that
number was never checked against the world — it was a value the creator invented,
stored on-chain, and presented as evidence. **That is worse than having no
commitment, because it reads as stronger.**

`snapshot()` replaced it. Before the embargo lifts, every validator fetches the
source and they must agree on its digest **exactly**. That is an observation, not
an assertion.

### The snapshot earns its place twice

Because consensus on it is exact-digest equality — a deliberately brutal standard
— it doubles as a **determinism filter**.

A source carrying a timestamp, a rotating banner, a per-request identifier or an
inconsistent load balancer will fail it. That is the point: a source independent
validators cannot read identically today will deadlock the verdict after the
event, by which time money is already staked and the only exit is a refund.
Finding out while the pool is still empty is worth more than the baseline itself.

`payout.py` refuses to open a pool until a market has been snapshotted.

Be precise about the direction, because the useful-sounding version of this claim
is the false one. **Failing** the snapshot is strong evidence a market is
unstakeable. **Passing** it is not evidence the market is safe: it says the source
read identically, once, before any money existed. An adversary serves a static
file for the length of the embargo, passes cleanly, and varies the bytes
afterwards. This filters accidental non-determinism, which is common. It does not
constrain a publisher who intends to break their own source.

---

## Why the strongest sources are the ones you must not bet on

`payout.py` refuses to open a pool on a `PINNED` market. This looks backwards for
about ten seconds.

If the bytes behind a URL are fixed at market creation, then so is the answer.
Anyone willing to read the document knows the outcome before betting opens.
Nothing is being predicted; the market is a race to be last to look.

Pinned sources are the right tool for adjudicating what a fixed document says.
They are the wrong thing to bet on.

---

## The embargo

`resolve()` is permissionless, which is correct for an oracle and dangerous for a
market: whoever reads the source first also chooses the moment the answer becomes
official. Left alone that is a free option — stake on the side you already know
wins, then resolve in the very next transaction so nobody can follow you in.

So the earliest resolution time is fixed when the market is created, before
anybody knows anything, and the payout contract closes its book at that same
instant rather than waiting to observe a status change it cannot front-run.

Resolution also has a **deadline**, not just a start. Bounding when a source may
first be read is pointless without bounding the end: on a live source, whoever
picks the reading instant picks the answer, and an unbounded window lets them
wait for the reading they want.

---

## Consensus is checked on the enum, not by a judge model

The obvious approach is `prompt_comparative`: hand both answers to a model and
ask whether they agree. That spends an inference call to compare three possible
values, and a judge model can be talked into "close enough".

Because the outcome is a closed enum, string equality decides it instead. Each
validator forms its own verdict and compares only the decision; rationale and
quoted evidence stay free to differ, which they always will.

The digest is deliberately **excluded** from that comparison. Any source carrying
a timestamp would produce a different hash on every node and deadlock on the
first try. What is recorded on-chain is the leader's read, made credible by
validators independently agreeing on the outcome derived from it. That is an
audit trail, not a proof, and calling it a proof would be the dishonest version.

### An outage is not an answer

`judge()` returns a `judged` flag alongside the outcome. A fetch failure, a
digest mismatch or a malformed model reply all produce `UNRESOLVED` with
`judged = False`, and the market **stays open and retryable** rather than being
terminally voided.

Validators compare the flag as well as the outcome. Without that, an endpoint
serving real content to the first request and 404s to every one after gives the
leader a judged `UNRESOLVED` and every validator an unjudged one — the enums
match, consensus passes unanimously, and a terminal verdict gets written on
evidence exactly one node ever saw. Since a consumer maps `UNRESOLVED` to a full
refund, that is a losing backer buying their money back with a rate limit.

---

## What broke when we attacked it

Four rounds of adversarial review, each one told to find ways to steal or lock
money. Roughly twenty-five findings. The ones worth recording:

**Funds could be locked forever, three separate ways.** Nothing capped how far in
the future a market could be set to resolve. A market created with a nonsense
value could never be resolved and never expired — no exit, and anything staked on
it gone. Every timing parameter is now bounded at both ends, in both contracts,
and the payout contract independently re-checks all four of the oracle's.

**A losing bet could be cancelled for free.** If a source went down during an
appeal, every validator saw the same failure, agreed unanimously, and the market
settled to "unresolvable" — which refunds everyone. Whoever was losing could
dispute, break their own source, and get their money back. Losing became
impossible.

**The escape hatch was itself a theft path.** The first attempt at unwinding a
jammed market refunded everyone. But an outcome becomes public at `RESOLVED`,
long before `FINAL`, so a backer who could see they had lost could dispute, wait,
and unwind a bet they had already lost. Rewritten twice; a jam now falls back to
the first-pass verdict rather than voiding it, so stalling reinstates exactly the
answer the staller was trying to escape.

**A "safety feature" turned out to be a weapon.** A `close_early()` function let
anyone shut the book once the source moved. In a parimutuel, freezing the book is
worth money to whoever is already winning — and the trigger fired at exactly the
moment the winner became knowable. The best-informed party could stake and then
freeze in the next transaction, undiluted. **A defence that pays its attacker more
than its user is not a defence.** Deleted.

**A cap became a lock.** A 500-backer limit, added to bound an audit list, could
be filled with throwaway addresses to shut every honest participant out of a pool
permanently — and the stakes are returned at settlement, so it cost the attacker
nothing. The cap and the list are gone.

**Two individually-correct timers combined into a theft.** Adjudication ran on
one clock and expiry on another, with nothing requiring the second to be later
than the first. Whenever expiry came first, the side favoured by the original
verdict could destroy a live appeal and take the pot, days before the appellant's
own deadline. Both bounds now derive from one timer, which makes the overlap
impossible rather than merely unlikely.

**A URL could forge its own provenance.** The authority in a URL ends at `/`, `?`
or `#`. Parsing only for `/` meant `https://evil.com?@raw.githubusercontent.com/…`
read as a GitHub host and classified as content-addressed, while the fetch went to
`evil.com`. Validating the sanitised string rather than the submitted one closed
three such bypasses at once.

**A feature silently never worked.** `close_early()` referenced a constant that
did not exist in its file. The `NameError` was swallowed by the broad exception
handler every non-deterministic block needs, identically on every node, so
consensus passed and the feature reported a plausible outage for every input
forever. Only executing the contract found it. Every module-level name used inside
a consensus block is now bound to a local before the closure is built, so a
missing name raises loudly, and `check_names.py` in this repo checks it in under a
second.

The last round found nothing wrong with the contracts. Every finding was in
tooling, or in code added while fixing the previous round.

---

## The last round deleted rather than added

Both money-moving findings in round four were in mechanisms added during rounds
two and three. So round four removed `close_early()`, the minimum-stake floor, a
duration cap that was provably unreachable, an oracle check that could never fire,
and an entire consensus block.

That is the general lesson, and it is why the contracts are smaller now than they
were two rounds ago: **each fix is new surface, and surface is where bugs live.**

---

## Known limits

Written out rather than left to be discovered. Each is here because the fix is
real work, not because it is unimportant.

- **A mutable source is published by somebody, and that somebody can lie.** The
  creator is barred from staking; the source, criteria and creator are copied
  into the pool before anyone stakes; the pre-event digest is observed by
  validators. None of that prevents a publisher colluding with a backer through a
  second key. It makes the collusion visible. This is the irreducible trust in an
  oracle that reads one web source.

- **Nothing knows when the event actually happens.** The embargo is a
  creator-chosen number, and if it lands after the source publishes, the answer is
  public while the book is still open. A baseline-freshness rule caps that
  exposure at 24 hours; it does not remove it.

- **Whoever calls `resolve()` picks the instant the source is read**, and on a
  live source the instant can pick the answer. Both readings are confined to
  bounded windows, so the discretion is hours rather than unlimited — but inside
  a window it is real. Removing it needs the source sampled at a committed time
  or averaged over several. Neither is built.

- **A market nobody manages to resolve ends `UNRESOLVED` and refunds.** That is
  the only defensible result, and it is also what a losing backer wants. The
  structural answer is not to read a single source: fetching several independent
  ones in the same block and taking the majority moves the cost from "run one
  flaky endpoint" to "control most of them". Settled reads one source, so it does
  not have that property today.

- **Disputing is free.** The profitable versions are closed — an outage during
  adjudication cannot void a market, the appeal has a deadline, and an appeal
  reaching only doubt leaves the first-pass verdict standing. But nothing prices
  the attempt, and a dispute still delays settlement. The fix is a bond posted
  with the objection and forfeited when the original outcome is upheld, which
  needs the oracle to custody value. **An unbonded appeal is not really an
  appeal**, and this is the next piece of work.

- **Prompt injection is mitigated, not eliminated.** Every party-supplied field is
  JSON-escaped so none can break out of its slot and forge instructions, and the
  prompt names them as untrusted. A persuasive argument written *inside* a field
  is still an argument the model reads — and the objection field is exactly that
  by design. Note the shape of the risk: a successful persuasion is
  deterministic, so every validator is convinced identically and consensus passes
  unanimously. **Agreement is not truth.**

- **The oracle address is fixed at deployment and cannot be changed.** That is
  correct — it cannot be redirected at a hostile oracle — but it means the oracle
  must be deployed with an empty upgraders list. Nothing on-chain here can check
  that, so it is a deployment precondition rather than a guarantee.

- Dust from integer division stays in the contract, bounded by the number of
  backers. A claim whose transfer fails cannot be re-claimed. A one-sided pool
  refunds, which makes the last staker pivotal — inherent to parimutuel pools.

---

## Why a refusal cannot be quoted from its receipt

Every refusal in these contracts is a specific sentence, written to say exactly
what is wrong. Getting that sentence in front of the person who tripped it took
three attempts, and the two failures are properties of the chain rather than
bugs that got fixed.

**Attempt 1 — read it out of the transaction receipt.** It is not there. A
GenLayer receipt carries the calldata (twice), a status, and a *hash* of the
result — one per validator, identical when they agree:

```
"validatorResultHash": [ "0xab3f3f10…", "0xab3f3f10…", ×5 ]
"txExecutionResultName": "FINISHED_WITH_ERROR"
```

Five machines agreeing on the hash of an error is exactly what consensus should
produce. It is also unreadable. Successive decoders got as far as recovering the
*calldata* — and briefly displayed the caller's own question back to them as
though it were the contract's answer, which is worse than admitting nothing was
found. Echoing the question as the answer is now explicitly guarded against.

**Attempt 2 — ask a node to run the call read-only first.** Nodes simulate
`view` methods, not `write` ones. The call was refused, the wallet opened
anyway, and the receipt was still a hash.

**Attempt 3 — check in the page.** `index.html` mirrors the opening validation of
`create_market`, which is the part a person filling in the form can actually
trip. The refusal appears immediately, quoted exactly, with no signature and no
gas.

Duplicating contract logic in a client is normally a bad trade, so it is
constrained in two ways:

- **The mirror only ever refuses. It never approves.** Passing it means nothing;
  the contract still runs all sixty-seven checks and is the only thing that
  decides. There is no path where the page's opinion admits something the
  contract would reject.
- **Drift is detected mechanically.** `contracts/check_mirror.py` parses
  `settled.py` and `index.html` and fails if the shortener list, the character
  and duration limits, the sentences, or *the order the checks fire in* have
  diverged. Order matters: if the mirror tested the URL before the market id, it
  would confidently name the wrong rule for a market that violates both.

The guard was itself tested against four drift shapes — a shortener dropped, a
shortener invented, two checks transposed, and a sentence the contract does not
raise — and catches all four. A checker that cannot fail is not a checker; that
lesson was already paid for once on this project, when the first version of
`check_names.py` passed a file whose `snapshot()` was dead code.

Finally, because a page vouching for a contract is not evidence, the refusal
panel links to the transaction where the deployed contract refused that same
market on-chain: five validators, unanimous, `FINISHED_WITH_ERROR`. The page
explains; the chain proves.

---

## Notes for anyone reading the code

- **Line 2 of each contract must stay blank.** The runtime concatenates
  consecutive leading comment lines into `runner.json`; deleting that blank line
  folds the whole header into the object, JSON parsing fails, and the contract
  will not deploy.

- **The non-deterministic functions are defined inline**, not returned from a
  factory. `genvm-lint` proves statically which code may run inside a consensus
  block by matching the qualified name of the function passed to `run_nondet`
  against the scope where the `gl.nondet.*` calls were found. A closure defined in
  one scope and passed in another breaks that match — which is what got the
  companion project rejected on its first submission.

- **Written against the SDK source, not the docs.** The published documentation
  contains errors that are load-bearing if copied: `gl.UserError` does not exist
  (it is `gl.vm.UserError`), and the web response field is `.status`, not
  `.status_code`.

- **Contract source goes on-chain, and there is a size ceiling.** These files were
  half prose and would not deploy. That is why this document exists.
