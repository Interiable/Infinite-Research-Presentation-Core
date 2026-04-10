
import os
import sys

# Adjust path to include backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.utils.academic_researcher import AcademicResearcher

def test_init():
    print("Testing AcademicResearcher Initialization...")
    academic = AcademicResearcher()
    print(f"Output Directory: {academic.output_dir}")
    
    if os.path.isabs(academic.output_dir):
        print("✅ Path is absolute.")
    else:
        print("❌ Path is relative.")
        
    if os.path.exists(academic.output_dir):
        print("✅ Directory created.")
    else:
        print("❌ Directory NOT created.")

if __name__ == "__main__":
    test_init()
