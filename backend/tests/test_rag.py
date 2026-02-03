import os
import sys
import shutil
import unittest
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.rag import VectorStoreManager

# Load Env
load_dotenv()

class TestRAG(unittest.TestCase):
    def setUp(self):
        # Create a temp directory for test data
        self.test_dir = "./backend/tests/data_rag_test"
        self.chroma_dir = "./backend/tests/chroma_test"
        
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        
        if os.path.exists(self.chroma_dir):
            shutil.rmtree(self.chroma_dir)
            
        # Create a sample file
        self.sample_file = os.path.join(self.test_dir, "space_facts.txt")
        with open(self.sample_file, "w") as f:
            f.write("The quick brown fox jumps over the lazy dog.\n")
            f.write("Gemini is a constellation in the northern celestial hemisphere.\n")
            f.write("Gravity is a fundamental interaction which causes mutual attraction between all things with mass or energy.\n")

    def tearDown(self):
        # Cleanup
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        # Note: Cleaning up chroma_dir might be tricky if the process holds a lock.
        # Ideally we clean it up, but for now we leave it or handle it carefully.
        
    def test_ingest_and_search(self):
        print("\nTesting RAG Ingestion & Search...")
        
        rag = VectorStoreManager(persistence_dir=self.chroma_dir)
        
        # 1. Ingest
        result = rag.ingest_directory(self.test_dir)
        print(f"Ingest Result: {result}")
        self.assertIn("Successfully indexed", result)
        
        # 2. Search
        # Query semantically relates to the Space Fact
        query = "What pulls objects together?"
        context = rag.similarity_search(query, k=1)
        
        print(f"Search Result for '{query}':\n{context}")
        
        # Expecting to find the definition of Gravity
        self.assertIn("Gravity is a fundamental interaction", context)

if __name__ == '__main__':
    unittest.main()
