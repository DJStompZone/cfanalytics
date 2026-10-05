"""Data visualization and reporting routines."""
import sys
from cfanalytics.db import DatabaseManager

def print_top_ips(db_path: str, limit: int = 10) -> None:
    """Queries the database and prints the top offending IPs across all domains."""
    db = DatabaseManager(db_path)
    query = f"""
        SELECT client_ip, SUM(request_count) as total_requests 
        FROM cloudflare_requests 
        GROUP BY client_ip 
        ORDER BY total_requests DESC 
        LIMIT {limit}
    """
    results = db.query(query)
    
    sys.stdout.write(f"--- Top {limit} Offending IPs ---\n")
    for row in results:
        sys.stdout.write(f"IP: {row[0]:<15} | Total Requests: {row[1]}\n")
