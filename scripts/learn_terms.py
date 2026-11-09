
import psycopg
from dotenv import load_dotenv

from cuad_ai.settings import database_url
from cuad_ai.terms import learn_terms


def main():
    load_dotenv()
    with psycopg.connect(database_url()) as conn:
        result = learn_terms(conn)
    for name in sorted(result):
        words = ", ".join(f"{t} ({share:.0%})" for t, share in result[name])
        print(f"{name}: {words}\n")


if __name__ == "__main__":
    main()
