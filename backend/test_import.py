import sys
sys.path.insert(0, ".")
try:
    from services.executive_agent_service import ExecutiveAgent
    from utils.intent_router import IntentRouter
    print("Import OK - all modules load correctly")
except Exception as e:
    print(f"Import ERROR: {e}")
    import traceback
    traceback.print_exc()
