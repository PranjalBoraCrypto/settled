# Deploy and submit — Settled

No terminal at any point. Roughly 30 minutes, most of it waiting for validators.

You've already done the GitHub half of this once with the spinner, so Part 3 will feel familiar.

---

## Part 1 — Wallet on Bradbury

You said you already have testnet GEN, so this is mostly a check.

1. Open MetaMask and look for a network called **Genlayer Bradbury Testnet**. If it's there with
   a GEN balance, skip to Part 2.

2. **⚠️ Check this before adding anything.** Testnet Bradbury and Testnet Asimov **share chain
   ID 4221**. MetaMask allows only one network per chain ID, so if you already have Asimov
   saved, adding Bradbury will either conflict or silently point you at Asimov's RPC and
   nothing will work. **Delete Asimov first** if it's there.

3. If you need to add Bradbury manually:

   | Field | Value |
   | --- | --- |
   | Network name | `Genlayer Bradbury Testnet` |
   | RPC URL | `https://rpc-bradbury.genlayer.com` |
   | Chain ID | `4221` |
   | Currency symbol | `GEN` |
   | Block explorer | `https://explorer-bradbury.genlayer.com/` |

4. Need more GEN? `https://testnet-faucet.genlayer.foundation/` — 100 GEN, once a week.

---

## Part 2 — Deploy the contract

1. Go to **`https://studio.genlayer.com`**. It opens on "GenLayer Studio" (its own sandbox).

2. **Switch the network.** Click the network chip in the header → **"Connect studio to"** →
   choose **Genlayer Bradbury Testnet** (`chain 4221 · testnet`). An amber warning appears
   saying Studio features are disabled on testnet — that's expected and correct.

   > If you can't find the network chip, tell me before going further. There's a fallback where
   > we deploy from our own page instead, but I'd rather adjust the code than have you guess.

3. **Connect your wallet** via the account chip → *Connect Wallet* → MetaMask. Approve the
   chain switch if prompted.

   Do **not** use the burner account Studio creates for you. It has 0 GEN on Bradbury and the
   deploy will fail.

4. Left sidebar → **Contracts** → **Add From File** → upload `settled.py`.

5. Click **Run and Debug** (▶). The constructor takes no arguments, so there's nothing to fill in.

6. Click **Deploy Settled**. Confirm in MetaMask.

7. Wait. This is real consensus with real validators — it is not instant.

8. When it completes, **copy the contract address.** You need it twice: for the frontend and for
   the submission.

### If the deploy fails on the first line

The contract starts with `# { "Depends": "py-genlayer:1jb45aa8..." }`, which pins the SDK
version. That hash comes from GenLayer's own docs, but I could not verify from here that
Bradbury currently accepts it.

If you get an error mentioning `Depends` or the runner: open any of Studio's built-in example
contracts, copy **its** first line, and paste it over ours. Then redeploy. Tell me if that
happens and I'll check whether anything else needs to change for that SDK version.

---

## Part 3 — Put the frontend online

Same flow as the spinner.

1. New **public** repo called `settled`.

2. Upload all five files at the **root** of the repo (not in a folder — GitHub Pages only
   serves from the root):
   - `index.html`
   - `genlayer-js.browser.js`
   - `README.md`
   - `DEPLOY.md`

   - `settled.py`

3. **Commit changes.**

4. Settings → Pages → Deploy from a branch → `main` → `/ (root)` → **Save**.

5. Wait a minute or two, then open `https://YOUR-USERNAME.github.io/settled/`.

6. Edit `README.md` on GitHub and replace `YOUR-USERNAME` and `YOUR_CONTRACT_ADDRESS` with the
   real values.

---

## Part 4 — Prove it works

Do this before submitting. A reviewer will.

1. Open your live page, paste the contract address, click **Connect wallet**.
2. Click **Fill an example**, then **Create market**. Confirm in MetaMask.
3. Click **Load markets** — your market should appear as `OPEN`.
4. Click **Run resolution**. **Now go and do something else** — this runs a language model on
   five validators against a live page. It takes a while.
5. Come back, **Load markets** again. The market should read `RESOLVED` with a `YES`/`NO`/
   `UNRESOLVED` outcome, the validators' reasoning, and a quote from the source.
6. Save the transaction link. `https://explorer-bradbury.genlayer.com/tx/0x…`

If resolution comes back "no consensus", that isn't a bug — the validators disagreed and the
contract correctly refused to write anything. Try a source that states the fact more plainly.
Worth knowing: **that behaviour is itself a selling point**, and I'd mention it in the
submission if it happens to you.

---

## Part 5 — Submit

Portal → **Builder** → **Projects** → **Submit**.

Remember there were only **2 spots left this week**, and weekly limits run Monday 00:00 to
Sunday 23:59 UTC. Don't submit until Part 4 actually worked.

**Evidence links — give all three:**

- Live app: `https://YOUR-USERNAME.github.io/settled/`
- Code: `https://github.com/YOUR-USERNAME/settled`
- Contract on-chain: `https://explorer-bradbury.genlayer.com/address/YOUR_CONTRACT_ADDRESS`

Also paste the deployment or resolution **transaction** link. The Foundation's evidence
guidelines specifically ask for a deployment transaction or contract address plus an explorer
link, publicly accessible with no login — test all of them in a private window first.

### Description — paste this and fill in the URLs

> **Settled — an adjudication oracle for ambiguous prediction-market questions.**
>
> Prediction markets rarely fail at pricing; they fail at resolution. When a market's wording
> meets reality, someone has to read a source and judge what it means — a decision no
> deterministic chain can make. That gap is currently filled by token-weighted voting, which is
> slow, capturable, and has produced settlements a reasonable person would call wrong.
>
> Settled puts the reading on-chain. A market names a question, its resolution criteria, and a
> source. `resolve()` opens a non-deterministic block where every validator independently
> fetches the source, runs inference over it, and forms its own verdict. A resolved market can
> be disputed once; `adjudicate()` re-runs the judgement with the objection placed in front of
> the validators, and that result is final — an optimistic oracle whose appeal is decided by
> re-reading the evidence rather than by whoever holds the most tokens.
>
> Two decisions worth noting. Agreement is checked **programmatically**, not by a judge model:
> because the outcome is a closed enum, `run_nondet_unsafe` compares outcomes by string
> equality while letting each validator word its reasoning freely — cheaper than
> `prompt_comparative` and impossible to talk into "close enough". And the outcome is
> **three-valued**: if the source is ambiguous the answer is UNRESOLVED, and if validators
> genuinely disagree the transaction goes undetermined, nothing is written, and the market
> stays open. For an oracle, no answer beats a wrong answer.
>
> Frontend is a single static HTML file with `genlayer-js` bundled and committed — no build
> step, no CDN, no framework. The contract was written against the `genlayer-py-std` v0.2.16
> source rather than the docs, which contain several errors that break on copy.
>
> Live: [your Pages URL]
> Code: [your GitHub URL]
> Contract: [your explorer URL]

If there's a date field, set it to today.

---

## Two honest notes

**The Studio network switcher is the one thing I couldn't verify from here.** My researcher
confirmed it from GenLayer's shipped frontend source and the live config on their hosted
instance — the evidence is strong, but nobody loaded the actual running app. If the switcher
isn't there, stop and tell me; there's a documented fallback and it's a code change, not a
dead end.

**Resolution latency is real.** Five validators, real inference, a live page fetch. If it feels
stuck, it probably isn't. Check the transaction on the explorer before assuming anything broke.
