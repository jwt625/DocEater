# PDF Processing Analysis for DocEater

**Analyze PDFs for privacy risks before uploading to DocEater.**

---

## 📊 Your Analysis Results

**Total PDFs:** 1,464 files (5.68 GB)

**Privacy Risk:**
- **HIGH:** 25 files (1.7%) - Review required
- **MEDIUM:** 95 files (6.5%) - Review recommended  
- **SAFE:** 1,344 files (91.8%) - Ready to process

---

## Quick Start

```bash
# 1. Run analysis
./analyze_pdfs.py

# 2. Review results
cat pdf_analysis_summary.txt

# 3. Edit exclusion list (uncomment files to exclude)
open pdf_exclusion_list.txt

# 4. Process PDFs (coming soon)
./process_pdfs.py
```

---

## Files

### Scripts
- **`analyze_pdfs.py`** - Scan PDFs and assess privacy risk

### Generated Files
- **`pdf_inventory.csv`** - Complete list with risk scores (open in Excel)
- **`pdf_analysis_summary.txt`** - Statistical analysis
- **`pdf_exclusion_list.txt`** - Files to exclude (edit this!)
- **`COMPARISON_REPORT.md`** - Comparison with Gemini's analysis

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

**Definitely exclude:**
- PayStubs (20 files)
- Passport scans
- Immigration docs (EAD, I-20, I-94, I-140, DS-2019)
- Insurance documents
- Transcripts
- Resumes
- Medical records
- Utility bills
- Financial documents

**Safe to process:**
- Academic papers
- Research papers
- Technical documentation
- Public reports

---

## More Info

- **Full comparison with Gemini:** See `COMPARISON_REPORT.md`
- **Customization:** Edit `analyze_pdfs.py` to add keywords/patterns
- **Re-run anytime:** `./analyze_pdfs.py` (backs up exclusion list first)
