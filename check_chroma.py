import sqlite3
conn = sqlite3.connect('rag_db/chroma.sqlite3')
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [row[0] for row in cursor])
cursor = conn.execute("SELECT * FROM collections")
print("\nCollections:")
for row in cursor:
    print(f"  ID: {row[0]}")
    print(f"  Name: {row[1]}")
    print(f"  Dimension: {row[2]}")

cursor = conn.execute("SELECT * FROM segments")
print("\nSegments:")
for row in cursor:
    print(f"  ID: {row[0]}")
    print(f"  Type: {row[1]}")
    print(f"  Scope: {row[2]}")
    print(f"  Collection ID: {row[3]}")
    print()
