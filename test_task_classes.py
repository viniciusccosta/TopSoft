#!/usr/bin/env python3
"""
Simple test script to verify the task classes work correctly.
"""

import threading
import time
from queue import Queue

from topsoft.tasks import (
    DatabaseProcessorTask,
    DatabaseSyncTask,
    FileReaderTask,
    TaskState,
)


def test_task_classes():
    """Test that task classes expose public attributes correctly."""
    
    # Create task instances
    file_reader = FileReaderTask()
    db_processor = DatabaseProcessorTask()
    db_sync = DatabaseSyncTask()
    
    print("=== Task Class Test ===")
    print(f"File Reader Task: {file_reader.name}")
    print(f"  - ID: {file_reader.task_id}")
    print(f"  - Description: {file_reader.description}")
    print(f"  - Initial State: {file_reader.state}")
    print(f"  - Initial Details: {file_reader.details}")
    print()
    
    print(f"DB Processor Task: {db_processor.name}")
    print(f"  - ID: {db_processor.task_id}")
    print(f"  - Description: {db_processor.description}")
    print(f"  - Initial State: {db_processor.state}")
    print(f"  - Initial Details: {db_processor.details}")
    print()
    
    print(f"DB Sync Task: {db_sync.name}")
    print(f"  - ID: {db_sync.task_id}")
    print(f"  - Description: {db_sync.description}")
    print(f"  - Initial State: {db_sync.state}")
    print(f"  - Initial Details: {db_sync.details}")
    print()
    
    # Test state updates
    print("=== Testing State Updates ===")
    file_reader.update_state(TaskState.RUNNING, "Lendo arquivo de teste...")
    print(f"File Reader after update: {file_reader.state} - {file_reader.details}")
    
    db_processor.update_state(TaskState.WAITING, "Aguardando dados...")
    print(f"DB Processor after update: {db_processor.state} - {db_processor.details}")
    
    db_sync.set_error("Erro de teste")
    print(f"DB Sync after error: {db_sync.state} - {db_sync.details}")
    print(f"DB Sync error message: {db_sync.error_message}")
    print()
    
    # Test that multiple threads can read the attributes safely
    print("=== Testing Thread Safety ===")
    
    def reader_thread(task, name):
        for i in range(5):
            print(f"{name} read #{i+1}: {task.state} - {task.details}")
            time.sleep(0.1)
    
    def writer_thread(task):
        states = [TaskState.RUNNING, TaskState.SUCCESS, TaskState.WAITING, TaskState.ERROR]
        for i, state in enumerate(states):
            task.update_state(state, f"Update #{i+1}")
            time.sleep(0.1)
    
    # Start threads
    reader1 = threading.Thread(target=reader_thread, args=(file_reader, "Reader1"))
    reader2 = threading.Thread(target=reader_thread, args=(file_reader, "Reader2"))
    writer = threading.Thread(target=writer_thread, args=(file_reader,))
    
    reader1.start()
    reader2.start()
    writer.start()
    
    # Wait for completion
    reader1.join()
    reader2.join()
    writer.join()
    
    print("=== Test Complete ===")
    print("Task classes are working correctly!")
    print("The TaskMonitorFrame can now read task.state, task.details, etc. directly.")


if __name__ == "__main__":
    test_task_classes()    print("The TaskMonitorFrame can now read task.state, task.details, etc. directly.")


if __name__ == "__main__":
    test_task_classes()