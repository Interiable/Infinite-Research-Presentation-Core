
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Adjust path to include backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.state import AgentState
from langchain_core.messages import HumanMessage, SystemMessage

class TestDeepSeekIntegration(unittest.TestCase):
    
    @patch('app.agents.researcher.local_llm')
    @patch('app.agents.researcher.local_deepseek')
    @patch('app.agents.researcher.llm_flash')
    def test_scientific_specialist_trigger(self, mock_flash, mock_deepseek, mock_local_llm):
        """
        Verifies that 'formula' keyword triggers DeepSeek-R1 and mirroring works.
        """
        # Setup Mocks
        mock_flash.invoke.return_value = MagicMock(content="YES") # Flash confirms complexity
        mock_deepseek.invoke.return_value = MagicMock(content="[DERIVED FORMULA: F=ma]") # DeepSeek returns notes
        mock_local_llm.invoke.return_value = MagicMock(content="Final Report Content") # Qwen3 writes report
        
        # Setup State with Technical Keyword
        state = {
            "plan": [{"description": "Derive the mathematical formula for DMP."}],
            "current_step_index": 0,
            "research_topic": "Dynamic Movement Primitives",
            "local_knowledge": "File A content...",
            "incremental_report_path": "/tmp/mock_report.md", 
            "shared_knowledge": "RESEARCH NOTES: Web data...",
            "messages": [HumanMessage(content="Start")]
        }
        
        # Mock file operations to avoid errors
        with patch('builtins.open', unittest.mock.mock_open(read_data="# Initial Report")):
            with patch('os.path.exists', return_value=True):
                # Import here to avoid early init issues, but we patched the globals
                from app.agents.researcher import researcher_node
                
                # Execute
                result = researcher_node(state, {"configurable": {"thread_id": "test"}})
                
                # VERIFICATION 1: Flash was called to check complexity
                print("\n[Audit] Checking Flash Complexity Check...")
                args, _ = mock_flash.invoke.call_args
                print(f"   -> Flash Prompt: {args[0][0].content[:50]}...")
                self.assertIn("Does this task require complex mathematical", args[0][0].content)
                
                # VERIFICATION 2: DeepSeek was called
                print("[Audit] Checking DeepSeek-R1 Reasoning Call...")
                mock_deepseek.invoke.assert_called_once()
                args, _ = mock_deepseek.invoke.call_args
                sent_context = args[0][1].content
                
                # VERIFICATION 3: Context Mirroring (The Critical Check)
                print("[Audit] Verifying Context Mirroring...")
                self.assertIn("File A content...", sent_context, "Local knowledge missing from DeepSeek context")
                self.assertIn("# Initial Report", sent_context, "Master report history missing from DeepSeek context")
                self.assertIn("RESEARCH NOTES: Web data", sent_context, "Web research notes missing from DeepSeek context")
                print("   -> All context sources confirmed present in DeepSeek input.")
                
                # VERIFICATION 4: Injection into Qwen3
                print("[Audit] Verifying Injection into Lead Writer (Qwen3)...")
                # Qwen3 is called multiple times (TOC, Filtering, Drafting). 
                # We check the DRAFTING call (which is likely the last one or close to it)
                # We search all calls for the injected note
                found_injection = False
                for call in mock_local_llm.invoke.call_args_list:
                    # Arg 0 is list of messages, Message 1 is HumanMessage
                    if len(call[0][0]) > 1:
                        prompt_content = call[0][0][1].content
                        if "[CRITICAL] SCIENTIFIC SPECIALIST NOTES" in prompt_content:
                            found_injection = True
                            self.assertIn("[DERIVED FORMULA: F=ma]", prompt_content)
                            break
                
                self.assertTrue(found_injection, "DeepSeek reasoning notes were NOT injected into Qwen3's prompt.")
                print("   -> DeepSeek notes successfully found in Qwen3 context.")

if __name__ == '__main__':
    unittest.main()
