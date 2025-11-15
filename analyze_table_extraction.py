"""
Comprehensive Table Extraction Test Report
Run this after making changes to verify improvements.
"""

import json
from pathlib import Path


def analyze_table_extraction():
    """Analyze table extraction success rates and quality."""
    
    json_path = Path("parser/output/parsed_document.json")
    if not json_path.exists():
        print("Error: parsed_document.json not found")
        print("Run: cd parser && uv run python -m src.main")
        return
    
    with open(json_path) as f:
        data = json.load(f)
    
    print("\n" + "="*80)
    print("TABLE EXTRACTION ANALYSIS")
    print("="*80 + "\n")
    
    # Overall statistics
    total_refs = 0
    extracted = 0
    text_refs = 0
    accuracy_scores = []
    
    table_details = []
    
    for chapter in data['chapters']:
        for section in chapter.get('sections', []):
            for table_ref in section.get('references', {}).get('tables', []):
                total_refs += 1
                td = table_ref.get('table_data')
                
                if td is not None:
                    extracted += 1
                    if td.get('accuracy'):
                        accuracy_scores.append(td['accuracy'])
                    
                    table_details.append({
                        'section': section['section_number'],
                        'reference': table_ref['reference'],
                        'page': td['page'],
                        'cols': len(td['headers']),
                        'rows': len(td['rows']),
                        'accuracy': td.get('accuracy', 0)
                    })
                else:
                    text_refs += 1
    
    # Print statistics
    success_rate = (extracted / total_refs * 100) if total_refs > 0 else 0
    avg_accuracy = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0
    
    print(f"📊 OVERALL STATISTICS:")
    print(f"  Total table references: {total_refs}")
    print(f"  ✅ Actual tables extracted: {extracted} ({success_rate:.1f}%)")
    print(f"  📝 Text references (cross-refs): {text_refs} ({text_refs/total_refs*100:.1f}% - expected)")
    print(f"  📊 Average extraction accuracy: {avg_accuracy:.2f}%")
    print()
    print(f"  ℹ️  Note: Text references (table_data=null) are CORRECT - they point to tables on other pages")
    print()
    
    # Best extractions
    if table_details:
        print(f"✅ TOP 10 SUCCESSFUL EXTRACTIONS:")
        sorted_tables = sorted(table_details, key=lambda x: x['accuracy'], reverse=True)
        for i, t in enumerate(sorted_tables[:10], 1):
            print(f"  {i:2d}. Section {t['section']:10s} | {t['reference']:20s} | "
                  f"Page {t['page']:3d} | {t['cols']:2d} cols × {t['rows']:3d} rows | "
                  f"Accuracy: {t['accuracy']:.1f}%")
        print()
    
    # Section 307 analysis (hazardous materials tables)
    print(f"🧪 HAZARDOUS MATERIALS TABLES (Section 307):")
    section_307_tables = [t for t in table_details if t['section'].startswith('307')]
    if section_307_tables:
        for t in section_307_tables:
            status = "✓" if t['accuracy'] > 90 else "⚠"
            print(f"  {status} Section {t['section']:10s} | {t['reference']:20s} | "
                  f"Page {t['page']:3d} | {t['cols']:2d} cols × {t['rows']:3d} rows | "
                  f"Accuracy: {t['accuracy']:.1f}%")
    else:
        print("  ⚠ No Section 307 tables found")
    print()
    
    # Quality distribution
    if accuracy_scores:
        high_quality = sum(1 for a in accuracy_scores if a >= 90)
        medium_quality = sum(1 for a in accuracy_scores if 70 <= a < 90)
        low_quality = sum(1 for a in accuracy_scores if a < 70)
        
        print(f"📈 QUALITY DISTRIBUTION:")
        print(f"  High quality (≥90%):  {high_quality:3d} tables ({high_quality/len(accuracy_scores)*100:.1f}%)")
        print(f"  Medium quality (70-89%): {medium_quality:3d} tables ({medium_quality/len(accuracy_scores)*100:.1f}%)")
        print(f"  Low quality (<70%):   {low_quality:3d} tables ({low_quality/len(accuracy_scores)*100:.1f}%)")
        print()
    
    # Size analysis
    if table_details:
        avg_cols = sum(t['cols'] for t in table_details) / len(table_details)
        avg_rows = sum(t['rows'] for t in table_details) / len(table_details)
        largest = max(table_details, key=lambda x: x['cols'] * x['rows'])
        
        print(f"📏 SIZE ANALYSIS:")
        print(f"  Average dimensions: {avg_cols:.1f} cols × {avg_rows:.1f} rows")
        print(f"  Largest table: Section {largest['section']} | {largest['reference']}")
        print(f"    {largest['cols']} cols × {largest['rows']} rows = {largest['cols']*largest['rows']} cells")
        print()
    
    print("="*80)
    print(f"✅ SUMMARY: {extracted} tables extracted with {avg_accuracy:.1f}% avg accuracy")
    print(f"📝 Plus {text_refs} text cross-references (correct behavior)")
    if avg_accuracy >= 90:
        print("🎉 Excellent extraction quality!")
    elif avg_accuracy >= 75:
        print("👍 Good extraction quality")
    else:
        print("⚠️  Extraction quality needs improvement")
    print("="*80 + "\n")


if __name__ == "__main__":
    analyze_table_extraction()
