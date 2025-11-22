import subprocess
import sqlite3
import re

# PROMPTING STRATEGY EXPLANATION:

# Approach: Few-Shot Prompting with Schema Context
# 
# Rationale:
# - Small models (< 4B params) like Qwen2.5:1.5b benefit from concrete examples
# - Few-shot examples provide templates for JOIN operations and aggregations
# - Schema + examples help the model understand table relationships without fine-tuning
# - We include 2 examples: one simple SELECT, one JOIN with aggregation
# - Qwen2.5 was chosen over Phi-3 for superior SQL generation and structured output
# - This balances token efficiency with accuracy improvement
#
# Alternative Considered: Chain-of-Thought prompting was tested but increased
# response length without improving SQL accuracy for structured tasks.



OLLAMA_PATH = r"C:\Users\prana\AppData\Local\Programs\Ollama\ollama.exe"
MODEL_NAME = "qwen2.5:1.5b"  # 1.5B parameters 
DB_PATH = "ecommerce.db"
MAX_RETRIES = 3

# --- SCHEMA CONTEXT WITH FEW-SHOT EXAMPLES ---
SCHEMA_CONTEXT = """
Database Schema:
users: user_id, name, email, region, signup_date
products: product_id, product_name, category, price
orders: order_id, user_id, product_id, quantity, order_date

Example 1:
Question: Show all users from the North region
SQL: SELECT * FROM users WHERE region = 'North';

Example 2:
Question: Get total quantity sold for each product
SQL: SELECT p.product_name, SUM(o.quantity) as total_sold FROM products p JOIN orders o ON p.product_id = o.product_id GROUP BY p.product_id, p.product_name;

Rules: Use only these tables and columns. Return ONLY valid SQL."""

def run_ollama(prompt):
    """Calls the Ollama executable directly with the prompt."""
    try:
        result = subprocess.run(
            [OLLAMA_PATH, "run", MODEL_NAME, prompt],
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f" Ollama Error: {e.stderr}")
        return ""
    except FileNotFoundError:
        print(f" Error: Could not find Ollama at {OLLAMA_PATH}")
        return ""

def clean_sql(llm_output):
    """Extracts just the SQL code from the model's chatty response."""
    # 1. Remove Markdown code blocks (```sql ... ```)
    match = re.search(r"```sql\s*(.*?)\s*```", llm_output, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # 2. If no code blocks, try to find the first SELECT statement
    match = re.search(r"(SELECT.*?;?)", llm_output, re.DOTALL | re.IGNORECASE)
    if match:
        query = match.group(1).strip()
        # Ensure it ends with semicolon
        if not query.endswith(';'):
            query += ';'
        return query
        
    return llm_output.strip()

def validate_sql(sql_query):
    """
    The 'Judge'. Validates SQL with two checks:
    1. Forbidden keyword check (DROP, DELETE, etc.)
    2. Syntax validation using EXPLAIN QUERY PLAN
    
    Returns (True, None) if valid, or (False, error_message) if invalid.
    """
   # Check for forbidden keywords (Security Layer)
    forbidden_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE"]
    for keyword in forbidden_keywords:
        
        if re.search(rf"\b{keyword}\b", sql_query, re.IGNORECASE):
            return False, f"Security Error: Forbidden keyword '{keyword}' detected. Only SELECT queries allowed."
    
    # Syntax validation using EXPLAIN QUERY PLAN
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
       
        cursor.execute(f"EXPLAIN QUERY PLAN {sql_query}")
        conn.close()
        return True, None
    except sqlite3.Error as e:
        if conn:
            conn.close()
        return False, f"SQL Syntax Error: {str(e)}"

def agent_loop(user_question):
    """
    Main agentic loop with self-correction capability.
    
    Process:
    1. Generate initial SQL from user question
    2. Validate (forbidden keywords + syntax)
    3. If invalid, feed error back to model and retry
    4. Maximum 3 retry attempts
    """
    print(f"\n{'='*70}")
    print(f"🔵 USER QUESTION: {user_question}")
    print(f"{'='*70}")
    
    # Initial Generation ---
    prompt = f"{SCHEMA_CONTEXT}\n\nQuestion: {user_question}\nSQL:"
    print(" Generating SQL...")
    raw_response = run_ollama(prompt)
    
    # Debug: Show raw output if it's suspiciously short
    if len(raw_response) < 20:
        print(f"  Warning: Short response from model: '{raw_response}'")
    sql_candidate = clean_sql(raw_response)
    
    print(f"\n  Initial SQL Generated:")
    print(f"   {sql_candidate}")

    #  SELF-CORRECTION LOOP 
    for attempt in range(MAX_RETRIES):
        print(f"\n Validation Attempt {attempt + 1}/{MAX_RETRIES}...")
        is_valid, error_msg = validate_sql(sql_candidate)
        
        if is_valid:
            print(" Validation PASSED! Executing query...\n")
            
           
            conn = sqlite3.connect(DB_PATH)
            try:
                cursor = conn.cursor()
                cursor.execute(sql_candidate)
                results = cursor.fetchall()
                
                
                col_names = [description[0] for description in cursor.description]
                
                print(f" QUERY RESULTS:")
                print(f"   Columns: {col_names}")
                print(f"   Rows: {len(results)}")
                for row in results[:10]:
                    print(f"   {row}")
                if len(results) > 10:
                    print(f"   ... ({len(results) - 10} more rows)")
                
                conn.close()
                print(f"\n{'='*70}")
                return results
                
            except Exception as e:
                print(f" Runtime error during execution: {e}")
                conn.close()
                return None
        
        else:
            # Validation failed - enter self-correction mode
            print(f" Validation FAILED!")
            print(f"   Error: {error_msg}\n")
            
            if attempt < MAX_RETRIES - 1:  
                print(" Initiating self-correction: Feeding error back to model...")
                
                # Feedback the prompt with error details
                fix_prompt = (
                    f"{SCHEMA_CONTEXT}\n\n"
                    f"The SQL query below has an error. Fix it.\n\n"
                    f"Bad SQL: {sql_candidate}\n"
                    f"Error: {error_msg}\n\n"
                    f"Question: {user_question}\n"
                    f"Fixed SQL:"
                )
                
                raw_response = run_ollama(fix_prompt)
                sql_candidate = clean_sql(raw_response)
                
                print(f" Corrected SQL Generated:")
                print(f"   {sql_candidate}")
    
    print("\n FAILURE: Agent could not generate valid SQL after all retry attempts.")
    print(f"{'='*70}\n")
    return None



# MAIN EXECUTION - TEST CASES(3 cases)

if __name__ == "__main__":
    print("\n" + "="*70)
    print("SQL AGENT WITH SELF-CORRECTION - DEMONSTRATION")
    print("Model: Qwen2.5:1.5b (1.5B parameters)")
    print("="*70)
    
    # Test Case 1: Simple query
    print("\n[TEST 1: Simple Query]")
    agent_loop("Show me all users from the North region")
    
    # Test Case 2: Complex JOIN 
    print("\n[TEST 2: Complex JOIN Query]")
    agent_loop("Calculate the total money spent by each user")
    
    # Test Case 3: Intentionally challenging query
    print("\n[TEST 3: Multi-table Aggregation]")
    agent_loop("Show the top 3 products by total revenue with user counts")
    
    print("\n" + "="*70)
    print("DEMONSTRATION COMPLETE")
    print("="*70)