import os
from dotenv import load_dotenv
load_dotenv()

import vertexai
from vertexai.preview import rag

vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("RAG_LOCATION")
)

corpus = os.getenv("RAG_CORPUS")

# List all files
files = list(rag.list_files(corpus_name=corpus))

# Group by display name
from collections import defaultdict
by_name = defaultdict(list)
for f in files:
    by_name[f.display_name].append(f)

# Show what we've got
for name, versions in sorted(by_name.items()):
    print(f"{name}: {len(versions)} copies")

# Delete older duplicates (keep the latest)
deleted = 0
for name, versions in by_name.items():
    if len(versions) > 1:
        # Sort by name (contains timestamp), keep last
        versions.sort(key=lambda f: f.name)
        for old in versions[:-1]:
            print(f"  Deleting dupe: {old.name}")
            rag.delete_file(name=old.name, corpus_name=corpus)
            deleted += 1

print(f"\nDone. Deleted {deleted} duplicates.")