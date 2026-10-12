from fastapi import HTTPException
import requests

from local_db import getDbCon
from embedding import calcEmbed

CONN_INFO = "host=127.0.0.1 port=5433 dbname=at_data_db user=vlada password=abc"
OLLAMA_MODEL = "qwen3:1.7b"
BASE_URL = "http://127.0.0.1:8080"

def get_answer(query: str):
    payload = [query]
    response = requests.post(f"{BASE_URL}/at_data/answer", json=payload)
    assert response.status_code == 200
    answer = response.json()["answer"]
    print(query, ", answer: [", answer, "]")


def start(query: str, limit = 5):

    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        query_vector = calcEmbed(query)
        conn = getDbCon()
        cur = conn.cursor()
        cur.execute("""
                    SELECT context, context_vector <=> %s::vector AS distance
                    FROM at_data
                    WHERE context_vector <=> %s::vector < 0.5
                    ORDER BY context_vector <=> %s::vector
                    LIMIT %s
                    """, (query_vector, query_vector, query_vector, limit))
        rows = cur.fetchall()
        # print(rows) #debug

        contexts = [row[0] for row in rows]

        return contexts

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

# MAIN
if __name__ == "__main__":
    start("What is our company's specialization?")
    get_answer("When was company founded?")