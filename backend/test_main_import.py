import sys
sys.path.insert(0, ".")
try:
    import main
    print("main.py import OK - backend can start")
except Exception as e:
    print(f"main.py import ERROR: {e}")
    import traceback
    traceback.print_exc()
