# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }


from dataclasses import dataclass

from genlayer import *
from genlayer.py.public_abi import StorageType

YES = "YES"
NO = "NO"
UNRESOLVED = "UNRESOLVED"

# The settlement outcome of a pool, which is not the same alphabet as the
# oracle's verdict. An oracle that says UNRESOLVED has answered honestly; a pool
# facing that answer has no winner and must give the money back.
REFUND = "REFUND"

OPEN = "OPEN"
FINAL = "FINAL"
MUTABLE = "MUTABLE"

# A pool will not bind to an oracle whose dispute window is shorter than this.
_MIN_ORACLE_WINDOW = 60

_MIN_ORACLE_EXPIRY = 259200
_MAX_ORACLE_WINDOW = 604800
_MAX_ORACLE_EXPIRY = 2592000

# How long resolution may stay open. The floor is the important one: it is the
# length of outage a source publisher would need to sustain in order to force
# every market on this oracle to expire unresolved, and therefore to refund.
_MIN_ORACLE_RESOLVE_WINDOW = 86400
_MAX_ORACLE_RESOLVE_WINDOW = 604800

# Nor to a market that can be resolved sooner than this. A two-minute book is
# not price discovery; it is a race between whoever is watching the mempool.
_MIN_STAKING_WINDOW = 600


_MAX_ID_CHARS = 64


_MAX_BASELINE_AGE = 86400


@allow_storage
@dataclass
class Pool:
    market_id: str
    creator: str                 # the market's creator on the oracle; barred from staking
    source_url: str              # copied from the oracle at bind time, see open_pool
    question: str                # likewise
    criteria: str                # and the field that actually decides the verdict
    baseline_digest: str         # the pre-event digest the validators observed
    provenance: str              # recorded so a backer can see it without a second lookup
    source_moved: bool           # did the source actually change by resolution
    by_timeout: bool             # did the verdict come from expire() rather than consensus
    by_appeal_denied: bool       # did an appeal reach only doubt, leaving the first pass to stand
    source_moved_known: bool     # was the source ever successfully read at all
    closes_at: u256              # epoch seconds; staking stops here, not on a status change
    total_yes: u256
    total_no: u256
    settled: bool
    result: str                  # YES | NO | REFUND
    opened_at: str
    settled_at: str


def _field(record, name: str) -> str:
    """Read one field from a record returned by a cross-contract view call."""
    if isinstance(record, dict):
        return str(record.get(name, ""))
    return str(getattr(record, name, ""))


def _stake_key(market_id: str, who: str) -> str:
    """Flat composite key, with the address normalised to lower case."""
    return market_id + "|" + who.lower()


def _days_from_civil(y: int, m: int, d: int) -> int:
    """Days since 1970-01-01. Hinnant's civil-calendar algorithm, integer only."""
    if m <= 2:
        y -= 1
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    mp = m - 3 if m > 2 else m + 9
    doy = (153 * mp + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _epoch_seconds(stamp: str) -> int:
    """Parse a consensus timestamp to epoch seconds. Fails closed."""
    digits = ""
    for ch in stamp:
        if "0" <= ch <= "9":
            digits += ch
            if len(digits) == 14:
                break
    if len(digits) != 14:
        raise gl.vm.UserError("unrecognised timestamp format")

    y = int(digits[0:4])
    mo = int(digits[4:6])
    d = int(digits[6:8])
    h = int(digits[8:10])
    mi = int(digits[10:12])
    s = int(digits[12:14])

    if y < 1970 or mo < 1 or mo > 12 or d < 1 or d > 31:
        raise gl.vm.UserError("unrecognised timestamp format")
    if h > 23 or mi > 59 or s > 60:
        raise gl.vm.UserError("unrecognised timestamp format")

    return _days_from_civil(y, mo, d) * 86400 + h * 3600 + mi * 60 + s


class Payout(gl.Contract):
    oracle: Address
    pools: TreeMap[str, Pool]
    ids: DynArray[str]
    stake_yes: TreeMap[str, u256]
    stake_no: TreeMap[str, u256]
    claimed: TreeMap[str, bool]

    def __init__(self, oracle_address: str):
        # Address() raises a builtin Exception on malformed input, which would
        # crash the runtime with a generic exit code and discard the message.
        # Validate first so the failure is a readable UserError instead.
        addr = oracle_address.strip()
        if len(addr) != 42 or not addr.startswith("0x"):
            raise gl.vm.UserError("oracle address must be a 0x-prefixed 20-byte address")
        for ch in addr[2:]:
            if ch not in "0123456789abcdefABCDEF":
                raise gl.vm.UserError("oracle address must be a 0x-prefixed 20-byte address")
        self.oracle = Address(addr)

    # ---------------------------------------------------------------- writes

    @gl.public.write
    def open_pool(self, market_id: str) -> None:
        """Bind a staking pool to one market on the configured oracle."""
        market_id = market_id.strip()
        if not market_id:
            raise gl.vm.UserError("market id is required")
        if len(market_id) > _MAX_ID_CHARS:
            raise gl.vm.UserError("market id is too long")
        if "|" in market_id:
            raise gl.vm.UserError("market id must not contain a pipe character")
        if market_id in self.pools:
            raise gl.vm.UserError("a pool is already open for this market")

        oracle = gl.get_contract_at(self.oracle)
        reader = oracle.view(state=StorageType.LATEST_NON_FINAL)

        objection_window = int(reader.dispute_window_seconds())
        if objection_window < _MIN_ORACLE_WINDOW:
            raise gl.vm.UserError("oracle dispute window is too short to stake against")
        if objection_window > _MAX_ORACLE_WINDOW:
            # A dispute window that never elapses is a market finalize() can
            # never close, and expire() refuses RESOLVED, so it would have no
            # exit and the pool would hold its deposits forever.
            raise gl.vm.UserError("oracle dispute window is too long to stake against")

        grace = int(reader.expire_after_seconds())
        if grace < _MIN_ORACLE_EXPIRY:
            raise gl.vm.UserError("oracle expires markets too aggressively to stake against")
        if grace > _MAX_ORACLE_EXPIRY:
            raise gl.vm.UserError("oracle takes too long to expire a jam to stake against")

        window = int(reader.resolve_window_seconds())
        if window < _MIN_ORACLE_RESOLVE_WINDOW:
            raise gl.vm.UserError("oracle resolution window is too short to stake against")
        if window > _MAX_ORACLE_RESOLVE_WINDOW:
            raise gl.vm.UserError("oracle resolution window is too long to stake against")

        market = reader.get_market(market_id)
        if _field(market, "status") != OPEN:
            raise gl.vm.UserError("market is not open")

        if _field(market, "baseline_observed") not in ("True", "true", "1"):
            raise gl.vm.UserError("market has no observed source baseline; snapshot it first")

        if _field(market, "provenance") != MUTABLE:
            raise gl.vm.UserError("only a mutable-source market can be staked on")

        # The embargo is the real deadline. Reading it here, once, means staking
        # closes at a time everybody could see in advance instead of at whatever
        # moment the fastest reader chooses to call resolve().
        closes_at = int(reader.resolve_not_before(market_id))
        now = _epoch_seconds(gl.message_raw["datetime"])
        if closes_at - now < _MIN_STAKING_WINDOW:
            raise gl.vm.UserError(
                "market has no usable resolution embargo; create it with resolve_after_seconds"
            )

        pool = self.pools.get_or_insert_default(market_id)
        pool.market_id = market_id
        pool.creator = _field(market, "creator").lower()

        baseline_at = _epoch_seconds(_field(market, "baseline_at"))
        if closes_at - baseline_at > _MAX_BASELINE_AGE:
            raise gl.vm.UserError("the source baseline is too old for this closing time")

        pool.source_url = _field(market, "source_url")
        pool.question = _field(market, "question")
        pool.criteria = _field(market, "criteria")
        pool.baseline_digest = _field(market, "baseline_digest")
        pool.provenance = _field(market, "provenance")
        pool.source_moved = False
        pool.by_timeout = False
        pool.by_appeal_denied = False
        pool.source_moved_known = False
        pool.closes_at = u256(closes_at)
        pool.total_yes = u256(0)
        pool.total_no = u256(0)
        pool.settled = False
        pool.result = ""
        pool.opened_at = gl.message_raw["datetime"]
        pool.settled_at = ""
        self.ids.append(market_id)

    @gl.public.write.payable
    def back(self, market_id: str, side: str) -> None:
        """Stake the attached value on one side of the question."""
        if market_id not in self.pools:
            raise gl.vm.UserError("no pool for this market")

        side = side.strip().upper()
        if side != YES and side != NO:
            raise gl.vm.UserError("side must be YES or NO")

        amount = int(gl.message.value)
        if amount <= 0:
            raise gl.vm.UserError("a stake must carry value")

        pool = self.pools[market_id]
        if pool.settled:
            raise gl.vm.UserError("pool is already settled")

        # The book closes on the clock, not on an observed status change. A
        # status check alone would let whoever reads the source first stake and
        # then resolve in the next transaction, with nobody able to follow.
        if _epoch_seconds(gl.message_raw["datetime"]) >= int(pool.closes_at):
            raise gl.vm.UserError("staking has closed for this market")

        who = gl.message.sender_address.as_hex

        if who.lower() == str(pool.creator):
            raise gl.vm.UserError("the market creator cannot stake on their own market")

        key = _stake_key(market_id, who)
        is_new_backer = key not in self.stake_yes and key not in self.stake_no

        if side == YES:
            self.stake_yes[key] = u256(int(self.stake_yes.get(key, u256(0))) + amount)
            pool.total_yes = u256(int(pool.total_yes) + amount)
        else:
            self.stake_no[key] = u256(int(self.stake_no.get(key, u256(0))) + amount)
            pool.total_no = u256(int(pool.total_no) + amount)

    @gl.public.write
    def settle(self, market_id: str) -> None:
        """Read the final verdict and fix the pool's result. Anyone may call."""
        if market_id not in self.pools:
            raise gl.vm.UserError("no pool for this market")

        pool = self.pools[market_id]
        if pool.settled:
            raise gl.vm.UserError("pool is already settled")

        oracle = gl.get_contract_at(self.oracle)
        reader = oracle.view(state=StorageType.LATEST_FINAL)

        market = reader.get_market(market_id)
        if _field(market, "status") != FINAL:
            raise gl.vm.UserError("verdict is not final on finalized chain state yet")

        outcome = str(reader.final_outcome(market_id))

        pool.by_timeout = _field(market, "expired") in ("True", "true", "1")
        _was_read = bool(_field(market, "resolved_outcome")) or not pool.by_timeout
        pool.source_moved = _was_read and _field(market, "source_changed") in ("True", "true", "1")
        pool.source_moved_known = _was_read

        effective = outcome
        appeal_denied = False
        disputed = bool(_field(market, "disputer"))
        if outcome == UNRESOLVED and disputed:
            prior = _field(market, "resolved_outcome")
            if prior == YES or prior == NO:
                effective = prior
                appeal_denied = True
        elif disputed and _field(market, "expired") in ("True", "true", "1"):
            appeal_denied = True
        total_yes = int(pool.total_yes)
        total_no = int(pool.total_no)

        if effective == UNRESOLVED:
            result = REFUND
        elif effective == YES and total_yes > 0 and total_no > 0:
            result = YES
        elif effective == NO and total_yes > 0 and total_no > 0:
            result = NO
        else:
            result = REFUND

        pool.result = result
        pool.by_appeal_denied = appeal_denied
        pool.settled = True
        pool.settled_at = gl.message_raw["datetime"]

        print(f"settled {market_id} -> oracle {outcome}, effective {effective}, result {result}")

    @gl.public.write
    def claim(self, market_id: str) -> None:
        """Withdraw whatever the caller is owed. Pull-based, once per address."""
        if market_id not in self.pools:
            raise gl.vm.UserError("no pool for this market")

        pool = self.pools[market_id]
        if not pool.settled:
            raise gl.vm.UserError("pool is not settled yet")

        who = gl.message.sender_address.as_hex
        key = _stake_key(market_id, who)

        if self.claimed.get(key, False):
            raise gl.vm.UserError("already claimed")

        mine_yes = int(self.stake_yes.get(key, u256(0)))
        mine_no = int(self.stake_no.get(key, u256(0)))
        if mine_yes == 0 and mine_no == 0:
            raise gl.vm.UserError("nothing staked on this market")

        result = str(pool.result)
        total_yes = int(pool.total_yes)
        total_no = int(pool.total_no)
        pot = total_yes + total_no

        if result == REFUND:
            amount = mine_yes + mine_no
        elif result == YES:
            amount = mine_yes * pot // total_yes
        else:
            amount = mine_no * pot // total_no

        self.claimed[key] = True

        if amount > 0:
            gl.get_contract_at(gl.message.sender_address).emit_transfer(
                value=u256(amount), on="finalized"
            )

        print(f"claim {market_id} {who} -> {amount}")

    # ----------------------------------------------------------------- views

    @gl.public.view
    def get_pool(self, market_id: str) -> Pool:
        if market_id not in self.pools:
            raise gl.vm.UserError("no pool for this market")
        return self.pools[market_id]

    @gl.public.view
    def get_pools(self) -> dict:
        return {k: v for k, v in self.pools.items()}

    @gl.public.view
    def get_ids(self) -> list:
        return [str(i) for i in self.ids]

    @gl.public.view
    def oracle_address(self) -> str:
        return self.oracle.as_hex

    @gl.public.view
    def position(self, market_id: str, who: str) -> dict:
        """What one address staked, and what it can withdraw."""
        if market_id not in self.pools:
            raise gl.vm.UserError("no pool for this market")

        pool = self.pools[market_id]
        key = _stake_key(market_id, who)
        mine_yes = int(self.stake_yes.get(key, u256(0)))
        mine_no = int(self.stake_no.get(key, u256(0)))

        entitlement = 0
        if pool.settled and not self.claimed.get(key, False):
            result = str(pool.result)
            total_yes = int(pool.total_yes)
            total_no = int(pool.total_no)
            pot = total_yes + total_no
            if result == REFUND:
                entitlement = mine_yes + mine_no
            elif result == YES and total_yes > 0:
                entitlement = mine_yes * pot // total_yes
            elif result == NO and total_no > 0:
                entitlement = mine_no * pot // total_no

        return {
            "market_id": market_id,
            "question": str(pool.question),
            "criteria": str(pool.criteria),
            "source_url": str(pool.source_url),
            "address": who,
            "staked_yes": str(mine_yes),
            "staked_no": str(mine_no),
            "provenance": str(pool.provenance),
            "baseline_digest": str(pool.baseline_digest),
            "settled_by_timeout": bool(pool.by_timeout),
            "settled_by_appeal_denied": bool(pool.by_appeal_denied),
            "settled": bool(pool.settled),
            "result": str(pool.result),
            "entitlement": str(entitlement),
            "claimed": bool(self.claimed.get(key, False)),
        }


