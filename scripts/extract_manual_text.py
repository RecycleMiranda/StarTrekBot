import re
import os

def clean_html(html_path, out_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Strip style tags and scripts
    content = re.sub(r'<style.*?>.*?</style>', '', content, flags=re.S)
    content = re.sub(r'<script.*?>.*?</script>', '', content, flags=re.S)
    
    # Replace <p>, <li>, <br> with newlines
    content = re.sub(r'<(p|li|br|h1|h2|h3).*?>', '\n', content)
    
    # Strip all other tags
    content = re.sub(r'<.*?>', '', content)
    
    # Normalize whitespace
    content = re.sub(r'\n\s*\n', '\n\n', content)
    content = re.sub(r' +', ' ', content)
    
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content.strip())

if __name__ == "__main__":
    manuals = [
        ("《星际迷航：下一代》技术手册.html", "tng_manual_clean.txt"),
        ("《星际迷航：深空九号》技术手册 (1).html", "ds9_manual_clean.txt")
    ]
    
    for html, txt in manuals:
        full_html = os.path.join("/Users/wanghaozhe/Documents/GitHub/StarTrekBot", html)
        full_txt = os.path.join("/Users/wanghaozhe/Documents/GitHub/StarTrekBot", txt)
        if os.path.exists(full_html):
            print(f"Cleaning {html} -> {txt}")
            clean_html(full_html, full_txt)
        else:
            print(f"Skipping {html} (not found)")
