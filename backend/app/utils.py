import os
import datetime

def save_artifact(name: str, content: str, extension: str = "md"):
    """
    Saves content to the 'artifacts' directory with a timestamp.
    """
    # Create artifacts dir if not exists
    base_dir = os.path.join(os.getcwd(), "artifacts")
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        
    # Timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Clean filename
    clean_name = name.replace(" ", "_").lower()
    
    filename = f"{timestamp}_{clean_name}.{extension}"
    filepath = os.path.join(base_dir, filename)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Artifact saved: {filepath}")
        return filepath
    except Exception as e:
        print(f"❌ Failed to save artifact: {e}")
        return None
