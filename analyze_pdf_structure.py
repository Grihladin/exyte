"""
PDF Structure Analysis Script for 2021 International Building Code

This script extracts text from the first 20 pages of the PDF and analyzes
its structure to identify patterns for sections, subsections, tables, figures, etc.
"""

import re
from typing import Dict, List, Tuple
import PyPDF2
from collections import defaultdict


class PDFStructureAnalyzer:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.pages_text = []
        self.patterns = {
            'chapter_headers': [],
            'section_headers': [],
            'subsection_patterns': [],
            'numbered_lists': [],
            'table_references': [],
            'figure_references': [],
            'special_prefixes': []
        }
        
    def extract_text(self, num_pages: int = 20) -> None:
        """Extract text from the first num_pages pages of the PDF."""
        print(f"Extracting text from first {num_pages} pages...")
        
        with open(self.pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            pages_to_read = min(num_pages, total_pages)
            
            for page_num in range(pages_to_read):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                self.pages_text.append({
                    'page_num': page_num + 1,
                    'text': text
                })
                print(f"  Page {page_num + 1} extracted ({len(text)} characters)")
    
    def analyze_structure(self) -> None:
        """Analyze the extracted text to identify structure patterns."""
        print("\nAnalyzing document structure...")
        
        for page_data in self.pages_text:
            page_num = page_data['page_num']
            text = page_data['text']
            lines = text.split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Check for chapter headers (e.g., "CHAPTER 3")
                chapter_match = re.match(r'^CHAPTER\s+\d+', line, re.IGNORECASE)
                if chapter_match:
                    self.patterns['chapter_headers'].append({
                        'page': page_num,
                        'text': line,
                        'next_line': lines[i+1].strip() if i+1 < len(lines) else ''
                    })
                
                # Check for section numbering patterns (e.g., "307.1", "[F] 307.1")
                # Pattern: optional prefix + section number + optional subsection
                section_match = re.match(r'^(\[[\w\s]+\]\s+)?(\d{3,4}(?:\.\d+)*)\s+(.+)', line)
                if section_match:
                    prefix = section_match.group(1) or ''
                    section_num = section_match.group(2)
                    title = section_match.group(3)
                    
                    # Count the depth by number of dots
                    depth = section_num.count('.')
                    
                    self.patterns['section_headers'].append({
                        'page': page_num,
                        'prefix': prefix.strip(),
                        'number': section_num,
                        'title': title,
                        'depth': depth,
                        'full_text': line
                    })
                    
                    if prefix:
                        if prefix not in [p['prefix'] for p in self.patterns['special_prefixes']]:
                            self.patterns['special_prefixes'].append({
                                'prefix': prefix.strip(),
                                'example': line
                            })
                
                # Check for subsection patterns (e.g., "307.1.1", "307.1.1.1")
                subsection_match = re.match(r'^(\[[\w\s]+\]\s+)?(\d{3,4}(?:\.\d+){2,})\s+', line)
                if subsection_match:
                    self.patterns['subsection_patterns'].append({
                        'page': page_num,
                        'text': line,
                        'depth': subsection_match.group(2).count('.')
                    })
                
                # Check for numbered lists (e.g., "1.", "2.", etc.)
                list_match = re.match(r'^\d+\.\s+[A-Z]', line)
                if list_match:
                    self.patterns['numbered_lists'].append({
                        'page': page_num,
                        'text': line[:80] + '...' if len(line) > 80 else line
                    })
                
                # Check for table references (e.g., "Table 307.1", "TABLE 307.1")
                table_match = re.search(r'\bTABLE\s+\d+(?:\.\d+)*', line, re.IGNORECASE)
                if table_match:
                    self.patterns['table_references'].append({
                        'page': page_num,
                        'reference': table_match.group(),
                        'context': line[:100] + '...' if len(line) > 100 else line
                    })
                
                # Check for figure references (e.g., "Figure 307.1", "FIGURE 307.1")
                figure_match = re.search(r'\bFIGURE\s+\d+(?:\.\d+)*', line, re.IGNORECASE)
                if figure_match:
                    self.patterns['figure_references'].append({
                        'page': page_num,
                        'reference': figure_match.group(),
                        'context': line[:100] + '...' if len(line) > 100 else line
                    })
    
    def generate_report(self, output_file: str = 'pdf_structure_analysis.md') -> None:
        """Generate a markdown report with the analysis findings."""
        print(f"\nGenerating report: {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# PDF Structure Analysis: 2021 International Building Code\n\n")
            f.write("## Summary\n\n")
            f.write(f"- **Pages Analyzed**: {len(self.pages_text)}\n")
            f.write(f"- **Chapter Headers Found**: {len(self.patterns['chapter_headers'])}\n")
            f.write(f"- **Section Headers Found**: {len(self.patterns['section_headers'])}\n")
            f.write(f"- **Subsection Patterns Found**: {len(self.patterns['subsection_patterns'])}\n")
            f.write(f"- **Table References Found**: {len(self.patterns['table_references'])}\n")
            f.write(f"- **Figure References Found**: {len(self.patterns['figure_references'])}\n")
            f.write(f"- **Numbered Lists Found**: {len(self.patterns['numbered_lists'])}\n\n")
            
            # Chapter Headers
            f.write("## Chapter Headers\n\n")
            if self.patterns['chapter_headers']:
                for ch in self.patterns['chapter_headers'][:10]:
                    f.write(f"### Page {ch['page']}\n")
                    f.write(f"```\n{ch['text']}\n")
                    if ch['next_line']:
                        f.write(f"{ch['next_line']}\n")
                    f.write("```\n\n")
            else:
                f.write("No chapter headers found in the analyzed pages.\n\n")
            
            # Section Numbering Patterns
            f.write("## Section Numbering Patterns\n\n")
            if self.patterns['section_headers']:
                f.write("### Depth Distribution\n\n")
                depth_counts = defaultdict(int)
                for sec in self.patterns['section_headers']:
                    depth_counts[sec['depth']] += 1
                
                for depth in sorted(depth_counts.keys()):
                    f.write(f"- **Depth {depth}** (e.g., {'X' + '.Y' * depth}): {depth_counts[depth]} instances\n")
                f.write("\n")
                
                f.write("### Examples by Depth\n\n")
                by_depth = defaultdict(list)
                for sec in self.patterns['section_headers']:
                    by_depth[sec['depth']].append(sec)
                
                for depth in sorted(by_depth.keys()):
                    f.write(f"#### Depth {depth}\n\n")
                    for sec in by_depth[depth][:5]:
                        f.write(f"**Page {sec['page']}**: ")
                        if sec['prefix']:
                            f.write(f"`{sec['prefix']}` ")
                        f.write(f"`{sec['number']}` {sec['title']}\n\n")
                        f.write(f"```\n{sec['full_text']}\n```\n\n")
            else:
                f.write("No section headers found.\n\n")
            
            # Special Prefixes
            f.write("## Special Prefixes\n\n")
            if self.patterns['special_prefixes']:
                f.write("The following prefixes were found before section numbers:\n\n")
                for prefix_data in self.patterns['special_prefixes']:
                    f.write(f"- **{prefix_data['prefix']}**\n")
                    f.write(f"  - Example: `{prefix_data['example']}`\n\n")
            else:
                f.write("No special prefixes found.\n\n")
            
            # Numbered Lists
            f.write("## Numbered Lists\n\n")
            if self.patterns['numbered_lists']:
                f.write("Examples of numbered list items:\n\n")
                for item in self.patterns['numbered_lists'][:10]:
                    f.write(f"**Page {item['page']}**:\n```\n{item['text']}\n```\n\n")
            else:
                f.write("No numbered lists found.\n\n")
            
            # Table References
            f.write("## Table References\n\n")
            if self.patterns['table_references']:
                f.write("Examples of table references found:\n\n")
                for table in self.patterns['table_references'][:10]:
                    f.write(f"**Page {table['page']}**: `{table['reference']}`\n")
                    f.write(f"```\n{table['context']}\n```\n\n")
            else:
                f.write("No table references found.\n\n")
            
            # Figure References
            f.write("## Figure References\n\n")
            if self.patterns['figure_references']:
                f.write("Examples of figure references found:\n\n")
                for figure in self.patterns['figure_references'][:10]:
                    f.write(f"**Page {figure['page']}**: `{figure['reference']}`\n")
                    f.write(f"```\n{figure['context']}\n```\n\n")
            else:
                f.write("No figure references found.\n\n")
            
            # Raw Text Samples
            f.write("## Raw Text Samples\n\n")
            f.write("First few pages of raw extracted text for manual inspection:\n\n")
            for page_data in self.pages_text[:3]:
                f.write(f"### Page {page_data['page_num']}\n\n")
                f.write("```\n")
                f.write(page_data['text'][:1000])
                if len(page_data['text']) > 1000:
                    f.write("\n... (truncated)")
                f.write("\n```\n\n")
        
        print(f"Report generated successfully: {output_file}")


def main():
    """Main execution function."""
    pdf_path = "2021_International_Building_Code.pdf"
    
    print("="*60)
    print("PDF Structure Analysis Tool")
    print("="*60)
    print()
    
    analyzer = PDFStructureAnalyzer(pdf_path)
    
    try:
        # Extract text from first 50 pages to get past front matter
        analyzer.extract_text(num_pages=50)
        
        # Analyze the structure
        analyzer.analyze_structure()
        
        # Generate the report
        analyzer.generate_report()
        
        print("\n" + "="*60)
        print("Analysis complete!")
        print("="*60)
        
    except FileNotFoundError:
        print(f"Error: PDF file not found: {pdf_path}")
        print("Please ensure the file exists in the current directory.")
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
