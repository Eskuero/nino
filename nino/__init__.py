import os
import json
from .project import project
from .utils import dpnds, cprint
from .statics import projects, workdir
from .config import running, retryconfig, failed

def main():
	# Check everything is in place before even starting to retrieve information
	dpnds()

	# Create the out directory in case it doesn't exist already
	if not os.path.isdir("NINO-RELEASES"):
		os.mkdir("NINO-RELEASES")

	# Loop for every folder on invocation dir
	for name in projects:
		# Skip project if retrying but nothing to do
		if running["retry"] and name not in running["projects"]:
			continue
		os.chdir(name)
		# Initialize project class
		app = project(name)
		# Introduce the project
		app.presentation()
		# If the project is set for retry skip normal execution and save previous config
		if name in retryconfig and not app.force:
			cprint("Project is set for retry, skipping.", "warning")
			cprint("Once fixed, rebuild via 'nino -r' or 'nino -f " + name, "warning")
			app.failed = retryconfig[name]
		else:
			# Initialize logging to file for output of each operation
			with open("log.txt", "w+") as app.logfile:
				# Sync the project
				if app.sync:
					app.fetch()
				# Only attempt gradle projects with build enabled and are either forced or have new changes
				if app.build and (app.changed or app.force):
					app.package()
				# We search for apks to sign and merge them to the current list
				if app.built == 0 or app.signlist:
					app.sign()
				# We deploy if we built something
				if app.deploylist:
					app.install()
		# Store retriable config for project if not empty
		if app.failed:
			failed["projects"][name] = app.failed
		# Go back to the invocation directory before moving onto the next project
		os.chdir(workdir)
	# Save the report to file
	with open(".nino-last", "w") as file:
		json.dump(failed, file)
