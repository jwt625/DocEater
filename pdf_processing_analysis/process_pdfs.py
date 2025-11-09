#!/usr/bin/env python3
"""
Process PDFs and upload to DocEater with progress tracking.

Usage:
    ./process_pdfs.py --test --limit 5           # Test with 5 files
    ./process_pdfs.py --batch tiny               # Process tiny files only
    ./process_pdfs.py --batch small              # Process small files only
    ./process_pdfs.py --risk-level SAFE          # Process SAFE files only
    ./process_pdfs.py --all                      # Process all (respecting exclusions)
"""

import os
import sys
import csv
import time
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime

# Configuration
DOCLING_API_URL = "http://192.222.54.152:8000"
API_KEY = "dk_prod_8f2a9b4c6d1e3f5a7b9c2d4e6f8a1b3c5d7e9f2a4b6c8d1e"  # Admin key
INVENTORY_FILE = "pdf_inventory.csv"
EXCLUSION_FILE_MY = "pdf_exclusion_list.txt"
EXCLUSION_FILE_GEMINI = "pdf_exclusion_list_gemini.txt"
PROGRESS_FILE = "processing_progress.json"
ERROR_LOG_FILE = "processing_errors.log"

# Size categories (in MB)
SIZE_CATEGORIES = {
    'tiny': (0, 0.1),
    'small': (0.1, 1),
    'medium': (1, 10),
    'large': (10, 50),
    'huge': (50, float('inf'))
}


def load_inventory():
    """Load PDF inventory from CSV."""
    inventory = []
    with open(INVENTORY_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            inventory.append(row)
    return inventory


def load_exclusions():
    """Load exclusion lists from both sources."""
    exclusions = set()
    
    # Load my exclusions
    if os.path.exists(EXCLUSION_FILE_MY):
        with open(EXCLUSION_FILE_MY, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    exclusions.add(line)
    
    # Load Gemini exclusions
    if os.path.exists(EXCLUSION_FILE_GEMINI):
        with open(EXCLUSION_FILE_GEMINI, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                exclusions.add(row['Full Path'])
    
    # Remove false positives
    false_positives = {
        '/Users/wentaojiang/Downloads/+README.pdf',
        '/Users/wentaojiang/Downloads/README.pdf',
    }
    
    return exclusions - false_positives


def load_progress():
    """Load processing progress from JSON file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        'processed': [],
        'failed': [],
        'skipped': [],
        'start_time': None,
        'last_update': None
    }


def save_progress(progress):
    """Save processing progress to JSON file."""
    progress['last_update'] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def log_error(filepath, error_msg):
    """Log error to file."""
    with open(ERROR_LOG_FILE, 'a') as f:
        timestamp = datetime.now().isoformat()
        f.write(f"[{timestamp}] {filepath}\n")
        f.write(f"  Error: {error_msg}\n\n")


def upload_pdf(filepath, progress):
    """Upload a single PDF to DocEater."""
    try:
        # Check if already processed
        if filepath in progress['processed']:
            print(f"  ⏭️  Already processed, skipping")
            return 'skipped'
        
        # Prepare file
        filename = os.path.basename(filepath)
        
        # Upload to DocEater
        with open(filepath, 'rb') as f:
            files = {'file': (filename, f, 'application/pdf')}
            headers = {'X-API-Key': API_KEY}
            
            start_time = time.time()
            response = requests.post(
                f"{DOCLING_API_URL}/documents/upload",
                files=files,
                headers=headers,
                timeout=300  # 5 minute timeout
            )
            elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            doc_id = result.get('document_id', 'unknown')
            print(f"  ✅ Uploaded in {elapsed:.1f}s (doc_id: {doc_id})")
            progress['processed'].append(filepath)
            save_progress(progress)
            return 'success'
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            print(f"  ❌ Failed: {error_msg}")
            log_error(filepath, error_msg)
            progress['failed'].append({'path': filepath, 'error': error_msg})
            save_progress(progress)
            return 'failed'
    
    except Exception as e:
        error_msg = str(e)
        print(f"  ❌ Exception: {error_msg}")
        log_error(filepath, error_msg)
        progress['failed'].append({'path': filepath, 'error': error_msg})
        save_progress(progress)
        return 'failed'


def filter_files(inventory, exclusions, args):
    """Filter files based on command line arguments."""
    files_to_process = []
    
    for item in inventory:
        filepath = item['full_path']
        
        # Skip excluded files
        if filepath in exclusions:
            continue
        
        # Filter by risk level
        if args.risk_level and item['risk_level'] != args.risk_level:
            continue
        
        # Filter by batch size
        if args.batch:
            size_mb = float(item['size_mb'])
            min_size, max_size = SIZE_CATEGORIES[args.batch]
            if not (min_size <= size_mb < max_size):
                continue
        
        files_to_process.append(item)
    
    # Limit if specified
    if args.limit:
        files_to_process = files_to_process[:args.limit]
    
    return files_to_process


def print_summary(files_to_process, exclusions):
    """Print processing summary."""
    print("\n" + "="*80)
    print("PDF PROCESSING PLAN")
    print("="*80)
    print(f"Total files to process: {len(files_to_process)}")
    print(f"Total files excluded: {len(exclusions)}")
    print()
    
    # Breakdown by risk
    risk_counts = {}
    for item in files_to_process:
        risk = item['risk_level']
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
    
    print("By risk level:")
    for risk in ['SAFE', 'LOW', 'MEDIUM', 'HIGH']:
        count = risk_counts.get(risk, 0)
        if count > 0:
            print(f"  {risk}: {count}")
    print()
    
    # Breakdown by size
    size_counts = {'tiny': 0, 'small': 0, 'medium': 0, 'large': 0, 'huge': 0}
    total_size = 0
    for item in files_to_process:
        size_mb = float(item['size_mb'])
        total_size += size_mb
        
        if size_mb < 0.1:
            size_counts['tiny'] += 1
        elif size_mb < 1:
            size_counts['small'] += 1
        elif size_mb < 10:
            size_counts['medium'] += 1
        elif size_mb < 50:
            size_counts['large'] += 1
        else:
            size_counts['huge'] += 1
    
    print("By size:")
    for size, count in size_counts.items():
        if count > 0:
            print(f"  {size}: {count}")
    print(f"\nTotal size: {total_size:.2f} MB ({total_size/1024:.2f} GB)")
    print("="*80)
    print()


def main():
    parser = argparse.ArgumentParser(description='Process PDFs and upload to DocEater')
    parser.add_argument('--test', action='store_true', help='Test mode (dry run)')
    parser.add_argument('--limit', type=int, help='Limit number of files to process')
    parser.add_argument('--batch', choices=['tiny', 'small', 'medium', 'large', 'huge'],
                       help='Process specific size batch')
    parser.add_argument('--risk-level', choices=['SAFE', 'LOW', 'MEDIUM', 'HIGH'],
                       help='Process specific risk level only')
    parser.add_argument('--all', action='store_true', help='Process all files (respecting exclusions)')
    parser.add_argument('--resume', action='store_true', help='Resume from previous run')
    
    args = parser.parse_args()
    
    # Load data
    print("Loading inventory and exclusions...")
    inventory = load_inventory()
    exclusions = load_exclusions()
    progress = load_progress()
    
    # Filter files
    files_to_process = filter_files(inventory, exclusions, args)
    
    # Print summary
    print_summary(files_to_process, exclusions)
    
    # Confirm before processing
    if not args.test:
        response = input(f"Process {len(files_to_process)} files? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Aborted.")
            return
    
    # Initialize progress
    if not args.resume:
        progress['start_time'] = datetime.now().isoformat()
        progress['processed'] = []
        progress['failed'] = []
        progress['skipped'] = []
    
    # Process files
    print(f"\n{'='*80}")
    print(f"PROCESSING {len(files_to_process)} FILES")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    for i, item in enumerate(files_to_process, 1):
        filepath = item['full_path']
        filename = item['filename']
        size_mb = item['size_mb']
        risk = item['risk_level']
        
        print(f"[{i}/{len(files_to_process)}] {filename}")
        print(f"  Size: {size_mb} MB | Risk: {risk}")
        
        if args.test:
            print(f"  🧪 TEST MODE - Would upload to {DOCLING_API_URL}")
            result = 'test'
        else:
            result = upload_pdf(filepath, progress)
        
        if result == 'success':
            success_count += 1
        elif result == 'failed':
            failed_count += 1
        elif result == 'skipped':
            skipped_count += 1
        
        # Progress update every 10 files
        if i % 10 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            remaining = (len(files_to_process) - i) / rate if rate > 0 else 0
            print(f"\n  📊 Progress: {i}/{len(files_to_process)} ({i*100//len(files_to_process)}%)")
            print(f"  ⏱️  Elapsed: {elapsed/60:.1f}m | Remaining: ~{remaining/60:.1f}m")
            print(f"  ✅ Success: {success_count} | ❌ Failed: {failed_count} | ⏭️  Skipped: {skipped_count}\n")
    
    # Final summary
    total_time = time.time() - start_time
    print(f"\n{'='*80}")
    print("PROCESSING COMPLETE")
    print(f"{'='*80}")
    print(f"Total time: {total_time/60:.1f} minutes")
    print(f"Success: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"Skipped: {skipped_count}")
    
    if failed_count > 0:
        print(f"\n⚠️  Check {ERROR_LOG_FILE} for error details")
    
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()

