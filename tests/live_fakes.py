"""A fake embedding model, a fake language model and a tiny example bank, so the live review can be tested with no key."""
import hashlib
import json
import re

import numpy as np

from cuad_ai.embed import vector_literal
from cuad_ai.live import store, tenants

GOVERNING = "This Agreement shall be governed by and construed in accordance with the laws of the State of New York."
ASSIGN = "Neither party may assign this Agreement without the prior written consent of the other party."
CONTRACT = (
    "SERVICES AGREEMENT\n\nThis Services Agreement is made between Gamma Corp and Delta LLC.\n\n"
    +"The supplier shall provide the services described in Schedule A and invoice monthly. " * 30
    +"\n\nThis Agreement shall be governed   by the laws of the\nState of Delaware.\n\n"
    +"Neither party may assign this Agreement without prior written consent. " * 3
    +"\n\nThe fees are payable within thirty days of the invoice date. " * 20
)
DELAWARE = "This Agreement shall be governed by the laws of the State of Delaware."  # as the model quotes it


class FakeEmbedder:
    """Hashed bag of words, 384 numbers, unit length. Texts that share words are close."""

    def embed(self, texts):
        for text in texts:
            vector = np.zeros(384)
            for word in re.findall(r"[a-z]+", text.lower()):
                vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % 384] += 1.0
            norm = np.linalg.norm(vector)
            yield vector / norm if norm else vector


class FakeModel:
    """Stands in for call_model. `quotes` maps a clause to the passage the extractor returns for it;
    `judge1` and `judge2` are the raw replies of the two judges (default: both say yes)."""

    def __init__(self, quotes=None, judge1='{"is_this_clause": true, "looks_like": "none"}', judge2=None, fail=False):
        self.quotes = quotes or {}
        self.judge1, self.judge2, self.fail = judge1, judge2 or judge1, fail
        self.calls = []

    def __call__(self, prompt):
        self.calls.append(prompt)
        if self.fail:
            raise RuntimeError("model down")
        if "Return only a JSON object" in prompt:
            clause = re.search(r"Clause to find: (.*)", prompt).group(1).strip()
            quote = self.quotes.get(clause)
            text = json.dumps({"found": True, "quotes": [quote], "value": None}) if quote else \
                '{"found": false, "quotes": [], "value": null}'
        elif "Is the new quote the same kind of text" in prompt:
            text = self.judge2
        else:
            text = self.judge1
        return {"text": text, "tokens_in": 100, "tokens_out": 10, "seconds": 0.0, "attempts": 1}


def load_bank_rows(conn, embedder):
    """Two bank contracts (Acme, Beta) with one lawyer-marked example each, and four clauses."""
    for name in ("Governing Law", "Anti-Assignment", "Document Name", "Parties"):
        conn.execute("INSERT INTO clauses (name, question) VALUES (%s, %s)", (name, f"Find the {name} clause."))
    for title, company, clause, text in (("Acme_2019_x.txt", "Acme", "Governing Law", GOVERNING),
                                         ("Beta_2018_y.txt", "Beta", "Anti-Assignment", ASSIGN)):
        contract_id = conn.execute("INSERT INTO contracts (title, company, n_chars) VALUES (%s, %s, 1000) RETURNING id",
                                   (title, company)).fetchone()[0]
        clause_id = conn.execute("SELECT id FROM clauses WHERE name = %s", (clause,)).fetchone()[0]
        vector = vector_literal(next(iter(embedder.embed([text]))).tolist())
        conn.execute("INSERT INTO highlights (contract_id, clause_id, start_char, end_char, text, embedding) "
                     "VALUES (%s, %s, 0, %s, %s, %s::vector)", (contract_id, clause_id, len(text), text, vector))
    conn.commit()


T = "acme"  # the client the existing tests upload as


def submit(conn, filename, text, tenant=T, **kw):
    """Store an upload for a test client, creating the client first if it does not exist."""
    if tenants.get_tenant(conn, tenant) is None:
        tenants.create_tenant(conn, tenant, tenant.title())
    return store.submit(conn, tenant, filename, text, **kw)
