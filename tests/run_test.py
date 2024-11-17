import argparse
import subprocess
import sys
import time
import logging
import os
from datetime import datetime

# Create logs directory structure if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'test_runner')
os.makedirs(log_dir, exist_ok=True)

# Configure logging
log_file = os.path.join(log_dir, f'test_runner_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def run_test(test_id: int) -> bool:
    """
    Run both server and client with the specified test ID
    Returns True if both processes complete successfully
    """
    logger.info(f"Starting test run for test ID: {test_id}")
    
    try:
        # Start server process
        logger.info("Starting server process")
        server_process = subprocess.Popen(
            [sys.executable, 'tests/server.py', str(test_id)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Give the server time to start up
        logger.debug("Waiting for server to initialize...")
        time.sleep(2)
        
        # Start client process
        logger.info("Starting client process")
        client_process = subprocess.Popen(
            [sys.executable, 'tests/client.py', str(test_id)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for client to complete
        logger.debug("Waiting for client process to complete")
        client_stdout, client_stderr = client_process.communicate(timeout=30)
        client_success = client_process.returncode == 0
        
        # Wait for server to complete
        logger.debug("Waiting for server process to complete")
        server_stdout, server_stderr = server_process.communicate(timeout=5)
        server_success = server_process.returncode == 0
        
        # Log outputs
        if client_stdout:
            logger.debug(f"Client stdout: {client_stdout.decode()}")
        if client_stderr:
            logger.warning(f"Client stderr: {client_stderr.decode()}")
        if server_stdout:
            logger.debug(f"Server stdout: {server_stdout.decode()}")
        if server_stderr:
            logger.warning(f"Server stderr: {server_stderr.decode()}")
        
        # Check results
        if client_success and server_success:
            logger.info("Test completed successfully")
            return True
        else:
            logger.error("Test failed")
            if not client_success:
                logger.error("Client process failed")
            if not server_success:
                logger.error("Server process failed")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("Test timed out")
        _cleanup_processes(server_process, client_process)
        return False
    except Exception as e:
        logger.error(f"Error running test: {e}", exc_info=True)
        _cleanup_processes(server_process, client_process)
        return False

def _cleanup_processes(server_process: subprocess.Popen, client_process: subprocess.Popen) -> None:
    """Helper function to clean up processes"""
    logger.info("Cleaning up processes")
    try:
        client_process.kill()
        server_process.kill()
        logger.debug("Processes terminated")
    except Exception as e:
        logger.error(f"Error cleaning up processes: {e}", exc_info=True)

def main():
    parser = argparse.ArgumentParser(description='Run HTTP/2 server and client tests')
    parser.add_argument('test_id', type=int, help='Test ID to run')
    args = parser.parse_args()
    
    logger.info(f"Starting test runner with test ID: {args.test_id}")
    
    success = run_test(args.test_id)
    
    if success:
        logger.info("Test run completed successfully")
        print("\nTest completed successfully! 🎉")
        sys.exit(0)
    else:
        logger.error("Test run failed")
        print("\nTest failed! ❌")
        sys.exit(1)

if __name__ == '__main__':
    main()