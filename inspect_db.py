import sqlite3
conn = sqlite3.connect('/tmp/tmpirtr582e/test.db')
c = conn.cursor()
c.execute("SELECT * FROM turn_based_games")
print(c.fetchall())
conn.close()
