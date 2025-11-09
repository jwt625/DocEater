#!/usr/bin/env python3
"""
PDF Inventory and Analysis Script for DocEater
Scans a directory for PDF files and generates comprehensive analysis with privacy filtering.
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import csv
import re
import argparse


# ============================================================================
# PRIVACY FILTERS - Extensive keyword patterns for sensitive content
# ============================================================================

SENSITIVE_PATTERNS = {
    'financial': [
        'invoice', 'receipt', 'bill', 'payment', 'transaction',
        'bank', 'statement', 'account', 'balance', 'credit card',
        'debit', 'paypal', 'venmo', 'zelle', 'wire transfer',
        'tax', 'w2', 'w-2', '1099', 'irs', 'refund',
        'salary', 'paycheck', 'paystub', 'pay stub', 'compensation',
        'expense', 'reimbursement', 'purchase order', 'po_'
    ],
    'personal_identity': [
        'passport', 'visa', 'ssn', 'social security',
        'driver license', 'drivers license', 'dl_', 'id card',
        'birth certificate', 'marriage certificate',
        'green card', 'ead', 'i-94', 'i-20', 'ds-160',
        'citizenship', 'naturalization'
    ],
    'employment': [
        'resume', 'cv', 'curriculum vitae',
        'offer letter', 'employment contract', 'nda',
        'non-disclosure', 'non-compete', 'severance',
        'performance review', 'termination', 'resignation'
    ],
    'education': [
        'transcript', 'diploma', 'degree', 'certificate of',
        'grade report', 'academic record', 'enrollment',
        'student id', 'tuition', 'financial aid'
    ],
    'medical': [
        'medical', 'health', 'prescription', 'rx_',
        'insurance', 'claim', 'eob', 'explanation of benefits',
        'hipaa', 'patient', 'diagnosis', 'treatment',
        'lab result', 'test result', 'vaccination', 'immunization'
    ],
    'legal': [
        'contract', 'agreement', 'lease', 'rental',
        'deed', 'title', 'mortgage', 'loan',
        'court', 'lawsuit', 'litigation', 'settlement',
        'will', 'trust', 'power of attorney', 'notary'
    ],
    'personal_communication': [
        'confidential', 'private', 'personal',
        'letter to', 'letter from', 'correspondence',
        'email print', 'message thread'
    ]
}

# Filename patterns that suggest personal/sensitive content
FILENAME_RISK_PATTERNS = [
    r'^\d{4}[-_]\d{2}[-_]\d{2}',  # Date-prefixed files (often scans)
    r'scan\d+',  # Scanned documents
    r'img[-_]\d+',  # Image scans
    r'document\d+',  # Generic document names
    r'untitled',  # Untitled documents
    r'screenshot',  # Screenshots
    r'photo[-_]\d+',  # Photo scans
    r'my[-_]',  # Files starting with "my"
    r'personal[-_]',  # Files with "personal"
    r'private[-_]',  # Files with "private"
]

# Subdirectory names that suggest sensitive content
SENSITIVE_DIRECTORIES = [
    'personal', 'private', 'confidential', 'taxes', 'tax',
    'medical', 'health', 'insurance', 'bank', 'financial',
    'paystub', 'paystubs', 'pay', 'salary', 'receipts', 'receipt',
    'invoices', 'bills', 'legal', 'contracts', 'documents',
    'scans', 'id', 'passport', 'visa', 'immigration'
]


# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def find_pdf_files(directory):
    """Find all PDF files in directory and subdirectories."""
    print(f"Scanning {directory} for PDF files...")
    result = subprocess.run(
        ['find', os.path.expanduser(directory), '-type', 'f', 
         '(', '-name', '*.pdf', '-o', '-name', '*.PDF', ')'],
        capture_output=True, text=True
    )
    
    pdf_files = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    print(f"Found {len(pdf_files)} PDF files")
    return pdf_files


def analyze_sensitivity(filename, parent_dir):
    """
    Analyze a file for potential sensitive content.
    Returns: (risk_level, matched_patterns, risk_score)
    """
    filename_lower = filename.lower()
    parent_lower = parent_dir.lower()
    
    matched_patterns = []
    risk_score = 0
    
    # Check keyword patterns
    for category, patterns in SENSITIVE_PATTERNS.items():
        for pattern in patterns:
            if pattern in filename_lower:
                matched_patterns.append(f"{category}:{pattern}")
                risk_score += 10
    
    # Check filename risk patterns
    for pattern in FILENAME_RISK_PATTERNS:
        if re.search(pattern, filename_lower):
            matched_patterns.append(f"pattern:{pattern}")
            risk_score += 5
    
    # Check directory sensitivity
    for sensitive_dir in SENSITIVE_DIRECTORIES:
        if sensitive_dir in parent_lower:
            matched_patterns.append(f"directory:{sensitive_dir}")
            risk_score += 15
    
    # Determine risk level
    if risk_score >= 20:
        risk_level = 'HIGH'
    elif risk_score >= 10:
        risk_level = 'MEDIUM'
    elif risk_score > 0:
        risk_level = 'LOW'
    else:
        risk_level = 'SAFE'
    
    return risk_level, matched_patterns, risk_score


def collect_inventory(pdf_files):
    """Collect detailed information about all PDF files."""
    inventory = []
    total_size = 0
    
    for i, pdf_path in enumerate(pdf_files, 1):
        if i % 100 == 0:
            print(f"Processing {i}/{len(pdf_files)}...")
        
        try:
            path = Path(pdf_path)
            stat = path.stat()
            
            # Analyze sensitivity
            risk_level, patterns, risk_score = analyze_sensitivity(
                path.name, path.parent.name
            )
            
            inventory.append({
                'full_path': str(path),
                'filename': path.name,
                'size_bytes': stat.st_size,
                'size_mb': round(stat.st_size / (1024*1024), 2),
                'modified_timestamp': stat.st_mtime,
                'modified_date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'parent_dir': path.parent.name,
                'risk_level': risk_level,
                'risk_score': risk_score,
                'risk_patterns': '|'.join(patterns) if patterns else ''
            })
            total_size += stat.st_size
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
    
    return inventory, total_size


def generate_statistics(inventory):
    """Generate comprehensive statistics from inventory."""
    stats = {
        'total_files': len(inventory),
        'total_size_gb': sum(item['size_bytes'] for item in inventory) / (1024**3),
        'size_distribution': {},
        'risk_distribution': {},
        'by_month': defaultdict(lambda: {'count': 0, 'size_mb': 0}),
        'by_directory': defaultdict(lambda: {'count': 0, 'size_mb': 0}),
        'by_year': defaultdict(lambda: {'count': 0, 'size_mb': 0}),
    }
    
    # Size distribution
    for item in inventory:
        size_mb = item['size_mb']
        if size_mb < 0.1:
            category = 'tiny'
        elif size_mb < 1:
            category = 'small'
        elif size_mb < 10:
            category = 'medium'
        elif size_mb < 50:
            category = 'large'
        else:
            category = 'huge'
        
        stats['size_distribution'][category] = stats['size_distribution'].get(category, 0) + 1
    
    # Risk distribution
    for item in inventory:
        risk = item['risk_level']
        stats['risk_distribution'][risk] = stats['risk_distribution'].get(risk, 0) + 1
    
    # By month and directory
    for item in inventory:
        date = datetime.strptime(item['modified_date'], '%Y-%m-%d %H:%M:%S')
        month_key = date.strftime('%Y-%m')
        year_key = date.strftime('%Y')
        
        stats['by_month'][month_key]['count'] += 1
        stats['by_month'][month_key]['size_mb'] += item['size_mb']
        
        stats['by_year'][year_key]['count'] += 1
        stats['by_year'][year_key]['size_mb'] += item['size_mb']
        
        stats['by_directory'][item['parent_dir']]['count'] += 1
        stats['by_directory'][item['parent_dir']]['size_mb'] += item['size_mb']
    
    return stats


def save_inventory_csv(inventory, output_file):
    """Save inventory to CSV file."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        if inventory:
            writer = csv.DictWriter(f, fieldnames=inventory[0].keys())
            writer.writeheader()
            writer.writerows(inventory)
    print(f"✅ Inventory saved to: {output_file}")


def save_summary_report(inventory, stats, output_file):
    """Generate and save comprehensive summary report."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("PDF INVENTORY ANALYSIS SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Total PDFs: {stats['total_files']:,} files\n")
        f.write(f"Total Size: {stats['total_size_gb']:.2f} GB\n")
        f.write(f"Date Range: {min(item['modified_date'] for item in inventory)} to ")
        f.write(f"{max(item['modified_date'] for item in inventory)}\n\n")
        
        # Size distribution
        f.write("=" * 80 + "\n")
        f.write("SIZE DISTRIBUTION\n")
        f.write("=" * 80 + "\n")
        size_order = ['tiny', 'small', 'medium', 'large', 'huge']
        size_labels = {
            'tiny': '< 100 KB',
            'small': '0.1 - 1 MB',
            'medium': '1 - 10 MB',
            'large': '10 - 50 MB',
            'huge': '> 50 MB'
        }
        for category in size_order:
            count = stats['size_distribution'].get(category, 0)
            pct = (count / stats['total_files'] * 100) if stats['total_files'] > 0 else 0
            f.write(f"{size_labels[category]:15s}: {count:5d} files ({pct:5.1f}%)\n")
        
        # Risk distribution
        f.write("\n" + "=" * 80 + "\n")
        f.write("PRIVACY RISK ASSESSMENT\n")
        f.write("=" * 80 + "\n")
        risk_order = ['HIGH', 'MEDIUM', 'LOW', 'SAFE']
        for risk in risk_order:
            count = stats['risk_distribution'].get(risk, 0)
            pct = (count / stats['total_files'] * 100) if stats['total_files'] > 0 else 0
            f.write(f"{risk:10s}: {count:5d} files ({pct:5.1f}%)\n")
        
        # By year
        f.write("\n" + "=" * 80 + "\n")
        f.write("DISTRIBUTION BY YEAR\n")
        f.write("=" * 80 + "\n")
        for year in sorted(stats['by_year'].keys(), reverse=True):
            data = stats['by_year'][year]
            f.write(f"{year}: {data['count']:5d} files, {data['size_mb']:10.2f} MB\n")
        
        # By month (last 12)
        f.write("\n" + "=" * 80 + "\n")
        f.write("DISTRIBUTION BY MONTH (Last 12 months)\n")
        f.write("=" * 80 + "\n")
        for month in sorted(stats['by_month'].keys(), reverse=True)[:12]:
            data = stats['by_month'][month]
            f.write(f"{month}: {data['count']:5d} files, {data['size_mb']:10.2f} MB\n")
        
        # By directory (top 30)
        f.write("\n" + "=" * 80 + "\n")
        f.write("DISTRIBUTION BY SUBDIRECTORY (Top 30)\n")
        f.write("=" * 80 + "\n")
        sorted_dirs = sorted(stats['by_directory'].items(), 
                           key=lambda x: x[1]['count'], reverse=True)
        for dir_name, data in sorted_dirs[:30]:
            f.write(f"{dir_name[:50]:50s}: {data['count']:5d} files, {data['size_mb']:10.2f} MB\n")
        
        # High risk files
        high_risk = [item for item in inventory if item['risk_level'] == 'HIGH']
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"HIGH RISK FILES (LIKELY SENSITIVE): {len(high_risk)} files\n")
        f.write("=" * 80 + "\n")
        f.write("These files should be carefully reviewed before processing!\n\n")
        for item in sorted(high_risk, key=lambda x: x['risk_score'], reverse=True)[:100]:
            f.write(f"[Score:{item['risk_score']:3d}] {item['filename']}\n")
            if item['risk_patterns']:
                f.write(f"          Reasons: {item['risk_patterns']}\n")
        if len(high_risk) > 100:
            f.write(f"\n... and {len(high_risk) - 100} more high-risk files\n")
        
        # Medium risk files
        medium_risk = [item for item in inventory if item['risk_level'] == 'MEDIUM']
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"MEDIUM RISK FILES (REVIEW RECOMMENDED): {len(medium_risk)} files\n")
        f.write("=" * 80 + "\n")
        for item in sorted(medium_risk, key=lambda x: x['risk_score'], reverse=True)[:50]:
            f.write(f"[Score:{item['risk_score']:3d}] {item['filename']}\n")
        if len(medium_risk) > 50:
            f.write(f"\n... and {len(medium_risk) - 50} more medium-risk files\n")
    
    print(f"✅ Summary report saved to: {output_file}")


def save_exclusion_list(inventory, output_file):
    """Generate exclusion list template with high/medium risk files."""
    high_risk = [item for item in inventory if item['risk_level'] in ['HIGH', 'MEDIUM']]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# PDF Exclusion List for DocEater Processing\n")
        f.write("# " + "=" * 76 + "\n")
        f.write("# Instructions:\n")
        f.write("#   - Uncomment (remove '#') any files you want to EXCLUDE from processing\n")
        f.write("#   - You can use exact filenames or glob patterns\n")
        f.write("#   - Lines starting with '#' are comments and will be ignored\n")
        f.write("# " + "=" * 76 + "\n\n")
        
        f.write("# Example patterns:\n")
        f.write("# my-personal-document.pdf\n")
        f.write("# *invoice*.pdf\n")
        f.write("# *tax*2024*.pdf\n")
        f.write("# Resume_*.pdf\n\n")
        
        f.write("# " + "=" * 76 + "\n")
        f.write(f"# HIGH & MEDIUM RISK FILES DETECTED: {len(high_risk)} files\n")
        f.write("# " + "=" * 76 + "\n")
        f.write("# These files matched sensitive keywords/patterns.\n")
        f.write("# REVIEW CAREFULLY and uncomment files you want to exclude!\n\n")
        
        # Group by risk level
        for risk_level in ['HIGH', 'MEDIUM']:
            risk_files = [item for item in high_risk if item['risk_level'] == risk_level]
            if risk_files:
                f.write(f"\n# --- {risk_level} RISK FILES ({len(risk_files)} files) ---\n\n")
                for item in sorted(risk_files, key=lambda x: x['risk_score'], reverse=True):
                    f.write(f"# [{item['risk_score']:3d}] {item['filename']}\n")
    
    print(f"✅ Exclusion list template saved to: {output_file}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Analyze PDF files for DocEater processing with privacy filtering'
    )
    parser.add_argument(
        '--directory', '-d',
        default='~/Downloads',
        help='Directory to scan for PDFs (default: ~/Downloads)'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default='pdf_processing_analysis',
        help='Output directory for analysis files (default: pdf_processing_analysis)'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 80)
    print("PDF INVENTORY AND ANALYSIS TOOL")
    print("=" * 80)
    print()
    
    # Find PDFs
    pdf_files = find_pdf_files(args.directory)
    if not pdf_files:
        print("No PDF files found!")
        return 1
    
    # Collect inventory
    print("\nCollecting detailed information...")
    inventory, total_size = collect_inventory(pdf_files)
    
    print(f"\nTotal files: {len(inventory)}")
    print(f"Total size: {total_size / (1024**3):.2f} GB")
    
    # Generate statistics
    print("\nGenerating statistics...")
    stats = generate_statistics(inventory)
    
    # Save outputs
    print("\nSaving analysis files...")
    save_inventory_csv(inventory, output_dir / 'pdf_inventory.csv')
    save_summary_report(inventory, stats, output_dir / 'pdf_analysis_summary.txt')
    save_exclusion_list(inventory, output_dir / 'pdf_exclusion_list.txt')
    
    # Print summary
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nFiles created in '{output_dir}':")
    print(f"  - pdf_inventory.csv           (Full inventory with risk scores)")
    print(f"  - pdf_analysis_summary.txt    (Statistical analysis)")
    print(f"  - pdf_exclusion_list.txt      (Template for excluding files)")
    print(f"\nPrivacy Risk Summary:")
    for risk in ['HIGH', 'MEDIUM', 'LOW', 'SAFE']:
        count = stats['risk_distribution'].get(risk, 0)
        pct = (count / stats['total_files'] * 100) if stats['total_files'] > 0 else 0
        print(f"  {risk:10s}: {count:5d} files ({pct:5.1f}%)")
    
    print(f"\n⚠️  IMPORTANT: Review {stats['risk_distribution'].get('HIGH', 0)} HIGH RISK files before processing!")
    print(f"   Edit pdf_exclusion_list.txt to exclude sensitive files.\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

