# scripts/run_all_scripts.py
import os
import subprocess


def run_all_scripts_in_folder(folder):
    """Run all .py scripts in a given folder alphabetically."""
    full_folder = os.path.abspath(folder)
    script_files = sorted(f for f in os.listdir(full_folder) if f.endswith(".py"))
    cwd = os.getcwd()
    os.chdir(folder)
    for script_name in script_files:
        if  "run_all" in script_name.lower():
            continue
        script_path = os.path.join(full_folder, script_name)
        print(f"Running: {script_path}")        
        result = subprocess.run(["py", script_path], capture_output=True, text=True)
        #subprocess.Popen(['py', script_path ])
        #if result.returncode == 0:
        #    print(result.stdout)
        #else:
        #    print(f"Error in {script_path}:\n{result.stderr}")

    os.chdir(cwd)

if __name__ == "__main__":    
    # rip-de scripts
    run_all_scripts_in_folder("rip-de/scripts")
    
    # rip-inf scripts (if any)
    run_all_scripts_in_folder("rip-inf/scripts")
    
    # global scripts
    run_all_scripts_in_folder("scripts")
    
