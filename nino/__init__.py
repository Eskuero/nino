import os
import sys
import json
import copy
import colorama
from .project import project
from .utils import utils
from .statics import statics

def main():
	# Start colorama for ANSI escape codes under Windows
	colorama.init()

	# Check everything is in place before even starting to retrieve information
	utils.dpnds()

	# We store the configuration on a dictionary for ease on accesing the data
	config = {"projects": {"default": {}}, "keystores": {}, "devices": {}, "retry": False, "force": []}
	# Global defaults for all projects
	defconfig = {
		"sync": False,
		"preserve": False,
		"build": False,
		"tasks": {
			"release": {
				"exec": "assembleRelease"
			}
		},
		"keystore": False,
		"keyalias": False,
		"deploy": []
	}

	# Create the out directory in case it doesn't exist already
	if not os.path.isdir("NINO-RELEASES"):
		os.mkdir("NINO-RELEASES")

	# Parse command line arguments and modify running config accordingly
	utils.cmdargs(config)

	# When retrying we completely ignore configurations from file and cmdargs
	if config["retry"]:
		try:
			with open(".nino-last", "r") as file:
				config.update(json.load(file))
		except:
			print("Failed to load retryable config from .nino-last so can't proceed")
			sys.exit(1)
	else:
		# Retrieve configuration file and load options
		config.update(utils.cfgfile())

	# Add missing fields in default project config using values from defconfig
	for entry in defconfig:
		if entry not in config["projects"]["default"]:
			config["projects"]["default"][entry] = defconfig[entry]

	# Retryable config that will be dumped onto .nino-last at the end, must retain keystore (before enables and promps) and device list
	failed = {
		"projects": {
			"default": copy.deepcopy(config["projects"]["default"])
		},
		"keystores": copy.deepcopy(config["keystores"]),
		"devices": copy.deepcopy(config["devices"])
	}

	# Enable keystores and aliases that will be used during the run
	utils.enablesigns(config)
	# Retrieve passwords for each keystore and key that may be used
	utils.promptpasswd(config["keystores"])

	# Loop for every folder on invocation dir
	for name in statics.projects:
		# Skip project if retrying but nothing to do
		if config["retry"] and name not in config["projects"]:
			continue
		os.chdir(name)
		# Initialize project class
		app = project(name, config)
		# Introduce the project
		app.presentation()
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
		os.chdir(statics.workdir)
	# Save the report to file
	with open(".nino-last", "w") as file:
		json.dump(failed, file)
