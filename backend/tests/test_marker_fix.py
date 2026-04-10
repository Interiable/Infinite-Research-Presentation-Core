
import os
import sys

# Adjust path to include backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.utils.academic_researcher import AcademicResearcher

def test_conversion():
    print("Testing Marker Conversion Flow...")
    academic = AcademicResearcher()
    
    # Use one of the PDFs that the user already has
    pdf_path = "/home/hgeon/gravity/LangAIAgent/backend/data/papers/Bodily_expressed_emotion_understanding_through_int.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ Test PDF not found: {pdf_path}")
        return

    result = academic.convert_pdf_to_markdown(pdf_path)
    
    if result:
        print("✅ Conversion successful!")
        print(f"Result Snippet (First 100 chars): {result[:100]}...")
    else:
        print("❌ Conversion failed.")

if __name__ == "__main__":
    test_conversion()
