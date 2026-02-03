import os
import chromadb
from typing import List, Dict, Any

from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Loaders
from langchain_community.document_loaders import TextLoader, PyPDFLoader, DirectoryLoader

class VectorStoreManager:
    def __init__(self, persistence_dir: str = "./backend/data/chroma_db"):
        self.persistence_dir = persistence_dir
        self.embedding_model = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            task_type="retrieval_document"
        )
        
        self.vector_store = Chroma(
            persist_directory=self.persistence_dir,
            embedding_function=self.embedding_model,
            collection_name="research_vectors"
        )
        
        # Splitters
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )

    def ingest_directory(self, directory_path: str):
        """
        Scans a directory, chunks content, and adds to ChromaDB.
        Smartly skips hidden files and known garbage.
        """
        if not os.path.exists(directory_path):
            return f"Directory not found: {directory_path}"
            
        print(f"📚 RAG: Ingesting directory {directory_path}...")
        
        documents = []
        supported_exts = ['.md', '.txt', '.py', '.js', '.ts', '.tsx', '.json', '.html', '.css', '.pdf']
        
        # Walk and load
        for root, _, files in os.walk(directory_path):
            # Skip hidden folders, but allow the current directory '.'
            if any((part.startswith('.') and part != '.') or part in ['node_modules', 'venv', 'dist', 'build', '__pycache__'] for part in root.split(os.sep)):
                continue
                
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in supported_exts:
                    file_path = os.path.join(root, file)
                    try:
                        if ext == '.pdf':
                            loader = PyPDFLoader(file_path)
                            documents.extend(loader.load())
                        else:
                            # Generic text loader
                            loader = TextLoader(file_path, encoding='utf-8', autodetect_encoding=True)
                            documents.extend(loader.load())
                    except Exception as e:
                        print(f"⚠️ Failed to load {file}: {e}")
        
        if not documents:
            return "No valid documents found to index."
            
        # Chunking
        print(f"✂️  RAG: Splitting {len(documents)} documents...")
        chunks = self.text_splitter.split_documents(documents)
        
        if not chunks:
            return "No content chunks generated."

        # Add to Vector Store
        # Chroma handles upserting usually, but for simplicity we just add. 
        # Ideally we'd check for duplicates, but for MVP we might just clear or append.
        # Here we append.
        print(f"💾 RAG: Embedding & Storing {len(chunks)} chunks...")
        self.vector_store.add_documents(chunks)
        
        return f"Successfully indexed {len(chunks)} chunks from {directory_path}."

    def similarity_search(self, query: str, k: int = 5) -> str:
        """
        Returns a string context of the top-k most relevant chunks.
        """
        print(f"🔍 RAG: Searching for '{query}'...")
        results = self.vector_store.similarity_search(query, k=k)
        
        if not results:
            return "No relevant local documents found via vector search."
            
        context_parts = []
        for i, doc in enumerate(results):
            source = doc.metadata.get('source', 'Unknown')
            content = doc.page_content.replace('\n', ' ')
            context_parts.append(f"Source [{i+1}]: {source}\nContent: {content}\n")
            
        return "\n---\n".join(context_parts)

    def get_file_overviews(self) -> str:
        """
        Returns a high-level summary (filename + snippet) of what is in the store.
        Used for initial context setting so the agent knows what files exist.
        """
        # Limiting to avoid huge context, but getting distinct sources
        # Chroma doesn't facilitate "SELECT DISTINCT source" easily without SQL traversal,
        # but we can do a dummy search or track ingestion. 
        # For this MVP, we will rely on a 'list' of files if we just ingested, 
        # or we just do a broad empty search if possible (not recommended for vector stores).
        
        # Better approach for MVP: return the recently ingested file list if available,
        # or just advise the agent to search broadly.
        # But to truly solve the user's request, let's peek at the first 10 chunks to give a flavor.
        
        results = self.vector_store.similarity_search("Assign context labels", k=10)
        sources = set()
        overview_text = []
        
        for doc in results:
            src = doc.metadata.get('source', 'Unknown')
            if src not in sources:
                sources.add(src)
                snippet = doc.page_content[:200].replace('\n', ' ')
                overview_text.append(f"- File: {os.path.basename(src)}\n  Snippet: {snippet}...")
                
        if not overview_text:
            return "No files knowledge found yet."
            
        return "\n".join(overview_text)
