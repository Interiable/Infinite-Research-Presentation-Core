
import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

print(f"🔑 Testing OpenAI Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")

try:
    print("🚀 Attempting to connect to model: gpt-5.2")
    llm = ChatOpenAI(
        model="gpt-5.2",
        temperature=0,
        api_key=api_key,
        model_kwargs={"reasoning": {"effort": "none"}}
    )
    
    response = llm.invoke("Hello, are you GPT-5.2? Reply with 'Yes' if you are.")
    print(f"✅ Success! Response:\n{response.content}")

except Exception as e:
    print(f"❌ Failed to connect to gpt-5.2: {e}")
    print("\n--- Troubleshooting ---")
    print("If this failed, 'gpt-5.2' might not be available to your key yet, or requires a different client setup.")
