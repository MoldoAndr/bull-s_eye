#!/usr/bin/env python3
"""
Quick validation script for Bull's Eye configuration
"""

import sys
import os

# Add worker to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'worker'))

def main():
    print("=" * 50)
    print("Bull's Eye Configuration Validation")
    print("=" * 50)
    
    try:
        from config import settings, get_available_models
        print("✓ Config loaded successfully")
        print(f"  - Database: {settings.database_path}")
        print(f"  - Redis: {settings.redis_url}")
        print(f"  - Ollama API: {settings.ollama_api_url}")
        print(f"  - Default Model: {settings.ollama_model}")
        print(f"  - API Key Set: {'Yes' if settings.ollama_api_key else 'No'}")
        print(f"  - Available Models: {len(get_available_models())}")
    except Exception as e:
        print(f"✗ Config error: {e}")
        return 1
    
    try:
        from database import Database
        db = Database()
        print("✓ Database manager initialized")
    except Exception as e:
        print(f"✗ Database error: {e}")
        return 1
    
    try:
        from llm import OllamaCloudClient, get_ollama_client
        print("✓ LLM client imports OK")
    except Exception as e:
        print(f"✗ LLM import error: {e}")
        return 1
    
    try:
        from analysis import AnalysisEngine, ComponentDetector
        print("✓ Analysis engine imports OK")
    except Exception as e:
        print(f"✗ Analysis import error: {e}")
        return 1
    
    try:
        from scanners import get_universal_scanners, get_scanner_for_language
        scanners = get_universal_scanners()
        print(f"✓ Scanners loaded: {len(scanners)} universal scanners")
    except Exception as e:
        print(f"✗ Scanners error: {e}")
        return 1
    
    print("\n" + "=" * 50)
    print("All checks passed! ✓")
    print("=" * 50)
    return 0

if __name__ == "__main__":
    sys.exit(main())
