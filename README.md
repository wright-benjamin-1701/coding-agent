# coding-agent-v2

a coding agent designed for use with small LLMs

# todo:

1. add a series of tests for an AI to determine if it makes a good agent
2. still getting some json parsing errors (expecting or not expecting commas)
   → Ranking by relevance... ✓
   → Stage 2: Refining prompt... ✓
   ✓ Found 4 relevant files
   Refined: Suggest performance improvements for the Database class in database.py, focusing on SQLite3 operatio...
   🤖 Generating execution plan...
   Parse error: Expecting ',' delimiter: line 29 column 355 (char 4284)
   [
   {
   "tool": "explain_steps",
   "parameters": {
   "explanation": "I'll suggest performance improvements for the Database class focusing on SQLite3 optimizations:\n1. Optimize connection management with persistent connections\n2. Implement batch operations for schema initia...

   Refined: Analyze the Database class in database.py for potential performance improvements, focusing on SQLite...
   🤖 Generating execution plan...
   Parse error: Invalid \escape: line 19 column 186 (char 938)
   [
   {
   "tool": "explain_steps",
   "parameters": {
   "explanation": "I'll optimize the Database class in database.py for SQLite performance and improve JSON parsing in agent.py. Key steps include:\n1. Implement persistent SQLite connections with proper pooling\n2. Optimize qu...
