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
    def __init__(self, persistence_dir: str = None, project_id: str = "default"):
        if persistence_dir is None:
            # Resolve absolute path: app/core/rag.py -> app/core -> app -> backend
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            persistence_dir = os.path.join(base_dir, "data", "projects", project_id, "chroma_db")
        self.persistence_dir = persistence_dir
        self.embedding_model = GoogleGenerativeAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "models/text-embedding-004"),  # Updated model name
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
        Smartly skips hidden files, known garbage, and ALREADY INDEXED files.
        """
        if not os.path.exists(directory_path):
            return f"Directory not found: {directory_path}"
            
        print(f"📚 RAG: Scanning directory {directory_path} for new content...")
        
        # --- B3.17: DEDUPLICATION CHECK ---
        # Get all uniquely indexed sources to avoid redundant parsing
        try:
            existing_data = self.vector_store.get(include=['metadatas'])
            existing_sources = set(m.get('source') for m in existing_data.get('metadatas', []) if m and 'source' in m)
            print(f"   - Found {len(existing_sources)} existing files in index.")
        except Exception as e:
            print(f"   - Index empty or unavailable: {e}")
            existing_sources = set()

        processed_chunk_count = 0
        skipped_count = 0
        documents = []
        supported_exts = ['.md', '.txt', '.py', '.js', '.ts', '.tsx', '.json', '.html', '.css', '.pdf']
        
        # Walk and load
        for root, _, files in os.walk(directory_path):
            # Skip hidden folders...
            if any((part.startswith('.') and part != '.') or part in ['node_modules', 'venv', 'dist', 'build', '__pycache__'] for part in root.split(os.sep)):
                continue
                
            for file in files:
                ext = os.path.splitext(file)[1]
                if ext in supported_exts:
                    file_path = os.path.join(root, file)
                    
                    # --- DEDUPLICATION: Skip if already in index ---
                    if file_path in existing_sources:
                        skipped_count += 1
                        continue
                        
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

    def similarity_search(self, query: str, k: int = 100) -> str:
        """
        Returns a string context of the top-k most relevant chunks.
        Default k increased to 100 for Gemini 3 Pro context window.
        """
        print(f"🔍 RAG: Searching for '{query}' (k={k})...")
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
        Returns a high-level summary (filename) of ALL files in the store.
        Used for initial context setting so the agent knows EVERY file that exists.
        """
        try:
            # unleash: Get ALL metadata to list every file
            # Chroma 'get' allows fetching metadata without embeddings
            all_data = self.vector_store.get(include=['metadatas'])
            metadatas = all_data.get('metadatas', [])
            
            sources = set()
            for m in metadatas:
                if m and 'source' in m:
                    sources.add(m['source'])
            
            if not sources:
                return "No files indexed yet."
                
            # Sort for stability
            sorted_sources = sorted(list(sources))
            
            overview_text = ["**📚 FULL FILE INDEX (All Ingested Files):**"]
            for src in sorted_sources:
                overview_text.append(f"- {os.path.basename(src)} ({src})")
                
            return "\n".join(overview_text)
            
        except Exception as e:
            print(f"⚠️ Failed to get full file overview: {e}")
            return "Error retrieving file list."


# ==============================================================================
# v4.5: LOCAL PAPER LIBRARY (Academic Paper Vector DB)
# ==============================================================================
class PaperLibrary:
    """
    A dedicated vector database for accumulated academic papers (PDFs).
    Uses a separate ChromaDB collection from the main research_vectors.
    Enables semantic search across all downloaded papers for any research topic.
    """
    
    def __init__(self, papers_dir: str = None, persistence_dir: str = None, project_id: str = "default"):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self.papers_dir = papers_dir or os.path.join(base_dir, "data", "projects", project_id, "papers")
        
        if persistence_dir is None:
            persistence_dir = os.path.join(base_dir, "data", "projects", project_id, "chroma_paper_library")
        
        self.persistence_dir = persistence_dir
        self.embedding_model = GoogleGenerativeAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "models/text-embedding-004"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            task_type="retrieval_document"
        )
        
        self.vector_store = Chroma(
            persist_directory=self.persistence_dir,
            embedding_function=self.embedding_model,
            collection_name="paper_library"
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=400,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def _get_indexed_sources(self) -> set:
        """Returns set of already-indexed file paths."""
        try:
            existing_data = self.vector_store.get(include=['metadatas'])
            return set(
                m.get('source') for m in existing_data.get('metadatas', [])
                if m and 'source' in m
            )
        except Exception:
            return set()
    
    def _extract_pdf_text(self, pdf_path: str) -> str:
        """Extracts text from a PDF using pymupdf4llm (CPU-safe, no GPU needed)."""
        try:
            import pymupdf4llm
            text = pymupdf4llm.to_markdown(pdf_path)
            return text if text and len(text.strip()) > 50 else ""
        except Exception as e:
            print(f"   ⚠️ PDF extraction failed for {os.path.basename(pdf_path)}: {e}")
            return ""
    
    def index_papers_dir(self, papers_dir: str = None) -> str:
        """
        Indexes all PDFs in the papers directory into ChromaDB.
        Skips already-indexed files (deduplication).
        """
        target_dir = papers_dir or self.papers_dir
        if not os.path.exists(target_dir):
            return f"Papers directory not found: {target_dir}"
        
        existing_sources = self._get_indexed_sources()
        print(f"📚 Paper Library: Scanning {target_dir}...")
        print(f"   Already indexed: {len(existing_sources)} files")
        
        pdf_files = [f for f in os.listdir(target_dir) if f.lower().endswith('.pdf')]
        new_count = 0
        skip_count = 0
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(target_dir, pdf_file)
            
            # Dedup check
            if pdf_path in existing_sources:
                skip_count += 1
                continue
            
            # Extract text
            text = self._extract_pdf_text(pdf_path)
            if not text:
                continue
            
            # Truncate very large papers to 20k chars
            if len(text) > 20000:
                text = text[:20000] + "\n\n...(Truncated)..."
            
            # Create document with metadata
            paper_title = pdf_file.replace('.pdf', '').replace('_', ' ')
            doc = Document(
                page_content=text,
                metadata={
                    "source": pdf_path,
                    "title": paper_title,
                    "type": "academic_paper"
                }
            )
            
            # Split into chunks and index
            chunks = self.text_splitter.split_documents([doc])
            if chunks:
                try:
                    self.vector_store.add_documents(chunks)
                    new_count += 1
                    print(f"   ✅ Indexed: {pdf_file} ({len(chunks)} chunks)")
                except Exception as e:
                    print(f"   ⚠️ Indexing failed for {pdf_file}: {e}")
        
        summary = f"📚 Paper Library Complete: {new_count} new papers indexed, {skip_count} skipped (already indexed)."
        print(summary)
        return summary
    
    def index_single_paper(self, pdf_path: str) -> bool:
        """Indexes a single newly-downloaded paper into the library."""
        if not os.path.exists(pdf_path):
            return False
        
        existing = self._get_indexed_sources()
        if pdf_path in existing:
            return True  # Already indexed
        
        text = self._extract_pdf_text(pdf_path)
        if not text:
            return False
        
        if len(text) > 20000:
            text = text[:20000] + "\n\n...(Truncated)..."
        
        paper_title = os.path.basename(pdf_path).replace('.pdf', '').replace('_', ' ')
        doc = Document(
            page_content=text,
            metadata={
                "source": pdf_path,
                "title": paper_title,
                "type": "academic_paper"
            }
        )
        
        chunks = self.text_splitter.split_documents([doc])
        if chunks:
            try:
                self.vector_store.add_documents(chunks)
                print(f"   📚 Paper Library: Auto-indexed new paper: {paper_title}")
                return True
            except Exception as e:
                print(f"   ⚠️ Auto-indexing failed: {e}")
                return False
        return False
    
    def search_papers(self, query: str, k: int = 30) -> str:
        """
        Searches the paper library for papers related to the query.
        v5.2: Uses relevance score filtering instead of fixed k.
        Retrieves up to k candidates, then keeps only those with relevance >= threshold.
        """
        print(f"📚 Local Paper DB (Curated): Scanned for '{query[:80]}...' (k={k})...")
        
        RELEVANCE_THRESHOLD = 0.3  # Minimum cosine similarity (0~1, higher = more similar)
        
        try:
            # Use score-based search to filter by relevance
            results_with_scores = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
        except Exception as e:
            # Fallback: some vector stores don't support score-based search
            print(f"   ⚠️ Score-based search failed ({e}), falling back to standard search...")
            try:
                results = self.vector_store.similarity_search(query, k=k)
                results_with_scores = [(doc, 1.0) for doc in results]  # Assume all relevant
            except Exception as e2:
                print(f"   ⚠️ Paper Library search failed: {e2}")
                return ""
        
        if not results_with_scores:
            print("   📚 No relevant papers found in local library.")
            return ""
        
        # Filter by relevance threshold
        relevant_results = [(doc, score) for doc, score in results_with_scores if score >= RELEVANCE_THRESHOLD]
        
        if not relevant_results:
            print(f"   📚 {len(results_with_scores)} papers found but none above relevance threshold ({RELEVANCE_THRESHOLD}).")
            return ""
        
        # v10.3: Aggregate ALL relevant chunks per paper (not just the first one)
        # This gives the Writer full relevant context from each paper.
        MAX_CHARS_PER_PAPER = 4000
        paper_chunks = {}  # title -> { source, best_score, chunks[] }
        
        for doc, score in relevant_results:
            title = doc.metadata.get('title', 'Unknown Paper')
            source = doc.metadata.get('source', '')
            chunk_text = doc.page_content.strip()
            
            if title not in paper_chunks:
                paper_chunks[title] = {
                    'source': source,
                    'best_score': score,
                    'chunks': []
                }
            paper_chunks[title]['chunks'].append(chunk_text)
            # Keep the best (highest) relevance score
            if score > paper_chunks[title]['best_score']:
                paper_chunks[title]['best_score'] = score
        
        context_parts = []
        for title, info in paper_chunks.items():
            # Merge all chunks, deduplicate, and cap at MAX_CHARS_PER_PAPER
            merged = "\n\n".join(info['chunks'])
            if len(merged) > MAX_CHARS_PER_PAPER:
                merged = merged[:MAX_CHARS_PER_PAPER] + "\n...[truncated]"
            
            context_parts.append(
                f"### 📄 Local Paper: {title} (Relevance: {info['best_score']:.2f})\n"
                f"**Source**: {os.path.basename(info['source'])}\n"
                f"**Content**:\n{merged}\n"
            )
        
        if context_parts:
            total_chunks = sum(len(v['chunks']) for v in paper_chunks.values())
            print(f"   📚 Found {len(context_parts)} relevant papers ({total_chunks} chunks, threshold: {RELEVANCE_THRESHOLD}, from {len(results_with_scores)} candidates).")
            return "\n---\n".join(context_parts)
        
        return ""
    
    def search_papers_with_sources(self, query: str, k: int = 30, high_relevance_threshold: float = 0.5):
        """
        v11.0: Enhanced search that returns BOTH context text AND high-relevance source paths.
        Returns: (context_text: str, high_relevance_sources: List[dict])
        Each source dict: {"title": str, "score": float, "source_path": str}
        The Researcher can use source_path to read the full original PDF.
        """
        context_text = self.search_papers(query, k=k)
        
        high_relevance_sources = []
        try:
            results_with_scores = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
            
            # Deduplicate by source path, keep highest score per paper
            seen_sources = {}  # source_path -> {title, score}
            for doc, score in results_with_scores:
                if score < high_relevance_threshold:
                    continue
                source_path = doc.metadata.get('source', '')
                title = doc.metadata.get('title', 'Unknown')
                if not source_path or not os.path.exists(source_path):
                    continue
                if source_path not in seen_sources or score > seen_sources[source_path]['score']:
                    seen_sources[source_path] = {'title': title, 'score': score, 'source_path': source_path}
            
            # Sort by score descending
            high_relevance_sources = sorted(seen_sources.values(), key=lambda x: x['score'], reverse=True)
            
            if high_relevance_sources:
                print(f"   📖 Full-Text Candidates: {len(high_relevance_sources)} papers above {high_relevance_threshold} threshold")
                for s in high_relevance_sources[:5]:
                    print(f"      🏆 [{s['score']:.2f}] {s['title'][:60]}")
        except Exception as e:
            print(f"   ⚠️ search_papers_with_sources failed: {e}")
        
        return context_text, high_relevance_sources
    
    def get_stats(self) -> dict:
        """Returns statistics about the paper library."""
        try:
            all_data = self.vector_store.get(include=['metadatas'])
            metadatas = all_data.get('metadatas', [])
            sources = set(m.get('source') for m in metadatas if m and 'source' in m)
            return {
                "total_papers": len(sources),
                "total_chunks": len(metadatas),
                "papers": sorted([os.path.basename(s) for s in sources])
            }
        except Exception:
            return {"total_papers": 0, "total_chunks": 0, "papers": []}


# ==============================================================================
# v6.3: PATENT LIBRARY (Patent Search Results Vector DB)
# ==============================================================================

class PatentLibrary:
    """
    Dedicated vector database for patent search results.
    Stores patent abstracts/claims from BigQuery, USPTO, PatentsView, Lens.
    Enables semantic search across all accumulated patent data.
    """
    
    def __init__(self, persistence_dir: str = None, project_id: str = "default"):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        if persistence_dir is None:
            persistence_dir = os.path.join(base_dir, "data", "projects", project_id, "chroma_patent_library")
        
        self.persistence_dir = persistence_dir
        self.embedding_model = GoogleGenerativeAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "models/text-embedding-004"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            task_type="retrieval_document"
        )
        
        self.vector_store = Chroma(
            persist_directory=self.persistence_dir,
            embedding_function=self.embedding_model,
            collection_name="patent_library"
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=400,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def _get_indexed_patents(self) -> set:
        """Returns set of already-indexed patent IDs."""
        try:
            all_data = self.vector_store.get(include=['metadatas'])
            return set(m.get('patent_id', '') for m in all_data.get('metadatas', []) if m)
        except Exception:
            return set()
    
    def index_patents(self, patents: List[Dict]) -> int:
        """
        Indexes a list of patent result dicts into ChromaDB.
        Each dict should have: title, abstract, patent_number, applicants, etc.
        If 'full_text' is present (from Google Patents scraping), uses that for deeper indexing.
        Returns number of newly indexed patents.
        """
        if not patents:
            return 0
        
        existing_ids = self._get_indexed_patents()
        indexed_count = 0
        
        for patent in patents:
            patent_id = patent.get("patent_number", patent.get("lens_id", ""))
            if not patent_id or patent_id in existing_ids:
                continue
            
            title = patent.get("title", "Unknown Patent")
            abstract = patent.get("abstract", "")
            applicants = ", ".join(patent.get("applicants", [])) or "Unknown"
            inventors = ", ".join(patent.get("inventors", [])) or "Unknown"
            pub_date = patent.get("publication_date", "Unknown")
            source = patent.get("source", "Unknown")
            cpc = ", ".join(patent.get("cpc_codes", []))
            
            # v7.0: Use full_text if available (from Google Patents scraping)
            if patent.get("full_text"):
                full_text = patent["full_text"]
                source += " (Full-Text)"
            else:
                # Fallback: Build text from metadata
                full_text = f"Patent: {title}\n"
                full_text += f"Patent ID: {patent_id}\n"
                full_text += f"Applicants: {applicants}\n"
                full_text += f"Inventors: {inventors}\n"
                full_text += f"Published: {pub_date}\n"
                if cpc:
                    full_text += f"CPC Classification: {cpc}\n"
                if abstract:
                    full_text += f"Abstract: {abstract}\n"
            
            doc = Document(
                page_content=full_text[:80000],  # Allow larger content for full-text patents
                metadata={
                    "patent_id": patent_id,
                    "title": title,
                    "source_api": source,
                    "applicants": applicants,
                    "pub_date": pub_date,
                    "has_fulltext": bool(patent.get("full_text")),
                    "type": "patent"
                }
            )
            
            chunks = self.text_splitter.split_documents([doc])
            if chunks:
                try:
                    self.vector_store.add_documents(chunks)
                    indexed_count += 1
                except Exception as e:
                    print(f"   ⚠️ Patent indexing failed for {patent_id}: {e}")
        
        if indexed_count > 0:
            print(f"   📋 Patent Library: Indexed {indexed_count} new patents.")
        return indexed_count
    
    def search_patents(self, query: str, k: int = 20) -> str:
        """Searches patent library for related patents."""
        RELEVANCE_THRESHOLD = 0.3
        
        try:
            results_with_scores = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
        except Exception:
            try:
                results = self.vector_store.similarity_search(query, k=k)
                results_with_scores = [(doc, 1.0) for doc in results]
            except Exception:
                return ""
        
        if not results_with_scores:
            return ""
        
        relevant = [(doc, score) for doc, score in results_with_scores if score >= RELEVANCE_THRESHOLD]
        if not relevant:
            return ""
        
        seen_ids = set()
        parts = []
        for doc, score in relevant:
            pid = doc.metadata.get('patent_id', '')
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            
            title = doc.metadata.get('title', 'Unknown')
            excerpt = doc.page_content[:800].replace('\n', ' ')
            parts.append(
                f"### 📋 Patent: {title} (Relevance: {score:.2f})\n"
                f"**Patent ID**: {pid}\n"
                f"**Excerpt**: {excerpt}\n"
            )
        
        if parts:
            print(f"   📋 Patent Library: Found {len(parts)} relevant patents (threshold: {RELEVANCE_THRESHOLD}).")
            return "\n---\n".join(parts)
        return ""
    
    def search_patents_with_sources(self, query: str, k: int = 20, high_relevance_threshold: float = 0.5):
        """
        v11.0: Enhanced search that returns BOTH context text AND high-relevance source paths.
        Returns: (context_text: str, high_relevance_sources: List[dict])
        Each source dict: {"patent_id": str, "title": str, "score": float, "source_path": str}
        The Researcher can use source_path to read the full original JSON (claims, description).
        """
        import json as _json
        context_text = self.search_patents(query, k=k)
        
        high_relevance_sources = []
        # Patent JSON files are stored in data/patents/{normalized_id}.json
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        patents_dir = os.path.join(base_dir, "data", "patents")
        
        try:
            results_with_scores = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
            
            seen_ids = {}  # patent_id -> {title, score, source_path}
            for doc, score in results_with_scores:
                if score < high_relevance_threshold:
                    continue
                patent_id = doc.metadata.get('patent_id', '')
                title = doc.metadata.get('title', 'Unknown')
                if not patent_id:
                    continue
                
                # Find the JSON file for this patent
                json_path = os.path.join(patents_dir, f"{patent_id}.json")
                # Try alternative formats (with/without country prefix dashes)
                if not os.path.exists(json_path):
                    clean_id = patent_id.replace('-', '')
                    json_path = os.path.join(patents_dir, f"{clean_id}.json")
                
                if not os.path.exists(json_path):
                    continue
                
                if patent_id not in seen_ids or score > seen_ids[patent_id]['score']:
                    seen_ids[patent_id] = {
                        'patent_id': patent_id,
                        'title': title,
                        'score': score,
                        'source_path': json_path
                    }
            
            high_relevance_sources = sorted(seen_ids.values(), key=lambda x: x['score'], reverse=True)
            
            if high_relevance_sources:
                print(f"   📖 Full-Text Patent Candidates: {len(high_relevance_sources)} patents above {high_relevance_threshold} threshold")
                for s in high_relevance_sources[:5]:
                    print(f"      🏆 [{s['score']:.2f}] {s['patent_id']}: {s['title'][:60]}")
        except Exception as e:
            print(f"   ⚠️ search_patents_with_sources failed: {e}")
        
        return context_text, high_relevance_sources
    
    def get_stats(self) -> dict:
        try:
            all_data = self.vector_store.get(include=['metadatas'])
            metadatas = all_data.get('metadatas', [])
            patent_ids = set(m.get('patent_id') for m in metadatas if m and 'patent_id' in m)
            return {"total_patents": len(patent_ids), "total_chunks": len(metadatas)}
        except Exception:
            return {"total_patents": 0, "total_chunks": 0}


# ==============================================================================
# v6.3: WEB SEARCH LIBRARY (Tavily/Web Results Vector DB with TTL)
# ==============================================================================

class WebSearchLibrary:
    """
    Vector database for web search results (Tavily, DuckDuckGo, etc).
    Stores search snippets with a 7-day TTL for freshness.
    """
    
    TTL_DAYS = 7  # Results expire after 7 days
    
    def __init__(self, persistence_dir: str = None, project_id: str = "default"):
        import time
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        if persistence_dir is None:
            persistence_dir = os.path.join(base_dir, "data", "projects", project_id, "chroma_web_library")
        
        self.persistence_dir = persistence_dir
        self.embedding_model = GoogleGenerativeAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "models/text-embedding-004"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            task_type="retrieval_document"
        )
        
        self.vector_store = Chroma(
            persist_directory=self.persistence_dir,
            embedding_function=self.embedding_model,
            collection_name="web_search_library"
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=300,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def index_results(self, results: List[Dict], search_query: str = "") -> int:
        """
        Indexes Tavily/web search result dicts.
        Each dict should have: title, url, content.
        v7.0: If 'has_fulltext' is True, content may be full page text (up to 50KB).
        Returns number of newly indexed results.
        """
        import time
        if not results:
            return 0
        
        indexed_count = 0
        timestamp = int(time.time())
        
        for res in results:
            if not isinstance(res, dict):
                continue
            
            title = res.get('title', 'No Title')
            url = res.get('url', '')
            content = res.get('content', '')
            has_fulltext = res.get('has_fulltext', False)
            
            if not content or len(content) < 50:
                continue
            
            full_text = f"Title: {title}\nSource: {url}\nQuery: {search_query}\n\n{content}"
            
            # v7.0: Allow much larger content for full-text pages
            max_content = 80000 if has_fulltext else 4000
            
            doc = Document(
                page_content=full_text[:max_content],
                metadata={
                    "title": title,
                    "url": url,
                    "search_query": search_query[:200],
                    "indexed_at": timestamp,
                    "has_fulltext": has_fulltext,
                    "type": "web_search"
                }
            )
            
            chunks = self.text_splitter.split_documents([doc])
            if chunks:
                try:
                    self.vector_store.add_documents(chunks)
                    indexed_count += 1
                except Exception as e:
                    print(f"   ⚠️ Web result indexing failed: {e}")
        
        if indexed_count > 0:
            ft_count = sum(1 for r in results if isinstance(r, dict) and r.get('has_fulltext'))
            print(f"   🌐 Web Library: Indexed {indexed_count} results ({ft_count} with full-text).")
        return indexed_count
    
    def search(self, query: str, k: int = 20) -> str:
        """Searches web library, filtering out expired results."""
        import time
        RELEVANCE_THRESHOLD = 0.3
        cutoff = int(time.time()) - (self.TTL_DAYS * 86400)
        
        try:
            results_with_scores = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
        except Exception:
            try:
                results = self.vector_store.similarity_search(query, k=k)
                results_with_scores = [(doc, 1.0) for doc in results]
            except Exception:
                return ""
        
        if not results_with_scores:
            return ""
        
        # Filter by relevance AND TTL
        relevant = []
        for doc, score in results_with_scores:
            if score < RELEVANCE_THRESHOLD:
                continue
            indexed_at = doc.metadata.get('indexed_at', 0)
            if indexed_at >= cutoff:
                relevant.append((doc, score))
        
        if not relevant:
            return ""
        
        seen_urls = {}
        for doc, score in relevant:
            url = doc.metadata.get('url', '')
            title = doc.metadata.get('title', 'Unknown')
            chunk_text = doc.page_content.strip()
            
            if url not in seen_urls:
                seen_urls[url] = {
                    'title': title,
                    'best_score': score,
                    'chunks': []
                }
            seen_urls[url]['chunks'].append(chunk_text)
            if score > seen_urls[url]['best_score']:
                seen_urls[url]['best_score'] = score
                
        parts = []
        for url, info in seen_urls.items():
            # Merge all original text chunks and cap at 3000 chars to avoid prompt overflow,
            # but preserve enough original text for the LLM to read real data.
            merged = "\n...\n".join(info['chunks'])
            if len(merged) > 3000:
                merged = merged[:3000] + "\n...[truncated]"
                
            parts.append(
                f"### 🌐 Web: {info['title']} (Relevance: {info['best_score']:.2f})\n"
                f"**URL**: {url}\n"
                f"**Original Content**:\n{merged}\n"
            )
        
        if parts:
            print(f"   🌐 Web Library: Found {len(parts)} relevant web results (TTL: {self.TTL_DAYS}d).")
            return "\n---\n".join(parts)
        return ""
    
    def search_web_with_sources(self, query: str, k: int = 30, high_relevance_threshold: float = 0.3):
        """
        Returns: (context_text: str, high_relevance_sources: List[dict])
        Each source dict: {"title": str, "url": str, "score": float, "source_file": str, "content": str}
        """
        context_text = self.search(query, k=k)
        
        high_relevance_sources = []
        try:
            import time
            cutoff = int(time.time()) - (self.TTL_DAYS * 86400)
            results_with_scores = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
            
            seen_urls = {}
            for doc, score in results_with_scores:
                if score < high_relevance_threshold:
                    continue
                indexed_at = doc.metadata.get('indexed_at', 0)
                if indexed_at < cutoff:
                    continue
                    
                url = doc.metadata.get('url', '')
                title = doc.metadata.get('title', 'Unknown')
                source_file = doc.metadata.get('source', '') 
                if not url:
                    continue
                    
                if url not in seen_urls or score > seen_urls[url]['score']:
                    seen_urls[url] = {
                        'title': title, 
                        'url': url,
                        'score': score, 
                        'source_file': source_file,
                        'content': doc.page_content
                    }
                    
            high_relevance_sources = sorted(seen_urls.values(), key=lambda x: x['score'], reverse=True)
            
            if high_relevance_sources:
                print(f"   🌐 Web Candidates: {len(high_relevance_sources)} results above {high_relevance_threshold} threshold")
        except Exception as e:
            print(f"   ⚠️ Web source extraction failed: {e}")
            
        return context_text, high_relevance_sources
    
    def get_stats(self) -> dict:
        try:
            all_data = self.vector_store.get(include=['metadatas'])
            metadatas = all_data.get('metadatas', [])
            urls = set(m.get('url') for m in metadatas if m and 'url' in m)
            return {"total_results": len(urls), "total_chunks": len(metadatas)}
        except Exception:
            return {"total_results": 0, "total_chunks": 0}

# ==============================================================================
# v11.1: MEDIA SEARCH LIBRARY (YouTube API Vector DB)
# ==============================================================================

class MediaLibrary:
    """
    Dedicated vector database for media search results.
    Stores YouTube video transcripts and metadata.
    Enables semantic search across all accumulated media data.
    """
    
    def __init__(self, persistence_dir: str = None, project_id: str = "default"):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        if persistence_dir is None:
            persistence_dir = os.path.join(base_dir, "data", "projects", project_id, "chroma_media_library")
        
        self.persistence_dir = persistence_dir
        self.embedding_model = GoogleGenerativeAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "models/text-embedding-004"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            task_type="retrieval_document"
        )
        
        self.vector_store = Chroma(
            persist_directory=self.persistence_dir,
            embedding_function=self.embedding_model,
            collection_name="media_library"
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=400,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def _get_indexed_media(self) -> set:
        """Returns set of already-indexed video IDs."""
        try:
            all_data = self.vector_store.get(include=['metadatas'])
            return set(m.get('video_id', '') for m in all_data.get('metadatas', []) if m)
        except Exception:
            return set()
    
    def index_media(self, videos: List[Dict]) -> int:
        """
        Indexes a list of media result dicts into ChromaDB.
        Each dict should have: title, id (video_id), url, channel, content (transcript).
        Returns number of newly indexed media items.
        """
        if not videos:
            return 0
        
        existing_ids = self._get_indexed_media()
        indexed_count = 0
        
        for video in videos:
            video_id = video.get("id", "")
            if not video_id or video_id in existing_ids:
                continue
            
            title = video.get("title", "Unknown Title")
            channel = video.get("channel", "Unknown Channel")
            url = video.get("url", "")
            content = video.get("content", "")
            
            if not content or content == "No transcript available.":
                continue
            
            full_text = f"Title: {title}\n"
            full_text += f"Channel: {channel}\n"
            full_text += f"Video ID: {video_id}\n"
            full_text += f"URL: {url}\n\n"
            full_text += f"Transcript:\n{content}\n"
            
            doc = Document(
                page_content=full_text,
                metadata={
                    "video_id": video_id,
                    "title": title,
                    "channel": channel,
                    "url": url,
                    "type": "media"
                }
            )
            
            chunks = self.text_splitter.split_documents([doc])
            if chunks:
                try:
                    self.vector_store.add_documents(chunks)
                    indexed_count += 1
                except Exception as e:
                    print(f"   ⚠️ Media indexing failed for {video_id}: {e}")
        
        if indexed_count > 0:
            print(f"   🎬 Media Library: Indexed {indexed_count} new media transcripts.")
        return indexed_count
    
    def search_media(self, query: str, k: int = 20) -> str:
        """Searches media library for related YouTube transcripts."""
        RELEVANCE_THRESHOLD = 0.3
        
        try:
            results_with_scores = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
        except Exception:
            try:
                results = self.vector_store.similarity_search(query, k=k)
                results_with_scores = [(doc, 1.0) for doc in results]
            except Exception:
                return ""
        
        if not results_with_scores:
            return ""
        
        relevant = [(doc, score) for doc, score in results_with_scores if score >= RELEVANCE_THRESHOLD]
        if not relevant:
            return ""
        
        seen_ids = {}
        for doc, score in relevant:
            vid = doc.metadata.get('video_id', '')
            title = doc.metadata.get('title', 'Unknown Title')
            channel = doc.metadata.get('channel', 'Unknown')
            url = doc.metadata.get('url', '')
            chunk_text = doc.page_content.strip()
            
            if vid not in seen_ids:
                seen_ids[vid] = {
                    'title': title,
                    'channel': channel,
                    'url': url,
                    'best_score': score,
                    'chunks': []
                }
            seen_ids[vid]['chunks'].append(chunk_text)
            if score > seen_ids[vid]['best_score']:
                seen_ids[vid]['best_score'] = score
                
        parts = []
        for vid, info in seen_ids.items():
            # Merge all original transcript chunks and cap at 4000 chars to provide full context
            merged = "\n...\n".join(info['chunks'])
            if len(merged) > 4000:
                merged = merged[:4000] + "\n...[truncated]"
                
            parts.append(
                f"### 🎬 Media: {info['title']} (Relevance: {info['best_score']:.2f})\n"
                f"**Channel**: {info['channel']}\n"
                f"**URL**: {info['url']}\n"
                f"**Original Transcript**:\n{merged}\n"
            )
        
        if parts:
            print(f"   🎬 Media Library: Found {len(parts)} relevant video transcripts (threshold: {RELEVANCE_THRESHOLD}).")
            return "\n---\n".join(parts)
        return ""

