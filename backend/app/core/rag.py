import os
import chromadb
from typing import List, Dict, Any

from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Loaders
from langchain_community.document_loaders import TextLoader, PDFMinerLoader, DirectoryLoader

class VectorStoreManager:
    def __init__(self, persistence_dir: str = None):
        if persistence_dir is None:
            # Resolve absolute path: app/core/rag.py -> app/core -> app -> backend
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            persistence_dir = os.path.join(base_dir, "data", "chroma_db")
        self.persistence_dir = persistence_dir
        self.embedding_model = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",  # Updated model name
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            task_type="retrieval_document"
        )
        
        self.vector_store = Chroma(
            persist_directory=self.persistence_dir,
            embedding_function=self.embedding_model,
            collection_name="research_vectors"
        )
        
        # Splitters - ENHANCED: Larger chunks for more context preservation
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,      # Increased from 1000 for more complete passages
            chunk_overlap=400,    # Increased from 200 for better continuity
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
        
        processed_chunk_count = 0
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
                            # --- v3.9 Pre-emptive PDF Repair ---
                            from app.utils.pdf_repair import repair_pdf
                            repair_pdf(file_path) # Fix hex/font errors at the source
                            
                            loader = PDFMinerLoader(file_path)
                            current_docs = loader.load()
                        else:
                            # Generic text loader
                            loader = TextLoader(file_path, encoding='utf-8', autodetect_encoding=True)
                            current_docs = loader.load()
                            
                        documents.extend(current_docs)
                        
                        # --- BATCH PROCESSING (Fix OOM) ---
                        if len(documents) >= 10: # Process every 10 documents
                            print(f"✂️  RAG: Splitting & Indexing batch of {len(documents)} documents...")
                            chunks = self.text_splitter.split_documents(documents)
                            if chunks:
                                self.vector_store.add_documents(chunks)
                                processed_chunk_count += len(chunks)
                            documents = [] # Free memory
                            
                    except Exception as e:
                        print(f"⚠️ Failed to load {file}: {e}")
        
        # Process remaining documents
        if documents:
            print(f"✂️  RAG: Splitting & Indexing final batch of {len(documents)} documents...")
            chunks = self.text_splitter.split_documents(documents)
            if chunks:
                self.vector_store.add_documents(chunks)
                processed_chunk_count += len(chunks)
        
        return f"Successfully indexed {processed_chunk_count} chunks from {directory_path}."

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
