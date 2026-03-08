import sys
import json
import fitz  # PyMuPDF
import os

def test_extraction(dept_name="감사원"):
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resource", "budget_depts")
    index_path = os.path.join(base_dir, "meta", "00_사업목록_인덱스.json")
    
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    dept_info = data["부처별_사업목록"].get(dept_name)
    if not dept_info:
        print(f"No info for {dept_name}")
        return
        
    pdf_file = dept_info["파일명"]
    pdf_path = os.path.join(base_dir, pdf_file)
    dept_start_page = dept_info["원본_시작페이지"]
    
    # Check if PDF exists
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        return
        
    print(f"Parsing {pdf_file} ...")
    doc = fitz.open(pdf_path)
    
    for project in dept_info["사업목록"]:
        proj_name = project["사업명"]
        proj_start = project["원본_시작페이지"]
        proj_end = project["원본_끝페이지"]
        
        # Calculate local page indices (0-indexed for PyMuPDF)
        local_start = proj_start - dept_start_page
        local_end = proj_end - dept_start_page
        
        print(f"\n[{proj_name}] Pages: {local_start} to {local_end}")
        text_content = ""
        
        for p_idx in range(local_start, local_end + 1):
            if p_idx < len(doc):
                page = doc[p_idx]
                text_content += page.get_text() + "\n"
        
        # We just print the first 1000 characters to inspect structure
        print("--- Extracted Text Preview ---")
        print(text_content[:1000])
        print("------------------------------")
        
        # Stop after first project for test
        break

if __name__ == "__main__":
    test_extraction("감사원")
