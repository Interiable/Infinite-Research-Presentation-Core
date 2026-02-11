import os
import sys
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

def verify_deep_model():
    print("🔍 Starting Deep Research Model Verification...")
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY is not set.")
        return

    model_name = "gemini-3-pro-preview"
    print(f"📡 Attempting to connect to: {model_name}")
    
    try:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.2,
            google_api_key=api_key
        )
        
        test_prompt = "간략하게 'Deep Research 기능을 확인했습니다'라고 한국어로 답변해줘."
        print(f"💬 Sending test prompt: {test_prompt}")
        
        response = llm.invoke([HumanMessage(content=test_prompt)])
        
        print("\n✅ Verification Successful!")
        print(f"🤖 Model Response: {response.content}")
        
    except Exception as e:
        print(f"\n❌ Verification Failed: {str(e)}")
        if "404" in str(e) or "not found" in str(e).lower():
            print("⚠️ Note: The model name might be incorrect or restricted to your API key.")
        elif "429" in str(e):
            print("⚠️ Note: Quota limit reached.")
        else:
            print("⚠️ Please check your internet connection and API key permissions.")

if __name__ == "__main__":
    verify_deep_model()
