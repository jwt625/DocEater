# PDF Processing Analysis for DocEater

**Analyze PDFs for privacy risks before uploading to DocEater.**

---

## Analysis Results

**Total PDFs:** 1,464 files (5.68 GB)

**Privacy Risk:**
- **HIGH:** 25 files (1.7%) - Review required
- **MEDIUM:** 95 files (6.5%) - Review recommended
- **SAFE:** 1,344 files (91.8%) - Ready to process

---

## Quick Start

### 1. Analyze PDFs
```bash
./analyze_pdfs.py
```

### 2. Review & Exclude Sensitive Files
```bash
# Review analysis
cat pdf_analysis_summary.txt

# Edit exclusion list (uncomment files to exclude)
open pdf_exclusion_list.txt
```

### 3. Process PDFs
```bash
# Check server is running
./process_pdfs.py --check-server

# Test with 5 files
./process_pdfs.py --test --limit 5
./process_pdfs.py --limit 5

# Validate uploads
./process_pdfs.py --validate

# Process by size (recommended)
./process_pdfs.py --batch tiny      # 645 files, ~20 min
./process_pdfs.py --batch small     # 302 files, ~20 min
./process_pdfs.py --batch medium    # 313 files, ~60 min
./process_pdfs.py --batch large     # 66 files, ~75 min
./process_pdfs.py --batch huge      # 19 files, ~90 min

# Or process everything
./process_pdfs.py --all             # All 1,345 files, 3-6 hours
```

### 4. Resume After Interruption
```bash
# If interrupted (Ctrl+C or connection lost)
./process_pdfs.py --validate        # Check what was uploaded
./process_pdfs.py --batch medium --resume  # Continue from where you left off
```

---

## Files

### Scripts
- **`analyze_pdfs.py`** - Scan PDFs and assess privacy risk
- **`process_pdfs.py`** - Upload PDFs to DocEater with progress tracking

### Generated Files
- **`pdf_inventory.csv`** - Complete list with risk scores (1,464 files)
- **`pdf_analysis_summary.txt`** - Statistical analysis
- **`pdf_exclusion_list.txt`** - Files to exclude (edit this!)
- **`files_to_process.json`** - Final list of 1,345 files to process
- **`processing_progress.json`** - Real-time progress tracking (created during processing)
- **`processing_errors.log`** - Error details (created if errors occur)

### Documentation
- **`COMPARISON_REPORT.md`** - Comparison with Gemini's analysis
- **`PROCESSING_PLAN.md`** - Detailed processing guide

---

## Privacy Filtering

**7 Categories:** Financial, Personal Identity, Employment, Education, Medical, Legal, Personal Communication

**Risk Scoring:**
- Keyword match: +10 points
- Filename pattern: +5 points
- Sensitive directory: +15 points

**Risk Levels:**
- HIGH (≥20): Definitely review
- MEDIUM (10-19): Review recommended
- LOW (1-9): Probably safe
- SAFE (0): No sensitive patterns

---

## What to Exclude

**Definitely exclude (120 files):**
- PayStubs (20 files)
- Passport scans
- Immigration docs (EAD, I-20, I-94, I-140, DS-2019)
- Insurance documents
- Transcripts (4 files)
- Resumes
- Medical records
- Utility bills (11 files)
- Financial documents
- Personal documents with your name
- Travel confirmations

**Safe to process (1,345 files):**
- Academic papers (~1,200+ files)
- Research papers
- Technical documentation
- Public reports

---

## Progress Tracking

### How It Works
1. **Auto-save:** Progress saved after each successful upload
2. **Resume:** Use `--resume` to skip already-processed files
3. **Validate:** Use `--validate` to compare local progress with server state

### Progress File
`processing_progress.json` tracks:
- Processed files (with paths)
- Failed files (with error messages)
- Start time and last update

### Validation
Catches silent failures by comparing local progress with actual server state:
```bash
./process_pdfs.py --validate
```

---

## Common Commands

```bash
# Check server health
./process_pdfs.py --check-server

# Validate progress with server
./process_pdfs.py --validate

# Test mode (dry run)
./process_pdfs.py --test --limit 5

# Process specific batch
./process_pdfs.py --batch tiny
./process_pdfs.py --risk-level SAFE

# Resume after interruption
./process_pdfs.py --batch medium --resume

# Process everything
./process_pdfs.py --all
```

---

## More Info

- **Detailed processing plan:** See `PROCESSING_PLAN.md`
- **Comparison with Gemini:** See `COMPARISON_REPORT.md`
- **Customization:** Edit `analyze_pdfs.py` to add keywords/patterns
