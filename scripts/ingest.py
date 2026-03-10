import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import vertexai
from vertexai.preview import rag

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
RAG_LOCATION = os.getenv("RAG_LOCATION", "us-west1")
CORPUS_DISPLAY_NAME = "museum-exhibits"
EXHIBITS_DIR = Path(__file__).parent.parent / "data" / "exhibits"

def get_or_create_corpus():
    vertexai.init(project=PROJECT, location=RAG_LOCATION)
    
    # Check if corpus already exists
    corpora = rag.list_corpora()
    for corpus in corpora:
        if corpus.display_name == CORPUS_DISPLAY_NAME:
            print(f"Found existing corpus: {corpus.name}")
            return corpus
    
    # Create new corpus
    corpus = rag.create_corpus(display_name=CORPUS_DISPLAY_NAME)
    print(f"Created new corpus: {corpus.name}")
    return corpus

def ingest_exhibits(corpus):
    exhibit_files = list(EXHIBITS_DIR.glob("*.md"))
    
    if not exhibit_files:
        print("No exhibit files found in data/exhibits/")
        sys.exit(1)
    
    print(f"Found {len(exhibit_files)} exhibit files")
    
    for exhibit_file in exhibit_files:
        print(f"Ingesting: {exhibit_file.name}")
        
        rag.upload_file(
            corpus_name=corpus.name,
            path=str(exhibit_file),
            display_name=exhibit_file.stem,
            description=f"Exhibit data for {exhibit_file.stem}"
        )
        
        print(f"  ✅ {exhibit_file.name} ingested")
    
    print(f"\nAll exhibits ingested into corpus: {corpus.name}")
    print(f"Save this corpus name — you'll need it in .env:")
    print(f"RAG_CORPUS={corpus.name}")

if __name__ == "__main__":
    print(f"Project: {PROJECT}")
    print(f"RAG Location: {RAG_LOCATION}")
    print(f"Exhibits dir: {EXHIBITS_DIR}")
    print()
    
    corpus = get_or_create_corpus()
    ingest_exhibits(corpus)
