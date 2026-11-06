import math
from collections import Counter, defaultdict

MIN_SHARE = 0.10  # term must appear in at least 10% of the clause's examples
MIN_CONTRACTS = 5  # and in at least 5 different contracts
MIN_LIFT = 3.0  # and be at least 3x more common there than elsewhere
EPS = 0.005


def learn_terms(conn, top=10, holdout=None):
    """Distinctive word stems per clause, learned from the example bank only.
    holdout: an SQL condition on contracts (alias c); matching contracts are left out.
    Returns {clause name: [(stem, share), ...]}."""
    where = "h.embedding IS NOT NULL"
    if holdout:
        where += f" AND NOT ({holdout})"
    rows = conn.execute(
        "SELECT cl.name, h.contract_id, tsvector_to_array(to_tsvector('english', h.text)) "
        "FROM highlights h JOIN clauses cl ON cl.id = h.clause_id "
        "JOIN contracts c ON c.id = h.contract_id "
        f"WHERE {where}"
    ).fetchall()

    n = Counter()
    df = defaultdict(Counter)
    total_df = Counter()
    contracts = defaultdict(lambda: defaultdict(set))
    for name, contract_id, terms in rows:
        n[name] += 1
        for t in set(terms):
            df[name][t] += 1
            total_df[t] += 1
            contracts[name][t].add(contract_id)
    total_n = sum(n.values())

    result = {}
    for name in n:
        scored = []
        for t, c in df[name].items():
            share = c / n[name]
            if share < MIN_SHARE or len(contracts[name][t]) < MIN_CONTRACTS or t.isdigit():
                continue
            other = (total_df[t] - c) / (total_n - n[name])
            lift = (share + EPS) / (other + EPS)
            if lift >= MIN_LIFT:
                scored.append((share * math.log(lift), t, share))
        scored.sort(reverse=True)
        result[name] = [(t, share) for _, t, share in scored[:top]]
    return result
