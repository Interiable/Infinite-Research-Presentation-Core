
import os
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

# Force the model name to what we just pulled
model_name = "llama4:scout"

print(f"🧪 Testing Model: {model_name}...")

try:
    llm = ChatOllama(
        model=model_name,
        temperature=0.7
    )
    
    prompt = "Hello! Are you functioning correctly? Please reply with a short poem about AI."
    print(f"📤 Sending prompt: {prompt}")
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    print("\n📥 Model Response:")
    print("-" * 50)
    print(response.content)
    print("-" * 50)
    print("\n✅ Test Complete: Model is working.")
    
except Exception as e:
    print(f"\n❌ Test Failed: {e}")
