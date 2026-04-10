
try:
    from ddgs import DDGS
    print(f"Successfully imported DDGS: {DDGS}")
    # Try to instantiate to trigger lazy loading
    instance = DDGS()
    print(f"Successfully instantiated DDGS: {instance}")
except Exception as e:
    print(f"Failed to import/instantiate DDGS: {e}")
except ImportError as e:
    print(f"ImportError: {e}")
