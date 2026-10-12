import psycopg2

CONN_INFO = "host=localhost port=5433 dbname=at_data_db user=vlada password=abc"

import os

def loadFiles(folder="files"):
    for name in os.listdir(folder):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            text = f.read()

        page = name[:-3]                    # aboutus.md -> aboutus
        for part in text.split("\n#"):      # each heading starts a section
            lines = part.strip().lstrip("#").strip().split("\n", 1)
            if len(lines) < 2:              # heading without text: skip
                continue
            title, context = lines
            insertInfo(page, title.strip(), context.strip())

def getDbCon():
    return psycopg2.connect(CONN_INFO)

def insertInfo(page, title, context):
    try:
        conn = psycopg2.connect(CONN_INFO)
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO at_data (page, title, context)
            VALUES (%s, %s, %s)
        """, (page, title, context))

        print("Information added!")

    except Exception as e:
        print("Error:", e)
    finally:
        print("finish")
        if cur:
            cur.close()
        if conn:
            conn.close()

# MAIN
if __name__ == "__main__":
    loadFiles()