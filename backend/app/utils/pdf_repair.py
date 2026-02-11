import os
import subprocess
import shutil

def repair_pdf(file_path: str) -> bool:
    """
    Attempts to repair a malformed PDF file using Ghostscript (gs).
    It re-distills the PDF, which often fixes structural errors like 
    'invalid hex string' or missing FontBBox descriptors.
    """
    if not shutil.which("gs"):
        print("⚠️ Ghostscript (gs) not found. Cannot repair PDF.")
        return False
        
    temp_repaired = file_path + ".repaired"
    
    # Ghostscript command to re-distill PDF
    # -dPDFSETTINGS=/prepress provides high-quality re-generation
    command = [
        "gs",
        "-o", temp_repaired,
        "-sDEVICE=pdfwrite",
        "-dPDFSETTINGS=/prepress",
        "-dBATCH",
        "-dNOPAUSE",
        "-q",  # Quiet mode
        file_path
    ]
    
    try:
        print(f"🔧 Attempting structural repair on: {os.path.basename(file_path)}...")
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(temp_repaired):
            # Check if at least some content was generated
            if os.path.getsize(temp_repaired) > 100:
                # Replace original with repaired version
                # Backup original just in case
                backup_path = file_path + ".bak"
                shutil.move(file_path, backup_path)
                shutil.move(temp_repaired, file_path)
                print(f"✅ Successfully repaired and replaced: {os.path.basename(file_path)}")
                return True
        else:
            print(f"❌ Repair failed for {file_path}: {result.stderr}")
            if os.path.exists(temp_repaired):
                os.remove(temp_repaired)
            return False
            
    except Exception as e:
        print(f"❌ Error during repair: {e}")
        if os.path.exists(temp_repaired):
            os.remove(temp_repaired)
        return False
    
    return False

def batch_repair_directory(directory_path: str):
    """
    Scans a directory for PDF files and attempts to repair them.
    """
    if not os.path.exists(directory_path):
        return
        
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith(".pdf") and not file.endswith(".bak"):
                file_path = os.path.join(root, file)
                repair_pdf(file_path)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if os.path.isdir(path):
            batch_repair_directory(path)
        else:
            repair_pdf(path)
