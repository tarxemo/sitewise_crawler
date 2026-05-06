import asyncio
import sys
import os
import json

# Add src to path for local testing
sys.path.append(os.path.join(os.getcwd(), 'src'))

from sitewise_crawler import InsightEngine, CrawlerConfig

async def test_analyzer():
    # Replace with your actual Groq API Key
    api_key = os.getenv("GROQ_API_KEY", "your-groq-api-key")
    
    if api_key == "your-groq-api-key":
        print("⚠️ Please set your GROQ_API_KEY environment variable to test the AI analyzer.")
        return

    print("🚀 Starting InsightEngine test...")
    engine = InsightEngine(api_key=api_key)
    
    # We use some fast, public URLs to simulate a user's browsing history
    urls_to_analyze = [
        "https://en.wikipedia.org/wiki/Machine_learning",
        "https://www.python.org/"
    ]
    
    try:
        # We can pass a custom CrawlerConfig to speed up the test (e.g., disable playwright)
        config = CrawlerConfig(start_url=urls_to_analyze[0], max_pages=len(urls_to_analyze), use_playwright=False)
        
        insight = await engine.analyze_user_behavior(
            user_id="test_user_001",
            urls=urls_to_analyze,
            crawler_config=config
        )
        
        print("\n✅ Analysis Complete! Here is the data ready for your database:\n")
        
        # Convert to dictionary and print as formatted JSON
        insight_dict = insight.model_dump(mode='json')
        print(json.dumps(insight_dict, indent=2))
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")

if __name__ == "__main__":
    asyncio.run(test_analyzer())
