import subprocess
import time
import sys
import os
import signal
import logging
from datetime import datetime
import argparse
import json

# Import your overload module
import overload

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def format_output(output: bytes, error: bytes):
    """Format process output, combining stdout and stderr"""
    result = []
    if output:
        result.append("=== STDOUT ===")
        result.append(output.decode().strip())
    if error:
        # Filter out hpack debug messages
        error_lines = [
            line for line in error.decode().strip().split('\n')
            if not (line.startswith('DEBUG:hpack') or line.startswith('DEBUG:h2'))
        ]
        if error_lines:
            result.append("=== STDERR ===")
            result.append('\n'.join(error_lines))
    return '\n'.join(result)

def run_single_test(test_id: int, verbose: bool = False) -> bool:
    """Run a single test. Returns True if no error occurred"""
    server_process = None
    client_process = None
    success = False
    
    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__)) + os.pathsep + env.get('PYTHONPATH', '')

        if verbose:
            logger.info(f"Starting HTTP/2 server with test ID {test_id}...")
        server_process = subprocess.Popen(
            [sys.executable, 'tests/server.py', '--test-id', str(test_id)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        time.sleep(2)
        
        if verbose:
            logger.info(f"Starting HTTP/2 client with test ID {test_id}...")
        client_process = subprocess.Popen(
            [sys.executable, 'tests/client.py', '--test-id', str(test_id)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        client_output, client_error = client_process.communicate(timeout=10)
        
        if verbose:
            client_log = format_output(client_output, client_error)
            if client_log:
                logger.info("\n=== Client Output ===\n%s", client_log)
            logger.info("Terminating server...")
            
        server_process.terminate()
        server_output, server_error = server_process.communicate(timeout=5)
        
        if verbose:
            server_log = format_output(server_output, server_error)
            if server_log:
                logger.info("\n=== Server Output ===\n%s", server_log)
        
        client_error_str = client_error.decode() if client_error else ""
        server_error_str = server_error.decode() if server_error else ""
        
        # Check for actual error indicators
        error_indicators = [
            "Error:",
            "Exception:",
            "Traceback (most recent call last):",
            "Failed:",
            "AssertionError"
        ]
        
        has_errors = any(indicator in client_error_str or indicator in server_error_str 
                        for indicator in error_indicators)
        
        success = not has_errors
        return success
        
    except Exception as e:
        if verbose:
            logger.error(f"Error running test: {e}")
        return False
    finally:
        for process in [client_process, server_process]:
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    process.kill()

def run_all_tests():
    """Run all tests from the JSON file"""
    try:
        with open('tests/test_cases.json', 'r') as f:
            test_cases = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load test cases: {e}")
        return

    for test_case in test_cases:
        test_id = test_case.get('id')
        if test_id is None:
            continue
            
        success = run_single_test(test_id, verbose=False)
        print(f"Test {test_id}: {'No Error' if success else 'Error'}")

def main():
    parser = argparse.ArgumentParser(description='HTTP/2 Test Runner')
    parser.add_argument('--test-id', type=int, help='Test case ID to run', required=False)
    args = parser.parse_args()

    if args.test_id is not None:
        run_single_test(args.test_id, verbose=True)
    else:
        run_all_tests()

if __name__ == '__main__':
    main()