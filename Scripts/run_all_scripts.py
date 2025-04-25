import os
import subprocess

def run_script(script_name):
    script_path = os.path.join(os.path.dirname(__file__), script_name)
    print(f"Running: {script_path}")
    result = subprocess.run(["python", script_path], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"Error in {script_path}:\n{result.stderr}")

if __name__ == "__main__":
    run_script("plot_all.py")
    run_script("plot_rip_field_derivative.py")
    run_script("plot_rip_field_mean_std.py")
    run_script("plot_rip_field_overlay.py")
    run_script("plot_rip_field_second_derivative.py")    
    run_script("plot_rip_field.py")
    run_script("plot_rip_field_fit.py")
    run_script("compare_rip_field_to_hz.py")
    
    
    
