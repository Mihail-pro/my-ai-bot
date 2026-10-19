from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import psycopg2
import ollama

from embedding import calcEmbed
from fastapi import Body
from typing import List, Dict

app = FastAPI()

CONN_INFO = "host=localhost port=5433 dbname=at_data_db user=vlada password=abc"
OLLAMA_MODEL = "qwen3:1.7b"


class PageInfo(BaseModel):
    page: str
    title: str
    context: str
    page_vector: List[float]
    title_vector: List[float]
    context_vector: List[float]


def getDbCon():
    return psycopg2.connect(CONN_INFO)


@app.get("/at_data/search")
def search_by_context(query: str = Query(...), limit: int = 5):
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


@app.get("/at_data/answer")
def generate_ollama_answer(question: str = Query(..., description="User's question")):
    try:
        query_vector = calcEmbed(question)

        conn = getDbCon()
        cur = conn.cursor()

        cur.execute("""
            SELECT context, context_vector <=> %s::vector AS distance
            FROM at_data
            WHERE context_vector <=> %s::vector < 0.5
            ORDER BY context_vector <=> %s::vector
            LIMIT 5
        """, (query_vector, query_vector, query_vector))

        rows = cur.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="No similar context found")

        combined_context = "\n".join([f"Chunk: {row[0]}" for row in rows])

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful and formal assistant. "
                        "Use the following context to answer the user's question. "
                        "Be concise and professional.\n\n"
                        f"Use only following context as factual informartion:\n{combined_context}"
                    )
                },
                {
                    "role": "user",
                    "content": question
                }
            ]
        )

        return {
            "question": question,
            "answer": response["message"]["content"].strip()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.post("/at_data/answer")
def generate_ollama_answer(messages: List[str] = Body(...)):
    print("Start generate_ollama_answer ", len(messages) if messages and len(messages) else "0", flush=True)
    cur = None
    try:
        history = messages[:-1]
        question = messages[-1]
        print(f"history: {history}", flush=True)  # DEBUG
        print(f"question: {question}", flush=True)  # DEBUG
        query_vector = calcEmbed(question)

        conn = getDbCon()
        cur = conn.cursor()

        cur.execute("""
            SELECT context, context_vector <=> %s::vector AS distance
            FROM at_data
            WHERE context_vector <=> %s::vector < 0.5
            ORDER BY context_vector <=> %s::vector
            LIMIT 5
        """, (query_vector, query_vector, query_vector))

        rows = cur.fetchall()
        if not rows:
            print(f"[ERROR] No similar context found for question {question}")
            raise HTTPException(status_code=500, detail="No similar context found")
            print("Please provide more information")

        combined_context = "\n".join([f"Chunk: {row[0]}" for row in rows])

        history_messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": msg}
                            for i, msg in enumerate(history)]
        history_messages.append({
            "role": "user",
            "content": question
        })

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                         {
                             "role": "system",
                             "content": (
                                 "You are a helpful and formal assistant. "
                                 "Use the following context to answer the user's question. "
                                 "Be concise and professional.\n\n"
                                 f"Use only following context as factual information:\n{combined_context}"
                             )
                         }
                     ] + history_messages
        )
        print("got response: ", response["message"]["content"].strip())

        return {
            "question": question,
            "answer": response["message"]["content"].strip()
        }

    except HTTPException:
        raise
    except Exception as e:
        print("HTTPException", str(e))
        raise HTTPException(status_code=500, detail=f"tol {str(e)}")
    finally:
        if cur:
            cur.close()
            conn.close()


@app.get("/at_data/")
def show_pages():
    try:
        conn = getDbCon()
        cur = conn.cursor()
        cur.execute("SELECT id, page, title, context, page_vector, title_vector, context_vector FROM at_data")
        rows = cur.fetchall()
        return [
            {
                "id": row[0], "page": row[1], "title": row[2], "context": row[3],
                "page_vector": row[4], "title_vector": row[5], "context_vector": row[6]
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.post("/at_data/", status_code=201)
def add_page(info: PageInfo):
    if not info.page.strip() or not info.title.strip() or not info.context.strip():
        raise HTTPException(status_code=400, detail="Fields must not be empty")

    try:
        conn = getDbCon()
        cur = conn.cursor()

        page_vector = calcEmbed(info.page)
        title_vector = calcEmbed(info.title)
        context_vector = calcEmbed(info.context)

        cur.execute("""
            INSERT INTO at_data (page, title, context, page_vector, title_vector, context_vector)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            info.page.strip(), info.title.strip(), info.context.strip(),
            page_vector, title_vector, context_vector
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        return {"message": "Added", "id": new_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.get("/at_data/{page_id}")
def get_page_by_id(page_id: int):
    try:
        conn = getDbCon()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, page, title, context, page_vector, title_vector, context_vector
            FROM at_data WHERE id = %s
        """, (page_id,))
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Record not found")

        return {
            "id": row[0], "page": row[1], "title": row[2], "context": row[3],
            "page_vector": row[4], "title_vector": row[5], "context_vector": row[6]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.put("/at_data/{page_id}")
def update_page(page_id: int, info: PageInfo):
    if not info.page.strip() or not info.title.strip() or not info.context.strip():
        raise HTTPException(status_code=400, detail="Fields must not be empty")

    try:
        conn = getDbCon()
        cur = conn.cursor()

        page_vector = calcEmbed(info.page)
        title_vector = calcEmbed(info.title)
        context_vector = calcEmbed(info.context)

        cur.execute("""
            UPDATE at_data
            SET page = %s, title = %s, context = %s,
                page_vector = %s, title_vector = %s, context_vector = %s
            WHERE id = %s
        """, (
            info.page.strip(), info.title.strip(), info.context.strip(),
            page_vector, title_vector, context_vector, page_id
        ))

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Data not found")

        conn.commit()
        return {"message": "Updated", "id": page_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.delete("/at_data/{page_id}")
def delete_page(page_id: int):
    try:
        conn = getDbCon()
        cur = conn.cursor()
        cur.execute("DELETE FROM at_data WHERE id = %s", (page_id,))

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Data not found")

        conn.commit()
        return {"message": "Deleted", "id": page_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()