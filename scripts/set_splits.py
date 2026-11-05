import json
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def company(title: str) -> str:
    return title.split("_")[0]


def test_titles(path: str="data/test.json") -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [c["title"] for c in json.load(f)["data"]]


def main() -> None:
    titles = test_titles()
    companies = sorted({company(t) for t in titles})

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(
            "UPDATE contracts "
            "SET official_split = CASE WHEN title = ANY(%s) THEN 'test' ELSE 'train' END",
            (titles,),
        )
        conn.execute(
            "UPDATE contracts "
            "SET shares_company_with_test = (official_split = 'train' AND company = ANY(%s))",
            (companies,),
        )
        rows = conn.execute(
            "SELECT official_split, shares_company_with_test, count(*) "
            "FROM contracts GROUP BY 1, 2 ORDER BY 1, 2"
        ).fetchall()

    for split, shared, n in rows:
        print(split, shared, n)


if __name__ == "__main__":
    main()
