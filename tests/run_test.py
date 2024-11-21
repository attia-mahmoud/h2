import subprocess
import time
import sys
import os
import signal
import logging
from datetime import datetime
import argparse

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

def run_server_client():
    parser = argparse.ArgumentParser(description='HTTP/2 Test Runner')
    parser.add_argument('--test-id', type=int, help='Test case ID to run', required=True)
    args = parser.parse_args()

    server_process = None
    client_process = None
    
    try:
        # Set PYTHONPATH to include the tests directory
        env = os.environ.copy()
        env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__)) + os.pathsep + env.get('PYTHONPATH', '')

        # Start the server process with test ID
        logger.info(f"Starting HTTP/2 server with test ID {args.test_id}...")
        server_process = subprocess.Popen(
            [sys.executable, 'tests/server.py', '--test-id', str(args.test_id)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        # Wait for server to start
        time.sleep(2)
        
        # Start the client process with test ID
        logger.info(f"Starting HTTP/2 client with test ID {args.test_id}...")
        client_process = subprocess.Popen(
            [sys.executable, 'tests/client.py', '--test-id', str(args.test_id)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        # Wait for client to complete
        client_output, client_error = client_process.communicate(timeout=10)
        
        # Format and print client output
        client_log = format_output(client_output, client_error)
        if client_log:
            logger.info("\n=== Client Output ===\n%s", client_log)
            
        # Terminate server gracefully
        logger.info("Terminating server...")
        server_process.terminate()
        
        # Get server output
        server_output, server_error = server_process.communicate(timeout=5)
        
        # Format and print server output
        server_log = format_output(server_output, server_error)
        if server_log:
            logger.info("\n=== Server Output ===\n%s", server_log)
            
    except subprocess.TimeoutExpired:
        logger.error("Timeout waiting for processes to complete")
        for process in [client_process, server_process]:
            if process and process.poll() is None:
                process.terminate()
    except Exception as e:
        logger.error(f"Error running test: {e}")
    finally:
        # Ensure processes are terminated
        for process in [client_process, server_process]:
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    process.kill()

def main():
    logger.info("Starting HTTP/2 test suite")
    try:
        run_server_client()
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
    logger.info("Test suite completed")

if __name__ == '__main__':
    main()