import os
import re
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(BASE_DIR, "services", "bot", "app")
REGISTRY_PATH = os.path.join(BASE_DIR, "BYPASS_REGISTRY.md")

def merge_bypass(module_name):
    """
    Finds Subspace Bypass tags in a module and 'finalizes' them 
    by removing the tags and the original commented-out code.
    """
    module_path = os.path.join(APP_DIR, module_name)
    if not os.path.exists(module_path):
        print(f"Error: Module {module_name} not found at {module_path}")
        return False

    with open(module_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "<<< SUBSPACE BYPASS START >>>" not in content:
        print(f"No active bypasses found in {module_name}.")
        return False

    # Regex to find the bypass block
    # It captures the header, the metadata, the original code, the new code, and the footer.
    # We want to keep ONLY the [fixed logic] part.
    
    pattern = r"# <<< SUBSPACE BYPASS START >>>.*?# ORIGINAL CODE:.*?#.*?\n(.*?)\n# <<< SUBSPACE BYPASS END >>>"
    
    # We need a more robust regex that handles multi-line blocks carefully.
    # Pattern: 
    # 1. Start tag
    # 2. Metadata/Reason
    # 3. Original code section (starts with # ORIGINAL CODE:)
    # 4. The actual new logic (non-commented lines usually, but could be anything)
    # 5. End tag
    
    # Let's use a simpler approach: line by line state machine
    lines = content.split("\n")
    new_lines = []
    in_bypass = False
    in_original_block = False
    
    for line in lines:
        if "<<< SUBSPACE BYPASS START >>>" in line:
            in_bypass = True
            in_original_block = False
            continue
        
        if in_bypass:
            if "<<< SUBSPACE BYPASS END >>>" in line:
                in_bypass = False
                continue
            
            if "# ORIGINAL CODE:" in line:
                in_original_block = True
                continue
            
            if in_original_block:
                if line.strip().startswith("#"):
                    # Still in original commented block
                    continue
                else:
                    # We hit the actual new code
                    in_original_block = False
                    new_lines.append(line)
            else:
                # We are in metadata or the new code already
                if not line.strip().startswith("# REASON:"):
                    new_lines.append(line)
        else:
            new_lines.append(line)

    final_content = "\n".join(new_lines)
    
    with open(module_path, "w", encoding="utf-8") as f:
        f.write(final_content)
    
    print(f"Successfully merged bypasses in {module_name}.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 merge_bypass.py [module_name_or_id]")
        sys.exit(1)
    
    target = sys.argv[1]
    # Simple logic: if it ends in .py it's a module
    if target.endswith(".py"):
        merge_bypass(target)
    else:
        # TODO: Handle lookup by Fault ID in registry
        print("Fault ID lookup not yet implemented. Please provide module name (e.g. tools.py)")
