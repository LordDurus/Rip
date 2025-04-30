from pathlib import Path
import subprocess
import sys
import os

# project root is two levels up from this file (…/Rip)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

def run_all_scripts_in_folder(relative_folder: Path):
	"""Run all .py scripts in a given folder alphabetically."""
	# resolve scripts/ under the project root
	scripts_dir = (PROJECT_ROOT / relative_folder).resolve()
	script_files = sorted(scripts_dir.glob("*.py"))

	# remember current cwd, then cd into the scripts folder
	cwd = Path.cwd()
	os.chdir(scripts_dir)

	for script_path in script_files:
		if "run_all" in script_path.name.lower():
			continue

		# ensure data & assets live at the project root
		#(PROJECT_ROOT / "data").mkdir(exist_ok=True)
		#(PROJECT_ROOT / "assets").mkdir(exist_ok=True)
		#(PROJECT_ROOT / "assets" / "history").mkdir(exist_ok=True)

		print(f"Running: {script_path}")
		result = subprocess.run(["py", str(script_path)], capture_output=True, text=True)
		if result.returncode == 0:
			print(result.stdout)
		else:
			print(f"Error in {script_path}:\n{result.stderr}")

	# restore whatever cwd you started in
	os.chdir(cwd)

if __name__ == "__main__":
	# point to the two sub‐folders under the project root
	run_all_scripts_in_folder(Path("rip-de") / "scripts")
	run_all_scripts_in_folder(Path("rip-inf") / "scripts")

	# just echo the name of this launcher script
	print(PROJECT_ROOT)
	run_all_scripts_in_folder(PROJECT_ROOT / "scripts")