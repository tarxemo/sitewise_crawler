import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for local testing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')))

from sitewise_crawler import InsightEngine

class TestGroqKeyRotation(unittest.TestCase):
    def test_key_parsing(self):
        """Verify that comma-separated API keys are parsed correctly into a list."""
        api_keys_str = "gsk_key1, gsk_key2,gsk_key3 "
        engine = InsightEngine(api_key=api_keys_str)
        
        self.assertEqual(len(engine.api_keys), 3)
        self.assertEqual(engine.api_keys[0], "gsk_key1")
        self.assertEqual(engine.api_keys[1], "gsk_key2")
        self.assertEqual(engine.api_keys[2], "gsk_key3")

    def test_starting_index_randomization(self):
        """Verify that the initial key index is within the correct range."""
        api_keys_str = "gsk_key1,gsk_key2,gsk_key3,gsk_key4,gsk_key5"
        indices = set()
        for _ in range(100):
            engine = InsightEngine(api_key=api_keys_str)
            self.assertTrue(0 <= engine.current_key_index < 5)
            indices.add(engine.current_key_index)
            
        # Over 100 trials, we should hit multiple different start indices
        self.assertTrue(len(indices) > 1, f"Indices hit: {indices}")

    @patch('sitewise_crawler.analyzer.Groq')
    def test_client_property_backward_compatibility(self, mock_groq):
        """Verify that accessing engine.client dynamic property returns the correct Groq client."""
        mock_instance = MagicMock()
        mock_groq.return_value = mock_instance
        
        api_keys_str = "gsk_key1,gsk_key2"
        engine = InsightEngine(api_key=api_keys_str)
        
        # Test that engine.client resolves dynamically and correctly cache-initializes it
        client1 = engine.client
        mock_groq.assert_called_with(api_key=engine.api_keys[engine.current_key_index])
        
        # Call again to verify cached client is returned
        client2 = engine.client
        self.assertIs(client1, client2)

    @patch('sitewise_crawler.analyzer.Groq')
    def test_automatic_key_rotation_on_failure(self, mock_groq):
        """Verify that when a Groq API call fails, it rotates keys and retries."""
        import groq
        
        # We will set up 3 mock Groq instances
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()
        mock_client3 = MagicMock()
        
        # Client 1 will throw a RateLimitError
        mock_client1.chat.completions.create.side_effect = groq.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(),
            body=None
        )
        
        # Client 2 will throw a generic APIStatusError
        mock_client2.chat.completions.create.side_effect = groq.APIStatusError(
            message="Temporary service issues",
            response=MagicMock(),
            body=None
        )
        
        # Client 3 will succeed
        mock_choice = MagicMock()
        mock_choice.message.content = '{"status": "Safe", "risk_score": 0.1}'
        mock_client3.chat.completions.create.return_value.choices = [mock_choice]
        
        # Map our clients to mock_groq constructor calls
        clients_map = {
            "gsk_key1": mock_client1,
            "gsk_key2": mock_client2,
            "gsk_key3": mock_client3
        }
        
        def side_effect(api_key):
            return clients_map[api_key]
            
        mock_groq.side_effect = side_effect
        
        # Initialize engine with these 3 keys
        engine = InsightEngine(api_key="gsk_key1,gsk_key2,gsk_key3")
        
        # Force start index to 0 so we test the exact sequence: key1 -> key2 -> key3
        engine.current_key_index = 0
        
        # Execute chat completion call
        result = engine._call_chat_completions(
            messages=[{"role": "user", "content": "hello"}],
            model="llama-3.3-70b-versatile"
        )
        
        # Check that result is from the successful third client
        self.assertEqual(result.choices[0].message.content, '{"status": "Safe", "risk_score": 0.1}')
        
        # Check that completions were called on the first, second, and third client
        mock_client1.chat.completions.create.assert_called_once()
        mock_client2.chat.completions.create.assert_called_once()
        mock_client3.chat.completions.create.assert_called_once()
        
        # Index should now point to index 2 (gsk_key3) since it succeeded and was the last one used
        self.assertEqual(engine.current_key_index, 2)

    @patch('sitewise_crawler.analyzer.Groq')
    def test_all_keys_failure(self, mock_groq):
        """Verify that if all keys fail, a RuntimeError is raised."""
        import groq
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = groq.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(),
            body=None
        )
        mock_groq.return_value = mock_client
        
        engine = InsightEngine(api_key="gsk_key1,gsk_key2")
        
        with self.assertRaises(RuntimeError) as context:
            engine._call_chat_completions(
                messages=[{"role": "user", "content": "hello"}],
                model="llama-3.3-70b-versatile"
            )
            
        self.assertIn("All 2 Groq API keys failed", str(context.exception))

if __name__ == '__main__':
    unittest.main()
